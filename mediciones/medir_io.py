"""Medición 1: 20 descargas secuenciales contra 20 concurrentes.

Las dos pasan por el sistema real: es una tarea `descargar` con el campo
`concurrente` en False o en True.
"""
import asyncio
from statistics import median

from comun import cliente, encargar, esperar_fin, servidor_lento

REPETICIONES = 5
DEMORA = 0.5


async def medir(sesion, urls: list[str], concurrente: bool) -> float:
    id_tarea = await encargar(sesion, {
        'tipo': 'descargar', 'urls': urls, 'concurrente': concurrente,
    })
    tarea = await esperar_fin(sesion, id_tarea)
    errores = [d for d in tarea['resultado']['descargas'] if 'error' in d]
    assert not errores, errores
    return tarea['ejecucion']


async def comparar(sesion, titulo: str, urls: list[str]) -> None:
    secuencial, concurrente = [], []
    for _ in range(REPETICIONES):
        secuencial.append(await medir(sesion, urls, False))
        concurrente.append(await medir(sesion, urls, True))
    # Mediana y no promedio: en Internet una sola repetición lenta lo distorsiona.
    s, c = median(secuencial), median(concurrente)
    print(f'\n{titulo}')
    print(f'  secuencial : {s:7.3f} s  {[round(x, 3) for x in secuencial]}')
    print(f'  concurrente: {c:7.3f} s  {[round(x, 3) for x in concurrente]}')
    print(f'  speedup    : {s / c:7.2f} x')


async def main() -> None:
    corredor = await servidor_lento(DEMORA, 100 * 1024)
    async with cliente() as sesion:
        await comparar(
            sesion,
            f'Servidor local, {DEMORA} s por URL, 100 KiB ({REPETICIONES} reps)',
            [f'http://127.0.0.1:9000/{i}' for i in range(20)],
        )
        await comparar(
            sesion,
            f'Internet real, https://example.com ({REPETICIONES} reps)',
            [f'https://example.com/?n={i}' for i in range(20)],
        )
    await corredor.cleanup()


asyncio.run(main())
