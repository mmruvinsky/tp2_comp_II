"""La API HTTP y el ciclo de vida del servicio. Se arranca con `python -m app.main`."""
import asyncio
import json
import logging
import signal
from contextlib import asynccontextmanager
from functools import partial

import aiohttp
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError

from app import config
from app.modelos import Estado, Pedido, Tarea
from app.persistencia import reportar_volcado_previo, volcar
from app.pool import PoolDeWorkers
from app.tareas import crear_executor, descargar, esperar, hashear

log = logging.getLogger('tp2.main')


def _al_recibir_senal(app: FastAPI, senal: signal.Signals) -> None:
    if app.state.apagado is not None:
        log.info('%s ignorada: el apagado ya está en marcha', senal.name)
        return
    log.info('%s recibida: empieza el apagado ordenado', senal.name)
    app.state.apagado = asyncio.create_task(_apagar(app))


async def _apagar(app: FastAPI) -> None:
    try:
        await app.state.pool.drenar(config.LIMITE_APAGADO)
    finally:
        app.state.servidor.should_exit = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(reportar_volcado_previo, config.DIR_ESTADO)

    executor = crear_executor()
    sesion = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=config.LIMITE_CONEXIONES),
        timeout=aiohttp.ClientTimeout(total=config.TIMEOUT_URL),
    )
    pool = PoolDeWorkers(
        funciones={
            'descargar': partial(descargar, sesion),
            'hashear': partial(hashear, executor),
            'esperar': esperar,
        },
        cantidad=config.WORKERS,
    )
    pool.arrancar()
    app.state.pool = pool
    app.state.apagado = None

    loop = asyncio.get_running_loop()
    for senal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(senal, _al_recibir_senal, app, senal)

    log.info(
        'Listo: %d workers, hash en modo %s',
        config.WORKERS, config.MODO_HASH,
    )
    yield

    try:
        await pool.cerrar(config.LIMITE_APAGADO)
        await sesion.close()
        if executor is not None:
            # shutdown() bloquea hasta que terminan los procesos.
            await asyncio.to_thread(executor.shutdown)
    finally:
        tareas = [t.a_dict() for t in pool.tareas.values()]
        destino = await asyncio.to_thread(volcar, config.DIR_ESTADO, tareas)
        log.info('Estado volcado en %s (%d tareas)', destino, len(tareas))


app = FastAPI(title='Plataforma de Tareas Distribuidas', lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def pedido_invalido(_: Request, error: RequestValidationError) -> Response:
    # Sin `input`: repetir un Infinity o un surrogate rompería el JSON y daría 500.
    detalle = [
        {clave: e[clave] for clave in ('type', 'loc', 'msg')}
        for e in error.errors()
    ]
    return Response(
        json.dumps({'detail': detalle}),
        status_code=422,
        media_type='application/json',
    )


# Los endpoints son `async def` para correr en el hilo del loop, igual que los
# workers. Con `def`, FastAPI los manda a un threadpool y habría carreras.

@app.post('/tareas', status_code=202)
async def crear_tarea(pedido: Pedido, request: Request) -> dict:
    pool: PoolDeWorkers = request.app.state.pool
    if not pool.aceptando:
        raise HTTPException(503, 'El servicio se está apagando')
    tarea = Tarea(
        tipo=pedido.tipo,
        params=pedido.model_dump(mode='json', exclude={'tipo', 'timeout'}),
        timeout=pedido.timeout or config.TIMEOUT_DEFECTO,
    )
    pool.encolar(tarea)
    return {'id': tarea.id, 'estado': tarea.estado}


@app.get('/tareas')
async def listar_tareas(request: Request, estado: Estado | None = None) -> list:
    return [
        tarea.a_dict(con_resultado=False)
        for tarea in request.app.state.pool.tareas.values()
        if estado is None or tarea.estado is estado
    ]


def _buscar(request: Request, id_tarea: str) -> Tarea:
    tarea = request.app.state.pool.tareas.get(id_tarea)
    if tarea is None:
        raise HTTPException(404, f'No existe la tarea {id_tarea}')
    return tarea


@app.get('/tareas/{id_tarea}')
async def ver_tarea(id_tarea: str, request: Request) -> dict:
    return _buscar(request, id_tarea).a_dict()


@app.delete('/tareas/{id_tarea}')
async def cancelar_tarea(id_tarea: str, request: Request) -> dict:
    tarea = _buscar(request, id_tarea)
    if tarea.estado not in (Estado.PENDIENTE, Estado.EJECUTANDO):
        raise HTTPException(409, f'La tarea ya terminó: {tarea.estado}')
    await request.app.state.pool.cancelar(tarea)
    return tarea.a_dict()


@app.get('/estadisticas')
async def estadisticas(request: Request) -> dict:
    return request.app.state.pool.estadisticas()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    # Server y no uvicorn.run: hace falta el objeto para pedirle should_exit.
    servidor = uvicorn.Server(uvicorn.Config(
        app,
        host=config.HOST,
        port=config.PUERTO,
        access_log=False,
        timeout_graceful_shutdown=2,
    ))
    app.state.servidor = servidor
    servidor.run()


# Sin la guarda, cada proceso de spawn re-importa esto y levanta otro servidor.
if __name__ == '__main__':
    main()
