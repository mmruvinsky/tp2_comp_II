"""Medición 2: latencia de GET /tareas mientras corre un `hashear` pesado.

Se corre una vez por modo, reiniciando el servicio entre cada una:
    MODO_HASH=bloqueante docker compose up -d
    docker compose exec api python mediciones/medir_loop.py
"""
import asyncio
import os
import time

from comun import API, cliente, encargar, esperar_todas, resumen_ms, ver

ITERACIONES = 10_000_000


async def get_tareas(sesion) -> float:
    inicio = time.perf_counter()
    async with sesion.get(f'{API}/tareas') as respuesta:
        await respuesta.read()
    return time.perf_counter() - inicio


async def main() -> None:
    async with cliente() as sesion:
        # Con spawn, los procesos arrancan bajo demanda: que no entre en la medición.
        await asyncio.gather(*(
            encargar(sesion, {
                'tipo': 'hashear', 'texto': 'calentar', 'iteraciones': 300_000,
            })
            for _ in range(os.cpu_count() or 1)
        ))
        await esperar_todas(sesion)

        base = []
        for _ in range(100):
            base.append(await get_tareas(sesion))
            await asyncio.sleep(0.01)

        inicio = time.perf_counter()
        id_tarea = await encargar(sesion, {
            'tipo': 'hashear', 'texto': 'pesado', 'iteraciones': ITERACIONES,
        })
        post = time.perf_counter() - inicio

        durante = []
        while True:
            durante.append(await get_tareas(sesion))
            tarea = await ver(sesion, id_tarea)
            if tarea['estado'] == 'completada':
                break
            await asyncio.sleep(0.01)

    print(f'  hash de {ITERACIONES:,} iteraciones: {tarea["ejecucion"]:.2f} s')
    print(f'  POST /tareas: {post * 1000:.1f} ms')
    print(f'  GET sin carga: {resumen_ms(base)}')
    print(f'  GET con hash : {resumen_ms(durante)}')


asyncio.run(main())
