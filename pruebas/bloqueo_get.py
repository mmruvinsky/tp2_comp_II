"""¿GET /tareas bloquea el loop, o parte de su latencia es solo transferencia?

Mientras corre, un endpoint rápido sondea: su peor latencia es el bloqueo real.

docker compose exec -T api python - < pruebas/bloqueo_get.py
"""
import asyncio
import sys
import time

sys.path.insert(0, '/srv/mediciones')
from comun import API, CONCURRENCIA_CLIENTE, cliente, encargar  # noqa: E402


async def encargar_varias(sesion, cantidad: int) -> list[str]:
    tope = asyncio.Semaphore(CONCURRENCIA_CLIENTE)

    async def una() -> str:
        async with tope:
            return await encargar(sesion, {'tipo': 'esperar', 'segundos': 1})

    return await asyncio.gather(*(una() for _ in range(cantidad)))


async def latencia(sesion, ruta: str) -> float:
    inicio = time.perf_counter()
    async with sesion.get(f'{API}{ruta}') as respuesta:
        await respuesta.read()
    return time.perf_counter() - inicio


async def main() -> None:
    async with cliente() as sesion:
        registradas = 0
        for meta in (10_000, 100_000):
            ids = await encargar_varias(sesion, meta - registradas)
            registradas = meta
            rapido = f'/tareas/{ids[-1]}'
            for _ in range(3):
                listado = asyncio.create_task(latencia(sesion, '/tareas'))
                await asyncio.sleep(0)
                sondeos = []
                while not listado.done():
                    sondeos.append(await latencia(sesion, rapido))
                print(
                    f'{meta} tareas: GET /tareas {listado.result() * 1000:.0f} ms, '
                    f'GET /tareas/{{id}} durante: {max(sondeos) * 1000:.0f} ms'
                )


asyncio.run(main())
