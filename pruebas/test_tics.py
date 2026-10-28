import asyncio
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


def hashear(texto, iteraciones):
    h = texto.encode()
    for _ in range(iteraciones):
        h = hashlib.sha256(h).digest()
    return h.hex()


async def tics(duracion):
    """Simula la API: quiere correr cada 10 ms. Mide cuánto se atrasa."""
    peor, cantidad = 0.0, 0
    fin = time.perf_counter() + duracion
    while time.perf_counter() < fin:
        t0 = time.perf_counter()
        await asyncio.sleep(0.01)
        peor = max(peor, time.perf_counter() - t0 - 0.01)
        cantidad += 1
    return peor, cantidad


async def sin_executor():
    await asyncio.sleep(0.1)
    hashear('hola', 3_000_000)              # corre EN el hilo del loop


async def con_executor(ex):
    await asyncio.sleep(0.1)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(ex, hashear, 'hola', 3_000_000)


async def main():
    peor, n = (await asyncio.gather(tics(2), sin_executor()))[0]
    print(f'Sin executor: peor atraso {peor * 1000:7.1f} ms, {n} tics')
    for nombre, Executor in [('Thread', ThreadPoolExecutor),
                             ('Process', ProcessPoolExecutor)]:
        with Executor(max_workers=1) as ex:
            peor, n = (await asyncio.gather(tics(2), con_executor(ex)))[0]
        print(f'{nombre:12}: peor atraso {peor * 1000:7.1f} ms, {n} tics')


if __name__ == '__main__':
    asyncio.run(main())
