"""La cola, los workers y el registro de tareas.

Todo corre en el hilo del event loop y entre dos `await` nadie puede interrumpir:
por eso el estado compartido no necesita Lock.
"""
import asyncio
import logging
from functools import partial
from statistics import fmean
from typing import Awaitable, Callable

from app.modelos import Estado, Tarea, ahora

log = logging.getLogger('tp2.pool')

Funcion = Callable[..., Awaitable[dict]]


class PoolDeWorkers:
    def __init__(self, funciones: dict[str, Funcion], cantidad: int) -> None:
        self._funciones = funciones
        self._cantidad = cantidad
        self._cola: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._ocupados = 0
        self.tareas: dict[str, Tarea] = {}
        self.aceptando = True

    def arrancar(self) -> None:
        self._workers = [
            asyncio.create_task(self._worker(), name=f'worker-{i}')
            for i in range(self._cantidad)
        ]

    def encolar(self, tarea: Tarea) -> None:
        self.tareas[tarea.id] = tarea
        self._cola.put_nowait(tarea.id)

    async def cancelar(self, tarea: Tarea) -> None:
        if tarea.estado is Estado.PENDIENTE:
            tarea.estado = Estado.CANCELADA
            tarea.motivo = 'cancelada por el cliente'
            tarea.finalizada = ahora()
        elif tarea.estado is Estado.EJECUTANDO:
            task = tarea.task
            task.cancel()
            # cancel() solo lo pide: el DELETE responde cuando ya terminó de limpiar.
            await asyncio.wait({task})

    def estadisticas(self) -> dict:
        totales = {estado.value: 0 for estado in Estado}
        for tarea in self.tareas.values():
            totales[tarea.estado] += 1
        completadas = [
            t for t in self.tareas.values() if t.estado is Estado.COMPLETADA
        ]
        return {
            'total': len(self.tareas),
            'por_estado': totales,
            'ejecucion_promedio': _promedio(t.ejecucion for t in completadas),
            'espera_promedio': _promedio(t.espera for t in completadas),
            'workers': {
                'total': self._cantidad,
                'vivos': sum(not w.done() for w in self._workers),
                'ocupados': self._ocupados,
            },
            'aceptando': self.aceptando,
        }

    async def _worker(self) -> None:
        while True:
            id_tarea = await self._cola.get()
            try:
                tarea = self.tareas[id_tarea]
                # Si no: la cancelaron en la cola, o el servicio se está apagando
                # y debe quedar `pendiente` en el volcado.
                if tarea.estado is Estado.PENDIENTE and self.aceptando:
                    await self._ejecutar(tarea)
            except Exception:
                log.exception('Error inesperado en el worker')
            finally:
                self._cola.task_done()

    async def _ejecutar(self, tarea: Tarea) -> None:
        tarea.estado = Estado.EJECUTANDO
        tarea.iniciada = ahora()
        self._ocupados += 1
        tarea.task = asyncio.create_task(
            self._correr(tarea), name=f'tarea-{tarea.id}'
        )
        tarea.task.add_done_callback(partial(self._al_terminar, tarea))
        try:
            # wait no relanza el resultado: un error o una cancelación de la
            # tarea no le llegan al worker, como sí pasaría con `await tarea.task`.
            await asyncio.wait({tarea.task})
        finally:
            self._ocupados -= 1

    async def _correr(self, tarea: Tarea) -> dict:
        funcion = self._funciones[tarea.tipo]
        async with asyncio.timeout(tarea.timeout):
            return await funcion(**tarea.params)

    def _al_terminar(self, tarea: Tarea, task: asyncio.Task) -> None:
        """Único lugar donde una tarea en ejecución pasa a un estado final.

        Un done callback corre siempre, incluso si la Task se canceló antes de dar
        su primer paso, y antes de que despierte quien la esté esperando.
        """
        tarea.finalizada = ahora()
        tarea.task = None
        if task.cancelled():
            tarea.estado = Estado.CANCELADA
            tarea.motivo = tarea.motivo or 'cancelada por el cliente'
        elif isinstance(error := task.exception(), TimeoutError):
            tarea.estado = Estado.FALLIDA
            tarea.motivo = f'timeout: superó los {tarea.timeout} s'
        elif error is not None:
            tarea.estado = Estado.FALLIDA
            tarea.motivo = f'{type(error).__name__}: {error}'
        else:
            tarea.estado = Estado.COMPLETADA
            tarea.resultado = task.result()
        log.info('Tarea %s (%s): %s', tarea.id, tarea.tipo, tarea.estado)

    async def drenar(self, limite: float) -> None:
        """Deja de aceptar, espera con límite a las que corren y cancela el resto."""
        self.aceptando = False
        try:
            async with asyncio.timeout(limite):
                await self._cola.join()
        except TimeoutError:
            en_curso = [t for t in self.tareas.values() if t.task]
            log.warning(
                'Venció el límite de %s s: cancelo %d tareas',
                limite, len(en_curso),
            )
            for tarea in en_curso:
                # False si la Task justo terminó: ahí el motivo no corresponde.
                if tarea.task.cancel():
                    tarea.motivo = 'cancelada por apagado: superó el límite de espera'
            await self._cola.join()

    async def cerrar(self, limite: float) -> None:
        await self.drenar(limite)
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)


def _promedio(valores) -> float | None:
    valores = list(valores)
    return fmean(valores) if valores else None
