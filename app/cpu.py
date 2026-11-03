"""Código que corre en los procesos del executor: se les manda por nombre (pickle)."""
import hashlib
import signal


def hashear_tanda(datos: bytes, iteraciones: int) -> bytes:
    for _ in range(iteraciones):
        datos = hashlib.sha256(datos).digest()
    return datos


def ignorar_sigint() -> None:
    """Ctrl+C le llega a todo el grupo; el apagado lo ordena el proceso principal."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
