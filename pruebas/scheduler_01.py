import sys
import time
from collections import deque

def dormir(segundos):
    """No duerme: cede el control diciendo cuándo quiere volver."""
    yield time.monotonic() + segundos


def tarea_lenta(nombre, veces, espera=0.15):
    for i in range(1, veces + 1):
        print(f'  [{nombre}] {i}/{veces}  (t={time.monotonic() - T0:.2f}s)')
        yield from dormir(espera)      # delega: los yield suben al scheduler
    print(f'  [{nombre}] terminada')


def scheduler_con_tiempo(tareas):
    """Igual que el anterior, pero respeta cuándo quiere volver cada tarea."""
    pendientes = deque((0.0, t) for t in tareas)
    while pendientes:
        despertar, t = pendientes.popleft()
        if time.monotonic() < despertar:
            pendientes.append((despertar, t))    # todavía no le toca
            continue
        try:
            cuando = next(t)                     # la tarea dice cuándo volver
            pendientes.append((cuando or 0.0, t))
        except StopIteration:
            pass

if __name__ == '__main__':
    T0 = time.monotonic()
    print('=== Tres tareas que esperan, intercaladas en un hilo ===')
    t0 = time.monotonic()
    scheduler_con_tiempo([
            tarea_lenta('A', 3),
            tarea_lenta('B', 2),
            tarea_lenta('C', 4),
        ])
    print(f'\nTotal: {time.monotonic() - t0:.2f}s')
    print('Las esperas se solapan: no es la suma de todas.')
