"""Volcado del estado a JSON. Escribe en disco: se llama con asyncio.to_thread."""
import json
import logging
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

log = logging.getLogger('tp2.persistencia')


def volcar(carpeta: Path, tareas: list[dict]) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime('%Y%m%d_%H%M%S')
    destino = carpeta / f'estado_{marca}.json'
    # os.replace es atómico: un corte no deja un volcado por la mitad.
    temporal = destino.with_suffix('.tmp')
    temporal.write_text(json.dumps({'tareas': tareas}, indent=2))
    os.replace(temporal, destino)
    return destino


def reportar_volcado_previo(carpeta: Path) -> None:
    volcados = sorted(carpeta.glob('estado_*.json'))
    if not volcados:
        log.info('No hay volcados previos en %s', carpeta)
        return
    ultimo = volcados[-1]
    try:
        tareas = json.loads(ultimo.read_text())['tareas']
    except (OSError, ValueError, KeyError) as error:
        log.warning('Volcado previo %s ilegible: %s', ultimo, error)
        return
    por_estado = Counter(tarea['estado'] for tarea in tareas)
    log.info(
        'Volcado previo: %s (%d archivos en total), %d tareas: %s',
        ultimo, len(volcados), len(tareas), dict(por_estado),
    )
