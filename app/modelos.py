"""Estados, pedidos HTTP y el registro de una tarea."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Body
from pydantic import BaseModel, Field, HttpUrl, field_validator


class Estado(StrEnum):
    PENDIENTE = 'pendiente'
    EJECUTANDO = 'ejecutando'
    COMPLETADA = 'completada'
    FALLIDA = 'fallida'
    CANCELADA = 'cancelada'


class PedidoBase(BaseModel):
    # allow_inf_nan=False: `Infinity` no existe en JSON y rompería GET y volcado.
    timeout: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class PedidoDescargar(PedidoBase):
    tipo: Literal['descargar']
    urls: list[HttpUrl] = Field(min_length=1)
    concurrente: bool = True


class PedidoHashear(PedidoBase):
    tipo: Literal['hashear']
    texto: str
    iteraciones: int = Field(gt=0)

    @field_validator('texto')
    @classmethod
    def _texto_codificable(cls, texto: str) -> str:
        # JSON permite surrogates sueltos ("\ud800"), pero no se pueden pasar a
        # UTF-8: guardados, harían fallar cada GET que los incluya.
        texto.encode()
        return texto


class PedidoEsperar(PedidoBase):
    tipo: Literal['esperar']
    segundos: float = Field(ge=0, allow_inf_nan=False)


Pedido = Annotated[
    PedidoDescargar | PedidoHashear | PedidoEsperar,
    Body(discriminator='tipo'),
]


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(momento: datetime | None) -> str | None:
    return momento.isoformat() if momento else None


def _segundos(desde: datetime | None, hasta: datetime | None) -> float | None:
    if desde is None or hasta is None:
        return None
    return (hasta - desde).total_seconds()


@dataclass
class Tarea:
    tipo: str
    params: dict
    timeout: float
    id: str = field(default_factory=lambda: uuid4().hex)
    estado: Estado = Estado.PENDIENTE
    resultado: dict | None = None
    motivo: str | None = None
    creada: datetime = field(default_factory=ahora)
    iniciada: datetime | None = None
    finalizada: datetime | None = None
    # Además de servir para cancelarla, evita que el GC la recolecte: el event
    # loop solo guarda referencias débiles a sus Tasks.
    task: asyncio.Task | None = None

    @property
    def espera(self) -> float | None:
        return _segundos(self.creada, self.iniciada)

    @property
    def ejecucion(self) -> float | None:
        return _segundos(self.iniciada, self.finalizada)

    def a_dict(self, con_resultado: bool = True) -> dict:
        datos = {
            'id': self.id,
            'tipo': self.tipo,
            'estado': self.estado,
            'motivo': self.motivo,
            'timeout': self.timeout,
            'params': self.params,
            'creada': _iso(self.creada),
            'iniciada': _iso(self.iniciada),
            'finalizada': _iso(self.finalizada),
            'espera': self.espera,
            'ejecucion': self.ejecucion,
        }
        if con_resultado:
            datos['resultado'] = self.resultado
        return datos
