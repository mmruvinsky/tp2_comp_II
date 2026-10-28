import sys
import time
from collections import deque


# ---------------------------------------------------------------
# Versión 1: intercalar tareas
# ---------------------------------------------------------------

def tarea(nombre, pasos):
    """Una tarea que cede el control en cada paso."""
    for i in range(1, pasos + 1):
        print(f'  [{nombre}] paso {i}/{pasos}')
        yield                      # me suspendo acá y cedo el control
    print(f'  [{nombre}] terminada')


def scheduler(tareas):
    """El event loop más simple posible: una cola y un next() por turno."""
    pendientes = deque(tareas)
    vueltas = 0
    while pendientes:
        t = pendientes.popleft()
        try:
            next(t)                # reanudar hasta el próximo yield
            pendientes.append(t)   # no terminó: vuelve al final de la cola
            vueltas += 1
        except StopIteration:
            # El generador se quedó sin código: la tarea terminó.
            pass
    return vueltas


if __name__ == '__main__':
    print('=== Tres tareas intercaladas en UN solo hilo ===')
    v = scheduler([tarea('A', 3), tarea('B', 2), tarea('C', 4)])
    print(f'\nEl scheduler hizo {v} reanudaciones.')
    print('Sin threads, sin procesos: solo generadores y una cola.')