"""English schema: every table and column renamed, enum values translated, data preserved.

The code moved from Spanish to English identifiers (see docs/glossary.md). Renaming in place would keep
the old Spanish names of every index and constraint, so this migration creates the English tables
with fresh names from the naming convention, copies the data across, and drops the Spanish tables:

    municipios → municipalities          enfermedades → diseases          usuarios → users
    farmacias → pharmacies               reportes_farmacia → pharmacy_reports
    registros_clima → weather_records    tendencias_busqueda → search_trends
    casos_oficiales → official_cases     eventos_volcanicos → volcanic_events
    modelos_entrenados → trained_models  predicciones → predictions      alertas → alerts
    roles: renamed in place (nombre → name, descripcion → description)

Stored enum values are translated too (VERDE → GREEN, CAIDA_CENIZA → ASH_FALL, ANTIGRIPALES → COLD_FLU…)
and so are the JSON documents of models and predictions. Model artifacts are not copied: they were
pickled with the old module paths, so the engine retrains on start-up (the stored predictions keep the
dashboard working meanwhile). Ids are preserved, so links and foreign keys stay valid; on PostgreSQL
the id sequences are moved past the copied rows.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-10 20:00:00
"""
import json
from collections.abc import Iterable, Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RISK = {"VERDE": "GREEN", "AMARILLO": "YELLOW", "NARANJA": "ORANGE", "ROJO": "RED"}
ROLES = {"ADMIN": "ADMIN", "FARMACIA": "PHARMACY", "CIUDADANO": "CITIZEN"}
ORIGIN = {"OBSERVADO": "OBSERVED", "PREDICHO": "PREDICTED"}
EVENT_TYPE = {"BOLETIN": "BULLETIN", "CAIDA_CENIZA": "ASH_FALL", "EMISION_GASES": "GAS_EMISSION", "SISMO": "EARTHQUAKE"}
CATEGORY = {"ANTIGRIPALES": "COLD_FLU", "ANTIPIRETICOS": "ANTIPYRETICS", "SALES_REHIDRATACION": "ORAL_REHYDRATION",
            "INHALADORES": "INHALERS", "TAPABOCAS": "FACE_MASKS", "REPELENTES": "REPELLENTS"}
FEATURES = {"tasa_l0": "rate_l0", "y_anio_ant": "y_prev_year", "sem_sin": "week_sin", "sem_cos": "week_cos",
            "lluvia_l0": "rain_l0", "lluvia_l1": "rain_l1", "lluvia_l2_6": "rain_l2_6", "busq_l0": "search_l0",
            "busq_l1": "search_l1", "busq_var": "search_change", "farm_l0": "pharm_l0", "farm_l1": "pharm_l1",
            "ceniza_l0_1": "ash_l0_1", "ceniza_l2_3": "ash_l2_3", "log_poblacion": "log_population",
            "altitud_km": "altitude_km"}
GROUPS = {"Casos recientes": "recent_cases", "Estacionalidad": "seasonality", "Clima": "weather",
          "Búsquedas en internet": "searches", "Ventas en farmacias": "pharmacy", "Actividad volcánica": "volcano",
          "Municipio": "municipality"}
DIRECTION = {"sube": "up", "baja": "down", "neutral": "neutral"}
ESTIMATORS = {"promedio_movil": "moving_average"}

# old table → new table, in foreign-key order (parents first)
TABLES = [
    ("municipios", "municipalities"), ("enfermedades", "diseases"), ("usuarios", "users"),
    ("farmacias", "pharmacies"), ("reportes_farmacia", "pharmacy_reports"), ("registros_clima", "weather_records"),
    ("tendencias_busqueda", "search_trends"), ("casos_oficiales", "official_cases"),
    ("eventos_volcanicos", "volcanic_events"), ("modelos_entrenados", "trained_models"),
    ("predicciones", "predictions"), ("alertas", "alerts"),
]
TIMESTAMPS = {"created_at": "creado_en", "updated_at": "actualizado_en"}
# new column → SQL expression over the old table (plain old column name in most cases)
COLUMNS: dict[str, dict[str, str]] = {
    "municipalities": {"id": "id", "divipola_code": "codigo_divipola", "name": "nombre", "department": "departamento",
                       "latitude": "latitud", "longitude": "longitud", "altitude_m": "altitud_m",
                       "population": "poblacion", "crater_distance_km": "distancia_crater_km", "active": "activo"},
    "diseases": {"id": "id", "code": "codigo", "name": "nombre", "description": "descripcion",
                 "icd10_code": "codigo_cie10", "recommendations": "recomendaciones",
                 "search_terms": "terminos_busqueda", "sivigila_codes": "codigos_sivigila",
                 "pharmacy_categories": "categorias_farmacia", "color": "color",
                 "yellow_threshold_pct": "umbral_amarillo_pct", "orange_threshold_pct": "umbral_naranja_pct",
                 "red_threshold_pct": "umbral_rojo_pct", "active": "activo"},
    "users": {"id": "id", "name": "nombre", "email": "email", "password_hash": "password_hash", "active": "activo",
              "role_id": "rol_id", "municipality_id": "municipio_id"},
    "pharmacies": {"id": "id", "name": "nombre", "tax_id": "nit", "address": "direccion", "phone": "telefono",
                   "municipality_id": "municipio_id", "user_id": "usuario_id", "latitude": "latitud",
                   "longitude": "longitud", "active": "activa"},
    "pharmacy_reports": {"id": "id", "pharmacy_id": "farmacia_id", "year": "anio", "epi_week": "semana_epi",
                         "category": "categoria", "units": "unidades", "reported_by_id": "reportado_por_id",
                         "is_simulated": "es_simulado"},
    "weather_records": {"id": "id", "municipality_id": "municipio_id", "date": "fecha", "temp_max_c": "temp_max_c",
                        "temp_min_c": "temp_min_c", "temp_mean_c": "temp_media_c",
                        "precipitation_mm": "precipitacion_mm", "relative_humidity_pct": "humedad_relativa_pct",
                        "is_forecast": "es_pronostico", "is_simulated": "es_simulado", "source": "fuente"},
    "search_trends": {"id": "id", "term": "termino", "region": "region", "year": "anio", "epi_week": "semana_epi",
                      "week_start": "fecha_semana", "interest": "indice", "source": "fuente",
                      "is_simulated": "es_simulado"},
    "official_cases": {"id": "id", "municipality_id": "municipio_id", "disease_id": "enfermedad_id", "year": "anio",
                       "epi_week": "semana_epi", "cases": "casos", "source": "fuente", "is_simulated": "es_simulado"},
    "volcanic_events": {"id": "id", "event_type": "tipo", "activity_level": "nivel_actividad",
                        "start_date": "fecha_inicio", "end_date": "fecha_fin", "municipality_id": "municipio_id",
                        "ash_intensity": "intensidad_ceniza", "so2_tons_per_day": "so2_ton_dia",
                        "description": "descripcion", "bulletin_url": "url_boletin", "is_simulated": "es_simulado",
                        "recorded_by_id": "registrado_por_id"},
    "trained_models": {"id": "id", "disease_id": "enfermedad_id", "algorithm": "algoritmo", "version": "version",
                       "trained_at": "fecha_entrenamiento", "baseline_mae": "mae_base", "baseline_rmse": "rmse_base",
                       "model_mae": "mae_modelo", "model_rmse": "rmse_modelo", "sample_count": "n_muestras",
                       "importances": "importancias", "parameters": "parametros", "active": "activo"},
    "predictions": {"id": "id", "model_id": "modelo_id", "municipality_id": "municipio_id",
                    "disease_id": "enfermedad_id", "year": "anio", "epi_week": "semana_epi", "horizon": "horizonte",
                    "expected_cases": "casos_esperados", "lower_bound": "limite_inferior",
                    "upper_bound": "limite_superior", "risk_level": "nivel_riesgo", "explanation": "explicacion"},
    "alerts": {"id": "id", "municipality_id": "municipio_id", "disease_id": "enfermedad_id",
               "prediction_id": "prediccion_id", "year": "anio", "epi_week": "semana_epi",
               "risk_level": "nivel_riesgo", "message": "mensaje", "origin": "origen", "active": "activa",
               "email_notified": "notificada_email", "closed_at": "cerrada_en"},
}
# columns whose stored values are translated with a CASE expression
VALUE_MAPS: dict[tuple[str, str], dict[str, str]] = {
    ("pharmacy_reports", "category"): CATEGORY,
    ("volcanic_events", "event_type"): EVENT_TYPE,
    ("volcanic_events", "activity_level"): RISK,
    ("predictions", "risk_level"): RISK,
    ("alerts", "risk_level"): RISK,
    ("alerts", "origin"): ORIGIN,
}
JSON_TABLES = {"trained_models", "predictions"}


def _case(column: str, mapping: dict[str, str]) -> str:
    whens = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items())
    return f"CASE {column} {whens} ELSE {column} END"


def _categories_sql(column: str) -> str:
    """Comma-separated category list: nested REPLACE calls (no old name contains another one)."""
    expr = column
    for old, new in CATEGORY.items():
        expr = f"REPLACE({expr}, '{old}', '{new}')"
    return expr


def _select_list(table: str) -> tuple[list[str], list[str]]:
    targets, sources = [], []
    for new, old in {**COLUMNS[table], **TIMESTAMPS}.items():
        targets.append(new)
        if (table, new) in VALUE_MAPS:
            sources.append(_case(old, VALUE_MAPS[(table, new)]))
        elif (table, new) == ("diseases", "pharmacy_categories"):
            sources.append(_categories_sql(old))
        else:
            sources.append(old)
    return targets, sources


# ── JSON documents ───────────────────────────────────────────────────────────
def _load(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _importances(doc: dict | None) -> dict | None:
    if not doc:
        return doc
    return {
        "method": doc.get("metodo", ""),
        "groups": {GROUPS.get(k, k): v for k, v in (doc.get("grupos") or {}).items()},
        "features": {FEATURES.get(f, f): {"importance": v.get("importancia"),
                                          "group": GROUPS.get(v.get("grupo"), v.get("grupo"))}
                     for f, v in (doc.get("variables") or {}).items()},
    }


def _parameters(doc: dict | None) -> dict | None:
    if not doc:
        return doc
    metrics = doc.get("metricas") or {}
    return {
        "key": doc.get("clave"),
        "metrics": {
            "summary": {ESTIMATORS.get(k, k): v for k, v in (metrics.get("resumen") or {}).items()},
            "by_horizon": {ESTIMATORS.get(k, k): v for k, v in (metrics.get("por_horizonte") or {}).items()},
            "test_weeks": metrics.get("semanas_prueba"),
        },
        "quantiles": doc.get("cuantiles"),
        "backtest": [{"municipality_id": b["municipio_id"], "year": b["anio"], "epi_week": b["semana_epi"],
                      "observed": b["real"], "predicted": b["predicho"]} for b in doc.get("backtest") or []],
        "hyperparameters": doc.get("hiperparametros"),
    }


def _explanation(doc: dict | None) -> dict | None:
    if not doc:
        return doc
    thresholds = doc.get("umbrales")
    return {
        "method": doc.get("metodo", ""),
        "prediction": doc.get("prediccion"),
        "factors": [{"group": GROUPS.get(f["grupo"], f["grupo"]), "contribution": f["contribucion"],
                     "direction": DIRECTION.get(f["direccion"], f["direccion"]), "message": f.get("mensaje")}
                    for f in doc.get("factores") or []],
        "thresholds": ({"yellow": thresholds["amarillo"], "orange": thresholds["naranja"], "red": thresholds["rojo"]}
                       if thresholds else None),
    }


def _chunks(rows: list[dict], size: int = 1000) -> Iterable[list[dict]]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def _copy_with_json(conn, old: str, new: str) -> None:
    targets, sources = _select_list(new)
    rows = [dict(r) for r in conn.execute(sa.text(
        f"SELECT {', '.join(f'{s} AS {t}' for t, s in zip(targets, sources, strict=True))} FROM {old}")).mappings()]
    if new == "trained_models":
        for r in rows:
            r["importances"] = _importances(_load(r["importances"]))
            r["parameters"] = _parameters(_load(r["parameters"]))
            r["artifact"] = None  # pickled with the old module paths: the engine retrains instead
    else:
        for r in rows:
            r["explanation"] = _explanation(_load(r["explanation"]))
    json_columns = {"importances", "parameters", "explanation"}
    table = sa.table(new, *(sa.column(c, sa.JSON() if c in json_columns else None) for c in rows[0])) if rows else None
    for chunk in _chunks(rows):
        op.bulk_insert(table, chunk)


def _copy_data(conn) -> None:
    for old, new in TABLES:
        if new in JSON_TABLES:
            _copy_with_json(conn, old, new)
            continue
        targets, sources = _select_list(new)
        conn.execute(sa.text(f"INSERT INTO {new} ({', '.join(targets)}) SELECT {', '.join(sources)} FROM {old}"))


def _reset_sequences(conn) -> None:
    if conn.dialect.name != "postgresql":
        return
    for _, new in [*TABLES, ("roles", "roles")]:
        conn.execute(sa.text(f"SELECT setval(pg_get_serial_sequence('{new}', 'id'), "
                             f"COALESCE((SELECT MAX(id) FROM {new}), 0) + 1, false)"))


def _rename_roles(conn) -> None:
    with op.batch_alter_table("roles") as batch:
        batch.drop_constraint("uq_roles_nombre", type_="unique")
        batch.alter_column("nombre", new_column_name="name", existing_type=sa.String(20), existing_nullable=False)
        batch.alter_column("descripcion", new_column_name="description", existing_type=sa.String(200))
    with op.batch_alter_table("roles") as batch:  # a second pass: SQLite rebuilds the table per batch
        batch.create_unique_constraint("uq_roles_name", ["name"])
    conn.execute(sa.text(f"UPDATE roles SET name = {_case('name', ROLES)}"))


def _create_tables() -> None:
    op.create_table('diseases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icd10_code', sa.String(length=40), nullable=True),
    sa.Column('recommendations', sa.Text(), nullable=True),
    sa.Column('search_terms', sa.String(length=300), nullable=True),
    sa.Column('sivigila_codes', sa.String(length=60), nullable=True),
    sa.Column('pharmacy_categories', sa.String(length=200), nullable=True),
    sa.Column('color', sa.String(length=9), nullable=False),
    sa.Column('yellow_threshold_pct', sa.Integer(), nullable=False),
    sa.Column('orange_threshold_pct', sa.Integer(), nullable=False),
    sa.Column('red_threshold_pct', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_diseases')),
    sa.UniqueConstraint('code', name=op.f('uq_diseases_code'))
    )
    op.create_table('municipalities',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('divipola_code', sa.String(length=5), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('department', sa.String(length=60), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('altitude_m', sa.Integer(), nullable=True),
    sa.Column('population', sa.Integer(), nullable=False),
    sa.Column('crater_distance_km', sa.Float(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_municipalities')),
    sa.UniqueConstraint('divipola_code', name=op.f('uq_municipalities_divipola_code'))
    )
    op.create_table('search_trends',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('term', sa.String(length=60), nullable=False),
    sa.Column('region', sa.String(length=10), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('epi_week', sa.Integer(), nullable=False),
    sa.Column('week_start', sa.Date(), nullable=False),
    sa.Column('interest', sa.Float(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_simulated', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_search_trends')),
    sa.UniqueConstraint('term', 'region', 'year', 'epi_week', name=op.f('uq_search_trends_term_region_year_epi_week'))
    )
    with op.batch_alter_table('search_trends', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_search_trends_term'), ['term'], unique=False)

    op.create_table('official_cases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('municipality_id', sa.Integer(), nullable=False),
    sa.Column('disease_id', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('epi_week', sa.Integer(), nullable=False),
    sa.Column('cases', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('is_simulated', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['disease_id'], ['diseases.id'], name=op.f('fk_official_cases_disease_id_diseases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['municipality_id'], ['municipalities.id'], name=op.f('fk_official_cases_municipality_id_municipalities'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_official_cases')),
    sa.UniqueConstraint('municipality_id', 'disease_id', 'year', 'epi_week', name=op.f('uq_official_cases_municipality_id_disease_id_year_epi_week'))
    )
    with op.batch_alter_table('official_cases', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_official_cases_disease_id'), ['disease_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_official_cases_municipality_id'), ['municipality_id'], unique=False)

    op.create_table('trained_models',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('disease_id', sa.Integer(), nullable=False),
    sa.Column('algorithm', sa.String(length=60), nullable=False),
    sa.Column('version', sa.String(length=30), nullable=False),
    sa.Column('trained_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('baseline_mae', sa.Float(), nullable=True),
    sa.Column('baseline_rmse', sa.Float(), nullable=True),
    sa.Column('model_mae', sa.Float(), nullable=True),
    sa.Column('model_rmse', sa.Float(), nullable=True),
    sa.Column('sample_count', sa.Integer(), nullable=True),
    sa.Column('importances', sa.JSON(), nullable=True),
    sa.Column('parameters', sa.JSON(), nullable=True),
    sa.Column('artifact', sa.LargeBinary(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['disease_id'], ['diseases.id'], name=op.f('fk_trained_models_disease_id_diseases'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_trained_models'))
    )
    with op.batch_alter_table('trained_models', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_trained_models_disease_id'), ['disease_id'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=160), nullable=False),
    sa.Column('password_hash', sa.String(length=100), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('municipality_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['municipality_id'], ['municipalities.id'], name=op.f('fk_users_municipality_id_municipalities'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_users_role_id_roles'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('weather_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('municipality_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('temp_max_c', sa.Float(), nullable=True),
    sa.Column('temp_min_c', sa.Float(), nullable=True),
    sa.Column('temp_mean_c', sa.Float(), nullable=True),
    sa.Column('precipitation_mm', sa.Float(), nullable=True),
    sa.Column('relative_humidity_pct', sa.Float(), nullable=True),
    sa.Column('is_forecast', sa.Boolean(), nullable=False),
    sa.Column('is_simulated', sa.Boolean(), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['municipality_id'], ['municipalities.id'], name=op.f('fk_weather_records_municipality_id_municipalities'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_weather_records')),
    sa.UniqueConstraint('municipality_id', 'date', name=op.f('uq_weather_records_municipality_id_date'))
    )
    with op.batch_alter_table('weather_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_weather_records_date'), ['date'], unique=False)
        batch_op.create_index(batch_op.f('ix_weather_records_municipality_id'), ['municipality_id'], unique=False)

    op.create_table('pharmacies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('tax_id', sa.String(length=20), nullable=False),
    sa.Column('address', sa.String(length=200), nullable=True),
    sa.Column('phone', sa.String(length=30), nullable=True),
    sa.Column('municipality_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['municipality_id'], ['municipalities.id'], name=op.f('fk_pharmacies_municipality_id_municipalities'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_pharmacies_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pharmacies')),
    sa.UniqueConstraint('tax_id', name=op.f('uq_pharmacies_tax_id')),
    sa.UniqueConstraint('user_id', name=op.f('uq_pharmacies_user_id'))
    )
    with op.batch_alter_table('pharmacies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pharmacies_municipality_id'), ['municipality_id'], unique=False)

    op.create_table('predictions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('model_id', sa.Integer(), nullable=False),
    sa.Column('municipality_id', sa.Integer(), nullable=False),
    sa.Column('disease_id', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('epi_week', sa.Integer(), nullable=False),
    sa.Column('horizon', sa.Integer(), nullable=False),
    sa.Column('expected_cases', sa.Float(), nullable=False),
    sa.Column('lower_bound', sa.Float(), nullable=False),
    sa.Column('upper_bound', sa.Float(), nullable=False),
    sa.Column('risk_level', sa.String(length=10), nullable=False),
    sa.Column('explanation', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['disease_id'], ['diseases.id'], name=op.f('fk_predictions_disease_id_diseases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['model_id'], ['trained_models.id'], name=op.f('fk_predictions_model_id_trained_models'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['municipality_id'], ['municipalities.id'], name=op.f('fk_predictions_municipality_id_municipalities'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_predictions'))
    )
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_predictions_disease_id'), ['disease_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_predictions_model_id'), ['model_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_predictions_municipality_id'), ['municipality_id'], unique=False)

    op.create_table('volcanic_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('activity_level', sa.String(length=10), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('municipality_id', sa.Integer(), nullable=True),
    sa.Column('ash_intensity', sa.Integer(), nullable=False),
    sa.Column('so2_tons_per_day', sa.Float(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('bulletin_url', sa.String(length=400), nullable=True),
    sa.Column('is_simulated', sa.Boolean(), nullable=False),
    sa.Column('recorded_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['municipality_id'], ['municipalities.id'], name=op.f('fk_volcanic_events_municipality_id_municipalities'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['recorded_by_id'], ['users.id'], name=op.f('fk_volcanic_events_recorded_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_volcanic_events'))
    )
    with op.batch_alter_table('volcanic_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_volcanic_events_municipality_id'), ['municipality_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_volcanic_events_start_date'), ['start_date'], unique=False)

    op.create_table('alerts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('municipality_id', sa.Integer(), nullable=False),
    sa.Column('disease_id', sa.Integer(), nullable=False),
    sa.Column('prediction_id', sa.Integer(), nullable=True),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('epi_week', sa.Integer(), nullable=False),
    sa.Column('risk_level', sa.String(length=10), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('origin', sa.String(length=10), server_default='PREDICTED', nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('email_notified', sa.Boolean(), nullable=False),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['disease_id'], ['diseases.id'], name=op.f('fk_alerts_disease_id_diseases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['municipality_id'], ['municipalities.id'], name=op.f('fk_alerts_municipality_id_municipalities'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id'], name=op.f('fk_alerts_prediction_id_predictions'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_alerts'))
    )
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alerts_disease_id'), ['disease_id'], unique=False)
        batch_op.create_index('ix_alerts_municipality_disease_week', ['municipality_id', 'disease_id', 'year', 'epi_week'], unique=False)
        batch_op.create_index(batch_op.f('ix_alerts_municipality_id'), ['municipality_id'], unique=False)

    op.create_table('pharmacy_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pharmacy_id', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('epi_week', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=30), nullable=False),
    sa.Column('units', sa.Integer(), nullable=False),
    sa.Column('reported_by_id', sa.Integer(), nullable=True),
    sa.Column('is_simulated', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['pharmacy_id'], ['pharmacies.id'], name=op.f('fk_pharmacy_reports_pharmacy_id_pharmacies'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reported_by_id'], ['users.id'], name=op.f('fk_pharmacy_reports_reported_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pharmacy_reports')),
    sa.UniqueConstraint('pharmacy_id', 'year', 'epi_week', 'category', name=op.f('uq_pharmacy_reports_pharmacy_id_year_epi_week_category'))
    )
    with op.batch_alter_table('pharmacy_reports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pharmacy_reports_pharmacy_id'), ['pharmacy_id'], unique=False)


def upgrade() -> None:
    conn = op.get_bind()
    _rename_roles(conn)
    _create_tables()
    _copy_data(conn)
    for old, _ in reversed(TABLES):  # children first, so foreign keys never point to a dropped table
        op.drop_table(old)
    _reset_sequences(conn)


def downgrade() -> None:
    raise NotImplementedError(
        "0004 is a one-way data migration (values and JSON documents were translated). "
        "Restore a database backup taken before upgrading to go back to the Spanish schema.")
