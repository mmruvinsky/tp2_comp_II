import asyncio
import time

async def tarea_lenta(nombre, veces, espera=0.15):
    for i in range(1, veces + 1):
        print(f'  [{nombre}] {i}/{veces}  (t={time.monotonic() - T0:.2f}s)')
        sum(range(3_000_000))
        await asyncio.sleep(0)
    print(f'  [{nombre}] terminada')

async def main():
    await asyncio.gather(
        tarea_lenta('A', 3),
        tarea_lenta('B', 2),
        tarea_lenta('C', 4),
    )

T0 = time.monotonic()
asyncio.run(main())
print(f'Total: {time.monotonic() - T0:.2f}s')