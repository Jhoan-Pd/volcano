"""Alert origin and closing

- alertas.origen: OBSERVADO (cases already above the threshold) or PREDICHO (the model anticipates it).
- alertas.cerrada_en: when the alert was closed (automatically or by an administrator).
- Index on (municipality, disease, year, week) so alerts are not duplicated.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08 21:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
