"""Configuración del servicio, leída de variables de entorno. Tiempos en segundos."""
import os
from pathlib import Path

WORKERS = int(os.getenv('WORKERS', '10'))

# proceso es el modo normal; hilo y bloqueante existen solo para las mediciones.
MODO_HASH = os.getenv('MODO_HASH', 'proceso')
PROCESOS_HASH = int(os.getenv('PROCESOS_HASH', str(os.cpu_count() or 1)))
TAMANO_TANDA = int(os.getenv('TAMANO_TANDA', '100000'))

TIMEOUT_DEFECTO = float(os.getenv('TIMEOUT_DEFECTO', '300'))
TIMEOUT_URL = float(os.getenv('TIMEOUT_URL', '30'))
LIMITE_CONEXIONES = int(os.getenv('LIMITE_CONEXIONES', '100'))

# Tiene que entrar en el `stop_grace_period` de docker-compose.yml.
LIMITE_APAGADO = float(os.getenv('LIMITE_APAGADO', '8'))

DIR_ESTADO = Path(os.getenv('DIR_ESTADO', 'datos'))

HOST = os.getenv('HOST', '0.0.0.0')
PUERTO = int(os.getenv('PUERTO', '8000'))
