import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


def hashear(texto, iteraciones):
    h = texto.encode()
    for _ in range(iteraciones):
        h = hashlib.sha256(h).digest()
    return h.hex()


def medir(Executor, n_tareas=4, iteraciones=2_000_000):
    t0 = time.perf_counter()
    with Executor(max_workers=n_tareas) as ex:
        list(ex.map(hashear, ['hola'] * n_tareas, [iteraciones] * n_tareas))
    return time.perf_counter() - t0


if __name__ == '__main__':
    print('Núcleos:', os.cpu_count())
    t0 = time.perf_counter()
    hashear('hola', 2_000_000)
    print(f'1 tarea sola:        {time.perf_counter() - t0:.2f}s')
    print(f'4 tareas, Threads:   {medir(ThreadPoolExecutor):.2f}s')
    print(f'4 tareas, Processes: {medir(ProcessPoolExecutor):.2f}s')
