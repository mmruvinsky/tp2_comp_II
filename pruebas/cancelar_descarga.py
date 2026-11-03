"""Cancela a mitad de descarga y comprueba que no queden tareas ni conexiones.

docker compose run --rm -T -e PYTHONPATH=/srv api python - \
    < pruebas/cancelar_descarga.py
"""
import asyncio

import aiohttp
from aiohttp import web

from app.modelos import Estado, Tarea
from app.pool import PoolDeWorkers
from app.tareas import descargar

URL = 'http://127.0.0.1:9100'
cortes = []
enviando = 0


async def goteo(pedido):
    """Una descarga que no termina sola: 1 KiB cada 0,1 s."""
    global enviando
    respuesta = web.StreamResponse()
    await respuesta.prepare(pedido)
    enviando += 1
    try:
        for _ in range(600):
            await respuesta.write(b'x' * 1024)
            await asyncio.sleep(0.1)
    except (ConnectionResetError, asyncio.CancelledError) as error:
        cortes.append(type(error).__name__)
        raise
    finally:
        enviando -= 1
    return respuesta


async def main():
    aplicacion = web.Application()
    aplicacion.router.add_get('/{x:.*}', goteo)
    corredor = web.AppRunner(
        aplicacion, access_log=None, handler_cancellation=True
    )
    await corredor.setup()
    await web.TCPSite(corredor, '127.0.0.1', 9100).start()

    sesion = aiohttp.ClientSession()
    conector = sesion.connector
    pool = PoolDeWorkers(
        {'descargar': lambda **k: descargar(sesion, **k)}, cantidad=2
    )
    pool.arrancar()

    tarea = Tarea(
        tipo='descargar',
        timeout=300,
        params={'urls': [f'{URL}/{i}' for i in range(5)]},
    )
    pool.encolar(tarea)
    await asyncio.sleep(0.5)
    print(
        f'a mitad: {tarea.estado}, conexiones en uso {len(conector._acquired)}, '
        f'server enviando {enviando}'
    )

    await pool.cancelar(tarea)
    print(
        f'tras DELETE: {tarea.estado} ({tarea.motivo}), '
        f'conexiones en uso {len(conector._acquired)}'
    )
    await asyncio.sleep(0.3)
    print(f'tras 0.3 s: server enviando {enviando}, cortes vistos {len(cortes)}')
    hijas = [
        t for t in asyncio.all_tasks() if '_descargar_una' in repr(t.get_coro())
    ]
    print(f'descargas todavía vivas: {len(hijas)}')
    assert tarea.estado is Estado.CANCELADA
    assert enviando == 0 and not conector._acquired and not hijas

    otra = Tarea(tipo='descargar', timeout=0.3, params={'urls': [f'{URL}/z']})
    pool.encolar(otra)
    await asyncio.sleep(0.8)
    print(
        f'timeout a mitad: {otra.estado} ({otra.motivo}), '
        f'conexiones en uso {len(conector._acquired)}, server enviando {enviando}'
    )
    assert otra.estado is Estado.FALLIDA
    assert enviando == 0 and not conector._acquired

    await pool.cerrar(1)
    await sesion.close()
    await corredor.cleanup()
    print('OK')


asyncio.run(main())
