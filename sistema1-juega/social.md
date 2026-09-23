# Kit de publicación

*Cifras tomadas de results.md.* — @abxda

## X / Twitter

**Tuit** (234 caracteres):

Un modelo de 4B jugando un run-and-gun ochentero sin generar texto: 6 preguntas tipadas por decisión, 408 ms. El mismo tamaño escribiendo JSON: 1041 ms. Avance: 24.9 % vs 10.3 %. El formato está garantizado; la corrección no. — @abxda

**Hilo opcional:**

1/ Sistema 1 = juicio rápido. En vez de pedirle a un LLM que escriba JSON, le pregunto 6 cosas (mover, saltar, agacharse, apuntar, disparar, peligro) y leo la probabilidad de cada opción en una pasada. — @abxda

2/ Resultado: 408 ms por decisión con Qwen3.5-4B local y 24.9 % de avance medio en tiempo real. Juega mal, pero rápido y dentro del esquema: disparar acierta 97 %, saltar apenas tiene 18 % de precisión. — @abxda

3/ Lo más útil: la redacción. Sin decir la meta, el agente se quedó quieto para siempre. Medir la altura desde los pies en vez de desde el arma lo hacía fallar la puntería. Y describir dónde estarán las balas cuando llegue la respuesta subió el avance. — @abxda

4/ Sistema 2 (el mismo tamaño de modelo escribiendo JSON): 1041 ms por decisión, 0.0 % de JSON inválido y 10.3 % de avance. Aquí el JSON no falló; lo que perdió fue el tiempo de reacción. — @abxda

## LinkedIn

¿Qué pasa si a un modelo de lenguaje no le pides texto, sino decisiones?

Construí «Ámbar Reflex», un run-and-gun original de estilo 8 bits, y lo puse a jugar con un servidor local de decisiones tipadas compatible con la API de Jev (Sistema 1): en cada decisión el modelo recibe una descripción compacta del frame y seis preguntas cerradas —mover, saltar, agacharse, apuntar, disparar y peligro— y devuelve probabilidades, sin generar un solo token.

Medí latencia, exactitud contra un oráculo del simulador y calibración. En una RTX 3060, cada decisión tomó 408 ms en promedio y el agente llegó al 24.9 % del nivel; el mismo tamaño de modelo generando JSON tardó 1041 ms y llegó al 10.3 %. Los hallazgos: la redacción de las preguntas pesa más que el modelo, la compensación de latencia importa en tiempo real, y la temperatura genérica no sustituye a calibrar umbrales con datos del dominio.

La lección práctica va más allá de los videojuegos: ruteo, moderación y pipelines de alto volumen pueden correr en local, sin costo por petición y con respuestas que nunca rompen el esquema. Eso sí: el formato está garantizado; la corrección no, y hay que medirla.

Código, datos y video en el repositorio. — @abxda

*(206 palabras)*

## Facebook

Le enseñé a una IA a jugar un videojuego retro… sin dejarla hablar 🎮

En lugar de pedirle que escriba qué hacer, le hago seis preguntas rápidas en cada momento (¿avanzo?, ¿salto?, ¿me agacho?, ¿a dónde apunto?, ¿disparo?, ¿qué tan peligroso está?) y ella responde con probabilidades. Tarda unos 408 ms por decisión y todo corre en mi computadora.

¿Qué tal juega? Honestamente, mal: llegó en promedio al 24.9 % del nivel. Pero decide en 408 ms, y la misma IA escribiendo sus respuestas tardó 1041 ms y llegó menos lejos. Aprendí que cómo le preguntas cambia todo, y que una respuesta bien formada no siempre es una respuesta correcta.

El video muestra en vivo lo que «piensa» en cada decisión. — @abxda

## Hashtags

#IA #LLM #SistemaUno #GameDev #PixelArt #OpenSource #Benchmark #IALocal

## Llamado a la acción

¿Qué decisión de tu trabajo podría ser una pregunta cerrada en vez de un prompt largo? Cuéntame. — @abxda

## Texto alternativo del video

Video en pantalla dividida: a la izquierda, un videojuego de estilo 8 bits donde un soldado de armadura verde azulado avanza y dispara contra soldados, torretas y drones; un abanico de flechas ámbar sale del soldado con opacidad según la probabilidad de cada dirección. A la derecha, una terminal ámbar muestra barras de probabilidad, un medidor de peligro, latencias y un registro de decisiones. Marca de agua @abxda. — @abxda
