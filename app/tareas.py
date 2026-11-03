"""Los tres tipos de tarea. Cada uno es una corrutina que devuelve un dict."""
import asyncio
import multiprocessing
import time
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor

import aiohttp

from app import config
from app.cpu import hashear_tanda, ignorar_sigint

TAMANO_BLOQUE = 64 * 1024


async def esperar(segundos: float) -> dict:
    await asyncio.sleep(segundos)
    return {'dormido': segundos}


async def _descargar_una(sesion: aiohttp.ClientSession, url: str) -> dict:
    inicio = time.perf_counter()
    try:
        async with sesion.get(url) as respuesta:
            tamano = 0
            async for bloque in respuesta.content.iter_chunked(TAMANO_BLOQUE):
                tamano += len(bloque)
        return {
            'url': url,
            'estado': respuesta.status,
            'tamano': tamano,
            'segundos': time.perf_counter() - inicio,
        }
    except Exception as error:
        # CancelledError no entra acá: hereda de BaseException, no de Exception.
        return {
            'url': url,
            'error': f'{type(error).__name__}: {error}',
            'segundos': time.perf_counter() - inicio,
        }


async def descargar(
    sesion: aiohttp.ClientSession, urls: list[str], concurrente: bool = True
) -> dict:
    if concurrente:
        descargas = await asyncio.gather(
            *(_descargar_una(sesion, url) for url in urls)
        )
    else:
        descargas = [await _descargar_una(sesion, url) for url in urls]
    return {'descargas': descargas}


async def hashear(
    executor: Executor | None, texto: str, iteraciones: int
) -> dict:
    datos = texto.encode()

    if executor is None:
        # MODO_HASH=bloqueante: bug a propósito, para la medición 2.
        datos = hashear_tanda(datos, iteraciones)
        return {'hash': datos.hex(), 'iteraciones': iteraciones}

    loop = asyncio.get_running_loop()
    restantes = iteraciones
    while restantes > 0:
        tanda = min(config.TAMANO_TANDA, restantes)
        # La tanda en curso no se puede interrumpir: la cancelación corta entre tandas.
        datos = await loop.run_in_executor(
            executor, hashear_tanda, datos, tanda
        )
        restantes -= tanda
    return {'hash': datos.hex(), 'iteraciones': iteraciones}


def crear_executor() -> Executor | None:
    if config.MODO_HASH == 'proceso':
        return ProcessPoolExecutor(
            max_workers=config.PROCESOS_HASH,
            # fork copiaría un proceso con el loop e hilos ya andando.
            mp_context=multiprocessing.get_context('spawn'),
            initializer=ignorar_sigint,
        )
    if config.MODO_HASH == 'hilo':
        return ThreadPoolExecutor(max_workers=config.PROCESOS_HASH)
    if config.MODO_HASH == 'bloqueante':
        return None
    raise ValueError(f'MODO_HASH desconocido: {config.MODO_HASH!r}')
