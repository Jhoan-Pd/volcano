"""mapeos de fuentes por enfermedad y autor del reporte de farmacia

- enfermedades.codigos_sivigila: códigos de evento INS que alimentan casos_oficiales.
- enfermedades.categorias_farmacia: categorías de venta que sirven de señal temprana.
- reportes_farmacia.reportado_por_id: usuario que guardó o editó el reporte.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08 09:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Valores para las enfermedades que ya existan (bases desplegadas con la Fase 1)
MAPEOS = {
    "IRA": (None, "ANTIGRIPALES,ANTIPIRETICOS"),
    "EDA": (None, "SALES_REHIDRATACION"),
    "DENGUE": ("210,220", "REPELENTES,ANTIPIRETICOS"),
    "RESP_CENIZA": (None, "TAPABOCAS,INHALADORES"),
}


def upgrade() -> None:
    with op.batch_alter_table("enfermedades") as batch:
        batch.add_column(sa.Column("codigos_sivigila", sa.String(length=60), nullable=True))
        batch.add_column(sa.Column("categorias_farmacia", sa.String(length=200), nullable=True))

    with op.batch_alter_table("reportes_farmacia") as batch:
        batch.add_column(sa.Column("reportado_por_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_reportes_farmacia_reportado_por_id_usuarios", "usuarios",
            ["reportado_por_id"], ["id"], ondelete="SET NULL",
        )

    enfermedades = sa.table("enfermedades", sa.column("codigo", sa.String),
                            sa.column("codigos_sivigila", sa.String), sa.column("categorias_farmacia", sa.String))
    for codigo, (sivigila, farmacia) in MAPEOS.items():
        op.execute(
            enfermedades.update().where(enfermedades.c.codigo == codigo)
            .values(codigos_sivigila=sivigila, categorias_farmacia=farmacia)
        )


def downgrade() -> None:
    with op.batch_alter_table("reportes_farmacia") as batch:
        batch.drop_constraint("fk_reportes_farmacia_reportado_por_id_usuarios", type_="foreignkey")
        batch.drop_column("reportado_por_id")
    with op.batch_alter_table("enfermedades") as batch:
        batch.drop_column("categorias_farmacia")
        batch.drop_column("codigos_sivigila")
