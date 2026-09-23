"""Batched option readout on llama.cpp with a sequence tree.

Every prompt is `template + state + question`. The template (system prompt) is
decoded once at startup and stays resident in sequence 0. Per batch:

  wave 1  each distinct state is branched from the template (seq_cp) and decoded once
  wave 2  each question is branched from its state and decoded; logits are read
          only at the answer position, restricted to the declared option tokens
  wave 3+ only for >26 options: one extra single-token branch per code digit

All nodes of a wave go through the same llama_decode calls, so questions (and
concurrent requests) share one pass over the weights. seq_cp on Qwen3.5's hybrid
memory shares attention KV cells and copy-on-writes the recurrent state.
"""

from __future__ import annotations

import ctypes
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .prompts import LETTERS, Readout, template_text

TEMPLATE_SEQ = 0


class EngineError(RuntimeError):
    pass


class ContextOverflow(EngineError):
    pass


@dataclass(eq=False)
class Node:
    """A token run decoded in its own sequence, branched from `parent`."""

    parent: "Node | None"
    tokens: list[int]
    on_logits: Callable | None = None  # (node, float*) -> list[Node] children created on the fly
    children_left: int = 0
    seq: int = -1
    pos0: int = 0
    full: list[int] = field(default_factory=list)  # every token from position 0, for re-rooting
    leaf: bool = False  # no children ever: tokens after the answer position cannot change its logits


def _lcp(a: list[int], b: list[int]) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _softmax(values: list[float], temperature: float) -> list[float]:
    scaled = [v / temperature for v in values]
    peak = max(scaled)
    weights = [math.exp(v - peak) for v in scaled]
    total = sum(weights)
    return [w / total for w in weights]


class Engine:
    def __init__(
        self,
        gguf: str | Path,
        *,
        n_ctx: int = 16384,
        n_seq_max: int = 16,
        n_batch: int = 2048,
        n_ubatch: int = 512,
        n_gpu_layers: int = 999,
        flash_attn: bool = True,
        threads: int | None = None,
        temperature: float = 1.8,
        pad_leaves: float = 0.5,
        min_shared_tokens: int = 64,
        profile: str = "semif",
    ):
        import llama_cpp as L

        if n_gpu_layers:
            n_ctx, n_seq_max, n_ubatch = _fit_gpu(Path(gguf), n_ctx, n_seq_max, n_ubatch)
        self.L = L
        self.temperature = temperature
        self.min_shared_tokens = min_shared_tokens
        self.pad_leaves = pad_leaves  # max padding overhead (fraction of real leaf tokens); 0 disables
        self.n_batch = n_batch
        L.llama_backend_init()
        L.llama_log_set(_quiet_logger(L), ctypes.c_void_p())
        mp = L.llama_model_default_params()
        mp.n_gpu_layers = n_gpu_layers
        self.model = L.llama_model_load_from_file(str(gguf).encode(), mp)
        if not self.model:
            raise EngineError(f"cannot load GGUF: {gguf}")
        cp = L.llama_context_default_params()
        cp.n_ctx = n_ctx
        cp.n_batch = n_batch
        cp.n_ubatch = n_ubatch
        cp.n_seq_max = n_seq_max
        cp.kv_unified = True
        cp.flash_attn_type = L.LLAMA_FLASH_ATTN_TYPE_ENABLED if flash_attn else L.LLAMA_FLASH_ATTN_TYPE_DISABLED
        cp.no_perf = True
        threads = threads or min(8, os.cpu_count() or 4)
        cp.n_threads = cp.n_threads_batch = threads
        # Smaller GPUs: halve parallel branches, then context, until the context fits in VRAM.
        self.ctx = None
        while not self.ctx:
            self.ctx = L.llama_init_from_model(self.model, cp)
            if self.ctx:
                break
            if cp.n_seq_max > 8:
                cp.n_seq_max //= 2
            elif cp.n_ctx > 8192:
                cp.n_ctx //= 2
            else:
                raise EngineError("cannot create llama.cpp context: not enough GPU memory")
            print(f"[jevlocal] retrying with n_seq_max={cp.n_seq_max} n_ctx={cp.n_ctx}", file=sys.stderr, flush=True)
        self.mem = L.llama_get_memory(self.ctx)
        self.vocab = L.llama_model_get_vocab(self.model)
        self.n_ctx = L.llama_n_ctx(self.ctx)
        self.n_seq_max = L.llama_n_seq_max(self.ctx)
        self.batch = L.llama_batch_init(n_batch, 0, 1)
        self.letter_ids = {c: self._single(c) for c in LETTERS}
        self.digit_ids = {c: self._single(c) for c in "0123456789"}
        self.pool = list(range(self.n_seq_max - 1, 0, -1))
        # Drop the last template token so the state's first token can never merge across the boundary.
        self.profile = profile
        self.template = self.tokenize(template_text(profile))[:-1]
        root = Node(None, self.template)
        root.full = list(self.template)
        root.seq = TEMPLATE_SEQ
        self._decode_wave([root], [])
        self.template_node = root

    # -- tokenizer ---------------------------------------------------------------
    def tokenize(self, text: str) -> list[int]:
        L = self.L
        data = text.encode()
        n = len(data) + 16
        buf = (L.llama_token * n)()
        got = L.llama_tokenize(self.vocab, data, len(data), buf, n, False, True)
        if got < 0:
            buf = (L.llama_token * -got)()
            got = L.llama_tokenize(self.vocab, data, len(data), buf, -got, False, True)
        return list(buf[:got])

    def _single(self, text: str) -> int:
        ids = self.tokenize(text)
        if len(ids) != 1:
            raise EngineError(f"label {text!r} is not a single token in this GGUF vocabulary")
        return ids[0]

    # -- scheduling ----------------------------------------------------------------
    def _assign(self, ready: list[Node]) -> tuple[list[Node], list[Node]]:
        """Give sequences to as many ready nodes as fit; the last child of a parent inherits its seq."""
        L = self.L
        wave, deferred = [], []
        for node in ready:
            parent = node.parent
            inherit = parent is not None and parent is not self.template_node and parent.children_left == 1
            if not inherit and not self.pool:
                deferred.append(node)
                continue
            if inherit:
                node.seq = parent.seq
            else:
                node.seq = self.pool.pop()
                if parent is not None:
                    L.llama_memory_seq_cp(self.mem, parent.seq, node.seq, -1, -1)
            if parent is not None:
                parent.children_left -= 1
            wave.append(node)
        if not wave and deferred:
            # Every sequence is held by a parent still waiting on several children. Re-root all
            # but one child of one parent on the template (re-decoding their shared prefix); the
            # remaining child then inherits the parent's sequence, so progress is guaranteed.
            parent = next(n.parent for n in deferred if n.parent not in (None, self.template_node))
            siblings = [n for n in deferred if n.parent is parent]
            for node in siblings[1:]:
                parent.children_left -= 1
                base = self.template_node if node.full[: len(self.template)] == self.template else None
                node.parent = base
                node.pos0 = len(self.template) if base else 0
                node.tokens = node.full[node.pos0:]
            return self._assign(deferred)
        return wave, deferred

    def _release(self, node: Node) -> None:
        self.L.llama_memory_seq_rm(self.mem, node.seq, -1, -1)
        self.pool.append(node.seq)
        node.seq = -1

    def _decode_wave(self, wave: list[Node], spawned: list[Node]) -> None:
        """Decode every node of a wave in shared llama_decode calls; fire logits callbacks."""
        L, batch = self.L, self.batch
        pending: list[tuple[int, Node]] = []
        fill = 0

        def flush():
            nonlocal fill
            if not fill:
                return
            batch.n_tokens = fill
            rc = L.llama_decode(self.ctx, batch)
            if rc != 0:
                raise ContextOverflow(f"llama_decode failed (rc={rc}); context or sequence budget exceeded")
            for index, node in pending:
                children = node.on_logits(node, L.llama_get_logits_ith(self.ctx, index)) or []
                for child in children:
                    child.parent = node
                    child.pos0 = node.pos0 + len(node.tokens)
                    child.full = node.full + child.tokens
                node.children_left = len(children)
                spawned.extend(children)
            pending.clear()
            fill = 0

        # Recurrent memory splits a batch into ubatches where every sequence contributes the same
        # number of tokens, so uneven branches waste most of each ubatch. Leaves are padded after
        # their answer position (causal: the answer logits are unchanged) to a shared length.
        leaves = [len(n.tokens) for n in wave if n.leaf]
        target = 0
        if self.pad_leaves and len(leaves) > 1:
            target = max(leaves)
            if sum(target - n for n in leaves) > self.pad_leaves * sum(leaves):
                target = 0  # too uneven: padding would cost more than it saves
        for node in wave:
            last = len(node.tokens) - 1
            tokens = node.tokens
            if node.leaf and target > len(tokens):
                tokens = tokens + [tokens[-1]] * (target - len(tokens))
            for offset, token in enumerate(tokens):
                if fill == self.n_batch:
                    flush()
                batch.token[fill] = token
                batch.pos[fill] = node.pos0 + offset
                batch.n_seq_id[fill] = 1
                batch.seq_id[fill][0] = node.seq
                want = offset == last and node.on_logits is not None
                batch.logits[fill] = want
                if want:
                    pending.append((fill, node))
                fill += 1
        flush()

    # -- readouts ------------------------------------------------------------------
    def _readout_callback(self, readout: Readout, prefix: str = "", mass: float = 1.0, acc=None):
        acc = acc if acc is not None else {}
        labels = readout.labels
        coded = labels[0] not in self.letter_ids
        T = self.temperature

        def done():
            displayed = [acc[label] for label in labels]
            probs = [0.0] * len(labels)
            for position, canonical in enumerate(readout.order):
                probs[canonical] = displayed[position]
            readout.probabilities = probs

        def callback(node, logits):
            if not coded:
                values = [logits[self.letter_ids[label]] for label in labels]
                for label, p in zip(labels, _softmax(values, T)):
                    acc[label] = p
                done()
                return []
            depth = len(prefix)
            nexts = sorted({label[depth] for label in labels if label.startswith(prefix)})
            probs = _softmax([logits[self.digit_ids[d]] for d in nexts], T)
            children = []
            for d, p in zip(nexts, probs):
                stem = prefix + d
                matches = [label for label in labels if label.startswith(stem)]
                if len(matches) == 1 and matches[0] == stem:
                    acc[stem] = mass * p
                elif len(matches) == 1:
                    acc[matches[0]] = mass * p  # only one completion: no need to read further digits
                else:
                    children.append(Node(None, [self.digit_ids[d]], self._readout_callback(readout, stem, mass * p, acc)))
            if len(acc) == len(labels):
                done()
            return children

        return callback

    def _is_letter(self, readout: Readout) -> bool:
        return readout.labels[0] in self.letter_ids

    def plan_nodes(self, readouts: list[Readout]) -> tuple[list[Node], int]:
        """Group readouts that share a system prompt and state into one prefix node + suffix branches."""
        groups: dict[tuple, list[tuple[Readout, list[int]]]] = {}
        for readout in readouts:
            ids = self.tokenize(readout.text)
            if len(ids) + 4 > self.n_ctx:
                raise ContextOverflow(f"prompt has {len(ids)} tokens; server context is {self.n_ctx}")
            groups.setdefault(readout.group, []).append((readout, ids))
        roots, tokens = [], 0
        tl = len(self.template)
        for members in groups.values():
            on_template = all(ids[:tl] == self.template for _, ids in members)
            base = self.template_node if on_template else None
            start = tl if on_template else 0
            for readout, ids in members:
                readout.charged = len(ids)
            if len(members) == 1:
                readout, ids = members[0]
                node = Node(base, ids[start:], self._readout_callback(readout), pos0=start, full=ids,
                            leaf=self._is_letter(readout))
                roots.append(node)
                tokens += len(node.tokens)
                continue
            shared = min(_lcp(members[0][1], ids) for _, ids in members)
            shared = min(shared, min(len(ids) for _, ids in members) - 1)
            for readout, ids in members[1:]:
                readout.charged = len(ids) - shared
            children = [
                Node(None, ids[shared:], self._readout_callback(readout), pos0=shared, full=ids,
                     leaf=self._is_letter(readout))
                for readout, ids in members
            ]
            # A separate prefix wave costs a full pass over the weights; only worth it when the
            # state tokens it saves (decoded once instead of per question) outweigh that pass.
            if (len(members) - 1) * (shared - start) >= self.min_shared_tokens:
                prefix = Node(base, members[0][1][start:shared], None, pos0=start, full=members[0][1][:shared])
                prefix.children_left = len(children)
                for child in children:
                    child.parent = prefix
                prefix._children = children  # decoded in the next wave
                roots.append(prefix)
                tokens += shared - start
            else:
                for child in children:
                    child.parent = base
                    child.pos0 = start
                    child.tokens = child.full[start:]
                roots.extend(children)
            tokens += sum(len(c.tokens) for c in children)
        return roots, tokens

    def score(self, readouts: list[Readout]) -> int:
        """Fill readout.probabilities for every readout; returns tokens decoded."""
        roots, tokens = self.plan_nodes(readouts)
        if tokens + len(self.template) > self.n_ctx:
            raise ContextOverflow(f"batch needs {tokens} tokens; server context is {self.n_ctx}")
        try:
            self._run(roots)
        except BaseException:
            self._reset()
            raise
        return tokens

    def warmup(self) -> None:
        """Run a few shapes once so CUDA graphs and buffers exist before the first real request."""
        from .prompts import plan_request

        q = {"type": "choice", "instructions": "Warm-up?", "criteria": {"a": "A", "b": "B", "c": "C"}}
        for n in (1, 3):
            body = {"state": "warm-up state " * 8, "model": "x", "questions": {f"q{i}": q for i in range(n)}}
            self.score(plan_request(body, profile=self.profile).readouts)

    def _reset(self) -> None:
        """Drop every branch after a failure; only the resident template survives."""
        for seq in range(1, self.n_seq_max):
            self.L.llama_memory_seq_rm(self.mem, seq, -1, -1)
        self.pool = list(range(self.n_seq_max - 1, 0, -1))

    def _run(self, roots: list[Node]) -> None:
        """Decode waves until every node is done; a prefix node's static children follow it."""
        ready = list(roots)
        while ready:
            wave, deferred = self._assign(ready)
            spawned: list[Node] = []
            self._decode_wave(wave, spawned)
            for node in wave:
                static = getattr(node, "_children", None)
                if static:
                    node.children_left = len(static)
                    spawned.extend(static)
                    node._children = None
                if node.children_left == 0:
                    self._release(node)
            ready = deferred + spawned
        if len(self.pool) != self.n_seq_max - 1:
            raise EngineError("sequence leak")

    def close(self) -> None:
        L = self.L
        if self.ctx:
            L.llama_batch_free(self.batch)
            L.llama_free(self.ctx)
            L.llama_model_free(self.model)
            self.ctx = None


DISPLAY_RESERVE_MB = 2560  # left free when the GPU also drives a desktop (compositor needs headroom)
HEADLESS_RESERVE_MB = 768


def _gpu_status() -> tuple[int, bool] | None:
    """(free MiB, display attached) of GPU 0 via nvidia-smi, or None when unavailable."""
    import subprocess

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free,display_active", "--format=csv,noheader,nounits", "-i", "0"],
            capture_output=True, text=True, timeout=10, check=True).stdout.strip().split(",")
        return int(out[0]), out[1].strip().lower() == "enabled"
    except Exception:  # noqa: BLE001
        return None


def _fit_gpu(gguf: Path, n_ctx: int, n_seq_max: int, n_ubatch: int) -> tuple[int, int, int]:
    """Shrink branches/context so the model never takes the VRAM a desktop on the same GPU needs.

    Estimate for Qwen3.5-4B: weights (file size) + 32 KiB/token KV + 50 MiB/branch recurrent
    state + compute buffers. A GPU that drives a display also gets short kernels (ubatch 512)
    so the compositor keeps getting time slices.
    """
    status = _gpu_status()
    if status is None:
        return n_ctx, n_seq_max, n_ubatch
    free, display = status
    reserve = DISPLAY_RESERVE_MB if display else HEADLESS_RESERVE_MB
    if display:
        n_ubatch = min(n_ubatch, 512)
    weights = gguf.stat().st_size / 2**20 * 1.05

    def need(ctx, seqs):
        return weights + ctx * 32 / 1024 + seqs * 50 + 256 + n_ubatch * 0.5

    while need(n_ctx, n_seq_max) > free - reserve:
        if n_seq_max > 8:
            n_seq_max //= 2
        elif n_ctx > 4096:
            n_ctx //= 2
        else:
            raise EngineError(f"not enough free VRAM: {free} MiB free, need ~{need(n_ctx, n_seq_max):.0f} MiB "
                              f"plus {reserve} MiB reserve{' for the display' if display else ''}")
    print(f"[jevlocal] GPU: {free} MiB free, display={'yes' if display else 'no'} -> ctx={n_ctx} seqs={n_seq_max} "
          f"ubatch={n_ubatch}, ~{need(n_ctx, n_seq_max):.0f} MiB planned", file=sys.stderr, flush=True)
    return n_ctx, n_seq_max, n_ubatch


def _quiet_logger(L):
    """Pass llama.cpp errors through; everything else only with JEVLOCAL_LLAMA_LOG=1."""
    verbose = bool(os.environ.get("JEVLOCAL_LLAMA_LOG"))

    @L.llama_log_callback
    def _log(level, text, user_data):
        if verbose or level == 4:
            os.write(2, text)

    _quiet_logger.keep = _log  # ctypes callbacks must outlive the call
    return _log
