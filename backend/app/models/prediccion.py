"""Modelos entrenados, predicciones y alertas (se llenan en Fases 2 y 3)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, ahora_utc
from app.models.enums import OrigenAlerta


class ModeloEntrenado(TimestampMixin, Base):
    __tablename__ = "modelos_entrenados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enfermedad_id: Mapped[int] = mapped_column(ForeignKey("enfermedades.id", ondelete="CASCADE"), index=True, nullable=False)
    algoritmo: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha_entrenamiento: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)
    mae_base: Mapped[float | None] = mapped_column(Float)
    rmse_base: Mapped[float | None] = mapped_column(Float)
    mae_modelo: Mapped[float | None] = mapped_column(Float)
    rmse_modelo: Mapped[float | None] = mapped_column(Float)
    n_muestras: Mapped[int | None] = mapped_column(Integer)
    importancias: Mapped[dict | None] = mapped_column(JSON)
    parametros: Mapped[dict | None] = mapped_column(JSON)
    # Modelo serializado (joblib). deferred: no se descarga cada vez que se consulta el modelo
    artefacto: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Prediccion(TimestampMixin, Base):
    __tablename__ = "predicciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    modelo_id: Mapped[int] = mapped_column(ForeignKey("modelos_entrenados.id", ondelete="CASCADE"), index=True, nullable=False)
    municipio_id: Mapped[int] = mapped_column(ForeignKey("municipios.id", ondelete="CASCADE"), index=True, nullable=False)
    enfermedad_id: Mapped[int] = mapped_column(ForeignKey("enfermedades.id", ondelete="CASCADE"), index=True, nullable=False)
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    semana_epi: Mapped[int] = mapped_column(Integer, nullable=False)
    horizonte: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..4 semanas adelante
    casos_esperados: Mapped[float] = mapped_column(Float, nullable=False)
    limite_inferior: Mapped[float] = mapped_column(Float, nullable=False)
    limite_superior: Mapped[float] = mapped_column(Float, nullable=False)
    nivel_riesgo: Mapped[str] = mapped_column(String(10), nullable=False)
    explicacion: Mapped[dict | None] = mapped_column(JSON)


class Alerta(TimestampMixin, Base):
    __tablename__ = "alertas"
    __table_args__ = (Index("ix_alertas_municipio_enfermedad_semana", "municipio_id", "enfermedad_id", "anio",
                            "semana_epi"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    municipio_id: Mapped[int] = mapped_column(ForeignKey("municipios.id", ondelete="CASCADE"), index=True, nullable=False)
    enfermedad_id: Mapped[int] = mapped_column(ForeignKey("enfermedades.id", ondelete="CASCADE"), index=True, nullable=False)
    prediccion_id: Mapped[int | None] = mapped_column(ForeignKey("predicciones.id", ondelete="SET NULL"))
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    semana_epi: Mapped[int] = mapped_column(Integer, nullable=False)
    nivel_riesgo: Mapped[str] = mapped_column(String(10), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    # OBSERVADO: los casos de la última semana ya superan el umbral · PREDICHO: el modelo lo anticipa
    origen: Mapped[str] = mapped_column(String(10), default=OrigenAlerta.PREDICHO.value,
                                        server_default=OrigenAlerta.PREDICHO.value, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notificada_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    municipio: Mapped["Municipio"] = relationship(lazy="joined")  # noqa: F821
    enfermedad: Mapped["Enfermedad"] = relationship(lazy="joined")  # noqa: F821
