# Notas para el README

## Experimento: I/O-bound vs CPU-bound en el event loop

Archivo: `pruebas/test_asyn.py`. Tres corrutinas (A: 3 pasos, B: 2, C: 4 → 9 pasos
en total) lanzadas con `asyncio.gather`.

| Versión | Qué hace cada paso | Orden observado | Total |
|---|---|---|---|
| I/O simulado | `await asyncio.sleep(0.15)` | intercaladas (A B C …) | **_a medir_** (esperado ≈ 0.6 s) |
| CPU sin `await` | `sum(range(3_000_000))` | secuencial (A A A → B B → C C C C) | 0.18 s |
| CPU + `await asyncio.sleep(0)` | `sum(...)` y después `sleep(0)` | intercaladas (A B C …) | 0.18 s |

### Qué muestra

- **I/O-bound:** mientras una corrutina espera en el `await`, el hilo del loop queda
  libre y corre las otras. El total se acerca a lo que tarda la tarea más larga
  (C: 4 × 0.15 s), no a la suma de todas (9 × 0.15 s).
- **CPU-bound sin `await`:** la corrutina nunca le devuelve el control al loop, así
  que corren una detrás de otra. El total es la suma: 9 × ~0.02 s ≈ 0.18 s.
- **CPU-bound con `sleep(0)`:** se vuelven a intercalar, pero **el total no baja**.
  Hay un solo hilo y trabaja un solo núcleo: turnarse no es paralelizar. Lo único
  que mejora es que otra corrutina (por ejemplo, un `GET /tareas`) espera como
  máximo un paso (~0.02 s) en lugar de la tarea entera.

### Concepto (clase 18)

Concurrencia **cooperativa**: el loop no puede quitarle el turno a una corrutina.
Solo cambia de corrutina cuando la que está corriendo hace `await`, igual que el
`yield` del scheduler casero (`pruebas/scheduler.py`). Por eso un cálculo
CPU-bound dentro del loop congela todo, la API incluida. Por eso `hashear` va a
un executor.

> Esto **no** reemplaza la medición obligatoria 1 (20 descargas secuenciales vs
> concurrentes) ni la 2 (latencia de `GET /tareas` con y sin executor). Es la
> intuición previa a esas mediciones.

## Experimento: GIL, ThreadPoolExecutor vs ProcessPoolExecutor

Archivo: `pruebas/test_gil.py`. Hash SHA-256 iterado 2.000.000 de veces, 4 tareas
a la vez. Máquina con 12 núcleos.

| Caso | Tiempo | En múltiplos de T |
|---|---|---|
| 1 tarea sola (T) | 0.65 s | 1 T |
| 4 tareas, `ThreadPoolExecutor` | 2.57 s | ≈ 4 T |
| 4 tareas, `ProcessPoolExecutor` | 0.73 s | ≈ 1.1 T |

### Qué muestra (clases 10 y 22)

- **Threads:** el GIL deja que un solo hilo a la vez ejecute bytecode de Python.
  Los 4 hilos son **concurrentes** (se turnan) pero no **paralelos**, así que el
  total es la suma: ≈ 4 T.
- **Processes:** cada proceso tiene su propio intérprete y su propio GIL, así que
  no compiten entre sí y corren en paralelo en núcleos distintos: ≈ T.
- El 0.08 s extra de Processes es el costo de crear los procesos y de serializar
  (pickle) argumentos y resultados. El paralelismo lo compensa.

**Decisión para `hashear`: `ProcessPoolExecutor`.**

### ¿Y si llega una sola tarea `hashear`?

Aunque llegue una sola tarea `hashear`, prefiero `ProcessPoolExecutor` porque con
threads hay un solo GIL en el proceso, que se reparten el hilo del executor (que
está hasheando) y el hilo del event loop (que es el que atiende las requests
HTTP). El hash ocupa el GIL la mayor parte del tiempo y el loop tiene que esperar
a que lo suelte, aunque haya núcleos libres. Con procesos hay dos: el principal,
con el event loop, y el del executor, con el hash. Cada uno tiene su propio GIL,
así que el loop no compite con nadie y pueden correr en núcleos distintos.

### Pendiente

- Medir con `pruebas/test_tics.py` cuánto se atrasa el loop en cada caso (sin
  executor / Thread / Process).
