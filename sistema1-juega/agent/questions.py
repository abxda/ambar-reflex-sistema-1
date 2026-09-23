"""The six atomic questions, in three wordings. Every decision sends all six in ONE request.

A: literal wording from the task spec (Spanish). Its crouch question says "low projectile", which is
   wrong for this game (crouching dodges chest-high bullets; low ones must be jumped) -> kept on purpose,
   it measures sensitivity to wording.
B: Spanish, geometric and matched to the game's physics, short option descriptions.
C: B in English (state also in English).
"""

from __future__ import annotations

DIRS8_ES = {"E": "derecha", "NE": "arriba-derecha", "N": "arriba", "NW": "arriba-izquierda",
            "W": "izquierda", "SW": "abajo-izquierda", "S": "abajo", "SE": "abajo-derecha"}
DIRS8_GEO_ES = {"E": "derecha (dx+, dy 0)", "NE": "arriba-derecha (dx+, dy+)", "N": "arriba (dy+)",
                "NW": "arriba-izquierda (dx-, dy+)", "W": "izquierda (dx-, dy 0)", "SW": "abajo-izquierda (dx-, dy-)",
                "S": "abajo (dy-)", "SE": "abajo-derecha (dx+, dy-)"}
DIRS8_GEO_EN = {"E": "right (dx+, dy 0)", "NE": "up-right (dx+, dy+)", "N": "up (dy+)", "NW": "up-left (dx-, dy+)",
                "W": "left (dx-, dy 0)", "SW": "down-left (dx-, dy-)", "S": "down (dy-)", "SE": "down-right (dx+, dy-)"}

VARIANTS = {
    "A": {
        "lang": "es",
        "move": {"type": "choice", "instructions": "¿Hacia dónde debe moverse el soldado ahora?",
                 "criteria": {"avanzar": "moverse hacia adelante", "retroceder": "moverse hacia atrás",
                              "quieto": "no moverse"}},
        "jump": {"type": "noul", "instructions": "¿Debe saltar en este instante para esquivar o subir?"},
        "crouch": {"type": "noul", "instructions": "¿Debe agacharse para esquivar un proyectil bajo?"},
        "aim": {"type": "choice", "instructions": "¿Hacia dónde debe apuntar para acertar a la amenaza principal?",
                "criteria": DIRS8_ES},
        "shoot": {"type": "noul", "instructions": "¿Hay un enemigo en la línea de tiro?"},
        "danger": {"type": "score", "instructions": "¿Qué tan peligrosa es la situación?",
                   "criteria": ["Seguro", "Alerta", "Crítico"]},
    },
    "B": {
        "lang": "es",
        "move": {"type": "choice",
                 "instructions": "La misión es avanzar hacia la derecha hasta el jefe. ¿Cómo moverse ahora?",
                 "criteria": {"avanzar": "ir adelante (dx+); lo normal si nada lo impide",
                              "retroceder": "ir atrás solo si algo muy cercano obliga a huir",
                              "quieto": "esperar solo si avanzar lleva directo a una bala"}},
        "jump": {"type": "noul",
                 "instructions": "¿Saltar ahora? Sí si hay hoyo o escalón a menos de 24px adelante, o si una mina o una bala baja (altura menor a 10) viene a menos de 40px, o un soldado viene a menos de 20px."},
        "crouch": {"type": "noul",
                   "instructions": "¿Agacharse ahora? Sí si una bala alta (altura entre 12 y 22) viene a menos de 60px."},
        "aim": {"type": "choice", "instructions": "¿Hacia qué dirección apuntar para pegarle al enemigo más cercano? dy 0 = derecha o izquierda.",
                "criteria": DIRS8_GEO_ES},
        "shoot": {"type": "noul", "instructions": "¿Hay un enemigo en la línea de tiro? Cuenta cualquier enemigo en pantalla (no balas): el arma gira en 8 direcciones."},
        "danger": {"type": "score", "instructions": "¿Qué tan peligrosa es la situación?",
                   "criteria": ["Seguro", "Alerta", "Crítico"]},
    },
    "C": {
        "lang": "en",
        "move": {"type": "choice",
                 "instructions": "The mission is to advance right until the boss. How to move now?",
                 "criteria": {"avanzar": "go ahead (dx+); the default when nothing blocks it",
                              "retroceder": "go back only if something very close forces escaping",
                              "quieto": "wait only if advancing runs straight into a bullet"}},
        "jump": {"type": "noul",
                 "instructions": "Jump now? Yes if a pit or step is less than 24px ahead, or a mine or low bullet (height under 10) is incoming within 40px, or a soldier is incoming within 20px."},
        "crouch": {"type": "noul",
                   "instructions": "Crouch now? Yes if a high bullet (height between 12 and 22) is incoming within 60px."},
        "aim": {"type": "choice", "instructions": "Which direction to aim to hit the nearest enemy? dy 0 = right or left.",
                "criteria": DIRS8_GEO_EN},
        "shoot": {"type": "noul", "instructions": "Is there an enemy in the line of fire? Any on-screen enemy counts (not bullets): the gun turns in 8 directions."},
        "danger": {"type": "score", "instructions": "How dangerous is the situation?",
                   "criteria": ["Safe", "Alert", "Critical"]},
    },
}
VARIANTS["D"] = dict(VARIANTS["B"], lookahead=True)  # B + latency compensation (dead reckoning)
KEYS = ("move", "jump", "crouch", "aim", "shoot", "danger")


def request_body(state: str, variant: str, model: str = "jev-latest") -> dict:
    v = VARIANTS[variant]
    return {"state": state, "model": model, "questions": {k: v[k] for k in KEYS}}
