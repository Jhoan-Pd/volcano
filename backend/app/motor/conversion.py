"""Traducción entre el dominio (dataclasses, enums, modelos ORM) y los mensajes protobuf.

Mantener las conversiones en un solo módulo evita que el servidor y el cliente repitan
`pb.NivelRiesgo.Value(...)` por todas partes (patrón Mapper).
"""
from app.core.epi import etiqueta
from app.ml.progreso import EventoProgreso
from app.ml.pronostico import PuntoPronostico
from app.models.enums import NivelRiesgo
from app.motor.protos import prediccion_pb2 as pb


def nivel_a_pb(nivel: NivelRiesgo | str | None) -> int:
    return pb.NivelRiesgo.Value(NivelRiesgo(nivel).value) if nivel else pb.NIVEL_DESCONOCIDO


def nivel_de_pb(valor: int) -> str | None:
    return None if valor == pb.NIVEL_DESCONOCIDO else pb.NivelRiesgo.Name(valor)


def punto_a_pb(p: PuntoPronostico) -> pb.PuntoPronostico:
    msg = pb.PuntoPronostico(
        anio=p.anio, semana_epi=p.semana_epi, etiqueta=etiqueta(p.anio, p.semana_epi), horizonte=p.horizonte,
        casos_esperados=p.casos_esperados, limite_inferior=p.limite_inferior, limite_superior=p.limite_superior,
        nivel=nivel_a_pb(p.nivel))
    if p.umbrales is not None:
        msg.umbrales.CopyFrom(pb.Umbrales(amarillo=p.umbrales.amarillo, naranja=p.umbrales.naranja,
                                          rojo=p.umbrales.rojo))
    return msg


def punto_de_pb(p: pb.PuntoPronostico) -> dict:
    return {
        "anio": p.anio, "semana_epi": p.semana_epi, "etiqueta": p.etiqueta, "horizonte": p.horizonte,
        "casos_esperados": p.casos_esperados, "limite_inferior": p.limite_inferior,
        "limite_superior": p.limite_superior, "nivel": nivel_de_pb(p.nivel),
        "umbrales": ({"amarillo": p.umbrales.amarillo, "naranja": p.umbrales.naranja, "rojo": p.umbrales.rojo}
                     if p.HasField("umbrales") else None),
    }


def progreso_a_pb(e: EventoProgreso) -> pb.ProgresoEntrenamiento:
    return pb.ProgresoEntrenamiento(
        etapa=pb.ProgresoEntrenamiento.Etapa.Value(e.etapa.value), mensaje=e.mensaje,
        porcentaje=round(100 * e.avance, 1), enfermedad=e.enfermedad, algoritmo=e.algoritmo,
        mae=e.mae, mae_base=e.mae_base)


def progreso_de_pb(p: pb.ProgresoEntrenamiento) -> dict:
    return {
        "etapa": pb.ProgresoEntrenamiento.Etapa.Name(p.etapa), "mensaje": p.mensaje, "porcentaje": p.porcentaje,
        "enfermedad": p.enfermedad or None, "algoritmo": p.algoritmo or None,
        "mae": p.mae if p.HasField("mae") else None, "mae_base": p.mae_base if p.HasField("mae_base") else None,
    }


def alerta_de_pb(a: pb.Alerta) -> dict:
    return {"id": a.id, "municipio_id": a.municipio_id, "municipio": a.municipio, "enfermedad_id": a.enfermedad_id,
            "enfermedad": a.enfermedad, "semana": a.semana, "nivel": nivel_de_pb(a.nivel), "origen": a.origen,
            "mensaje": a.mensaje}
