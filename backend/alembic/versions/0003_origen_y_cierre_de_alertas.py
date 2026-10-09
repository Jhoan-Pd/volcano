"""origen y cierre de alertas

- alertas.origen: OBSERVADO (los casos ya superan el umbral) o PREDICHO (lo anticipa el modelo).
- alertas.cerrada_en: cuándo se cerró la alerta (automáticamente o por un administrador).
- Índice por (municipio, enfermedad, año, semana) para no duplicar alertas.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08 21:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("alertas") as batch:
        batch.add_column(sa.Column("origen", sa.String(length=10), nullable=False, server_default="PREDICHO"))
        batch.add_column(sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_alertas_municipio_enfermedad_semana",
                           ["municipio_id", "enfermedad_id", "anio", "semana_epi"])


def downgrade() -> None:
    with op.batch_alter_table("alertas") as batch:
        batch.drop_index("ix_alertas_municipio_enfermedad_semana")
        batch.drop_column("cerrada_en")
        batch.drop_column("origen")
