"""Ayudas compartidas por los scripts de medición.

Corren dentro del contenedor, contra la API en 127.0.0.1:8000:
    docker compose exec api python mediciones/medir_io.py
"""
import asyncio
from datetime import datetime
from statistics import median

import aiohttp
from aiohttp import web

API = 'http://127.0.0.1:8000'
FINALES = {'completada', 'fallida', 'cancelada'}
CONCURRENCIA_CLIENTE = 200


def cliente() -> aiohttp.ClientSession:
    conector = aiohttp.TCPConnector(limit=CONCURRENCIA_CLIENTE)
    return aiohttp.ClientSession(
        connector=conector, timeout=aiohttp.ClientTimeout(total=None)
    )


async def encargar(sesion: aiohttp.ClientSession, cuerpo: dict) -> str:
    async with sesion.post(f'{API}/tareas', json=cuerpo) as respuesta:
        assert respuesta.status == 202, await respuesta.text()
        return (await respuesta.json())['id']


async def ver(sesion: aiohttp.ClientSession, id_tarea: str) -> dict:
    async with sesion.get(f'{API}/tareas/{id_tarea}') as respuesta:
        return await respuesta.json()


async def listar(sesion: aiohttp.ClientSession) -> list[dict]:
    async with sesion.get(f'{API}/tareas') as respuesta:
        return await respuesta.json()


async def esperar_fin(sesion: aiohttp.ClientSession, id_tarea: str) -> dict:
    while True:
        tarea = await ver(sesion, id_tarea)
        if tarea['estado'] in FINALES:
            return tarea
        await asyncio.sleep(0.02)


async def esperar_todas(sesion: aiohttp.ClientSession) -> None:
    while True:
        async with sesion.get(f'{API}/estadisticas') as respuesta:
            por_estado = (await respuesta.json())['por_estado']
        if por_estado['pendiente'] + por_estado['ejecutando'] == 0:
            return
        await asyncio.sleep(0.1)


def percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(int(len(ordenados) * p), len(ordenados) - 1)]


def resumen_ms(valores: list[float]) -> str:
    return (
        f'n={len(valores):<5} mediana={median(valores) * 1000:9.1f} ms  '
        f'p95={percentil(valores, 0.95) * 1000:9.1f} ms  '
        f'max={max(valores) * 1000:9.1f} ms'
    )


def duracion_total(tareas: list[dict]) -> float:
    inicio = min(datetime.fromisoformat(t['creada']) for t in tareas)
    fin = max(datetime.fromisoformat(t['finalizada']) for t in tareas)
    return (fin - inicio).total_seconds()


async def servidor_lento(demora: float, tamano: int, puerto: int = 9000):
    """Servidor de prueba con demora conocida, para no depender de Internet."""
    cuerpo = b'x' * tamano

    async def responder(_pedido: web.Request) -> web.Response:
        await asyncio.sleep(demora)
        return web.Response(body=cuerpo)

    aplicacion = web.Application()
    aplicacion.router.add_get('/{resto:.*}', responder)
    corredor = web.AppRunner(aplicacion, access_log=None)
    await corredor.setup()
    await web.TCPSite(corredor, '127.0.0.1', puerto, backlog=4096).start()
    return corredor
