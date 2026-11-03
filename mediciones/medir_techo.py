"""Medición 3: subir las tareas concurrentes hasta que los tiempos se degraden.

Cada tipo de tarea se satura por un motivo distinto, así que se mide uno por vez.
Uso (WORKERS se fija al levantar el servicio):
    docker compose exec api python mediciones/medir_techo.py esperar 1 5 10 20
    docker compose exec api python mediciones/medir_techo.py hashear 1 2 4 8
    docker compose exec api python mediciones/medir_techo.py descargar 50 100 200
    docker compose exec api python mediciones/medir_techo.py avalancha 10000
    docker compose exec api python mediciones/medir_techo.py cola 100000
"""
import asyncio
import os
import sys
import time
from statistics import fmean

from comun import (
    API,
    CONCURRENCIA_CLIENTE,
    cliente,
    duracion_total,
    encargar,
    esperar_todas,
    listar,
    resumen_ms,
    servidor_lento,
)

ITER_HASH = 2_000_000
DEMORA_DESCARGA = 0.5


async def lanzar(sesion, cuerpos: list[dict]) -> tuple[list[str], float]:
    tope = asyncio.Semaphore(CONCURRENCIA_CLIENTE)

    async def uno(cuerpo: dict) -> str:
        async with tope:
            return await encargar(sesion, cuerpo)

    inicio = time.perf_counter()
    ids = await asyncio.gather(*(uno(c) for c in cuerpos))
    return list(ids), time.perf_counter() - inicio


async def barrido(sesion, armar, cantidades: list[int]) -> None:
    print(f'  {"tareas":>7} {"total s":>9} {"tareas/s":>9} '
          f'{"ejecución s":>12} {"espera cola s":>14}')
    for cantidad in cantidades:
        ids, _ = await lanzar(sesion, [armar(i) for i in range(cantidad)])
        await esperar_todas(sesion)
        conjunto = set(ids)
        tareas = [t for t in await listar(sesion) if t['id'] in conjunto]
        malas = [t for t in tareas if t['estado'] != 'completada']
        assert not malas, malas[:3]
        total = duracion_total(tareas)
        print(
            f'  {cantidad:>7} {total:>9.2f} {cantidad / total:>9.1f} '
            f'{fmean(t["ejecucion"] for t in tareas):>12.3f} '
            f'{fmean(t["espera"] for t in tareas):>14.3f}'
        )


async def latencias_get(sesion, ruta: str, veces: int) -> list[float]:
    resultado = []
    for _ in range(veces):
        inicio = time.perf_counter()
        async with sesion.get(f'{API}{ruta}') as respuesta:
            await respuesta.read()
        resultado.append(time.perf_counter() - inicio)
    return resultado


async def imprimir_latencias(sesion, id_tarea: str, veces_listado: int) -> None:
    rutas = [
        (f'/tareas/{id_tarea}', 'GET /tareas/{id}  ', 20),
        ('/estadisticas', 'GET /estadisticas ', 20),
        ('/tareas', 'GET /tareas       ', veces_listado),
    ]
    for ruta, nombre, veces in rutas:
        print(f'  {nombre}: {resumen_ms(await latencias_get(sesion, ruta, veces))}')


async def avalancha(sesion, cantidad: int) -> None:
    ids, encolado = await lanzar(
        sesion, [{'tipo': 'esperar', 'segundos': 1} for _ in range(cantidad)]
    )
    print(f'  {cantidad} POST en {encolado:.2f} s ({cantidad / encolado:.0f} POST/s)')
    await imprimir_latencias(sesion, ids[0], 5)
    await esperar_todas(sesion)
    conjunto = set(ids)
    tareas = [t for t in await listar(sesion) if t['id'] in conjunto]
    print(f'  total {duracion_total(tareas):.2f} s; ejecución promedio '
          f'{fmean(t["ejecucion"] for t in tareas):.3f} s (ideal 1.000 s); '
          f'espera promedio {fmean(t["espera"] for t in tareas):.3f} s')


def memoria_del_servidor() -> str:
    """PID 1 es la API: el script corre en su mismo contenedor."""
    with open('/proc/1/status') as archivo:
        for linea in archivo:
            if linea.startswith('VmRSS'):
                return f'{int(linea.split()[1]) / 1024:.0f} MiB'
    return '?'


async def cola(sesion, cantidad: int) -> None:
    print(f'  memoria antes: {memoria_del_servidor()}')
    ids, encolado = await lanzar(
        sesion, [{'tipo': 'esperar', 'segundos': 1} for _ in range(cantidad)]
    )
    print(f'  {cantidad} POST en {encolado:.2f} s ({cantidad / encolado:.0f} POST/s)')
    print(f'  memoria después: {memoria_del_servidor()}')
    await imprimir_latencias(sesion, ids[-1], 3)


async def calentar_pool(sesion) -> None:
    await lanzar(sesion, [
        {'tipo': 'hashear', 'texto': 'calentar', 'iteraciones': 300_000}
        for _ in range(os.cpu_count() or 1)
    ])
    await esperar_todas(sesion)


async def main() -> None:
    modo, *resto = sys.argv[1:]
    cantidades = [int(x) for x in resto]
    async with cliente() as sesion:
        if modo == 'esperar':
            await barrido(
                sesion, lambda _: {'tipo': 'esperar', 'segundos': 1}, cantidades
            )
        elif modo == 'hashear':
            print(f'  ({os.cpu_count()} núcleos, {ITER_HASH:,} iteraciones c/u)')
            await calentar_pool(sesion)
            await barrido(sesion, lambda i: {
                'tipo': 'hashear', 'texto': f't{i}', 'iteraciones': ITER_HASH,
            }, cantidades)
        elif modo == 'descargar':
            print(f'  (una URL por tarea, {DEMORA_DESCARGA} s cada una)')
            corredor = await servidor_lento(DEMORA_DESCARGA, 10 * 1024)
            await barrido(sesion, lambda i: {
                'tipo': 'descargar', 'urls': [f'http://127.0.0.1:9000/{i}'],
            }, cantidades)
            await corredor.cleanup()
        elif modo == 'avalancha':
            await avalancha(sesion, cantidades[0])
        elif modo == 'cola':
            await cola(sesion, cantidades[0])
        else:
            raise SystemExit(f'Modo desconocido: {modo}')


asyncio.run(main())
