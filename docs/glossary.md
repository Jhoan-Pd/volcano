# Glossary: domain terms (UI in Spanish ↔ code in English)

The user interface, alert messages, e-mails and PDF reports are written in Spanish because
the people who use the system speak Spanish. Everything else — identifiers, files, REST
routes, gRPC contracts, database tables, logs and comments — is written in English. This
table is the single source of truth for that translation.

## Entities and tables

| Spanish (UI)            | Code / class           | Table               |
|-------------------------|------------------------|---------------------|
| Municipio               | `Municipality`         | `municipalities`    |
| Enfermedad              | `Disease`              | `diseases`          |
| Caso oficial            | `OfficialCase`         | `official_cases`    |
| Registro de clima       | `WeatherRecord`        | `weather_records`   |
| Tendencia de búsqueda   | `SearchTrend`          | `search_trends`     |
| Evento volcánico        | `VolcanicEvent`        | `volcanic_events`   |
| Farmacia                | `Pharmacy`             | `pharmacies`        |
| Reporte de farmacia     | `PharmacyReport`       | `pharmacy_reports`  |
| Modelo entrenado        | `TrainedModel`         | `trained_models`    |
| Predicción              | `Prediction`           | `predictions`       |
| Alerta                  | `Alert`                | `alerts`            |
| Usuario / Rol           | `User` / `Role`        | `users` / `roles`   |

## Columns and fields

| Spanish                     | English                  |
|-----------------------------|--------------------------|
| codigo_divipola             | divipola_code            |
| nombre                      | name                     |
| departamento                | department               |
| latitud / longitud          | latitude / longitude     |
| altitud_m                   | altitude_m               |
| poblacion                   | population               |
| distancia_crater_km         | crater_distance_km       |
| activo / activa             | active                   |
| codigo                      | code                     |
| descripcion                 | description              |
| codigo_cie10                | icd10_code               |
| recomendaciones             | recommendations          |
| terminos_busqueda           | search_terms             |
| codigos_sivigila            | sivigila_codes           |
| categorias_farmacia         | pharmacy_categories      |
| umbral_{amarillo,naranja,rojo}_pct | {yellow,orange,red}_threshold_pct |
| fecha                       | date                     |
| temp_media_c                | temp_mean_c              |
| precipitacion_mm            | precipitation_mm         |
| humedad_relativa_pct        | relative_humidity_pct    |
| es_pronostico / es_simulado | is_forecast / is_simulated |
| fuente                      | source                   |
| termino / indice            | term / interest          |
| anio / semana_epi           | year / epi_week          |
| fecha_semana                | week_start               |
| casos                       | cases                    |
| tipo (evento volcánico)     | event_type               |
| nivel_actividad             | activity_level           |
| fecha_inicio / fecha_fin    | start_date / end_date    |
| intensidad_ceniza           | ash_intensity            |
| so2_ton_dia                 | so2_tons_per_day         |
| url_boletin                 | bulletin_url             |
| registrado_por_id           | recorded_by_id           |
| nit                         | tax_id                   |
| direccion / telefono        | address / phone          |
| categoria / unidades        | category / units         |
| reportado_por_id            | reported_by_id           |
| algoritmo                   | algorithm                |
| fecha_entrenamiento         | trained_at               |
| mae_base / rmse_base        | baseline_mae / baseline_rmse |
| mae_modelo / rmse_modelo    | model_mae / model_rmse   |
| n_muestras                  | sample_count             |
| importancias / parametros   | importances / parameters |
| artefacto                   | artifact                 |
| horizonte                   | horizon                  |
| casos_esperados             | expected_cases           |
| limite_inferior / superior  | lower_bound / upper_bound |
| nivel_riesgo                | risk_level               |
| explicacion                 | explanation              |
| mensaje / origen            | message / origin         |
| notificada_email            | email_notified           |
| cerrada_en                  | closed_at                |
| creado_en / actualizado_en  | created_at / updated_at  |
| etiqueta (semana)           | label (e.g. `2026-S14`)  |

## Enumerations (stored values)

| Enum               | Spanish value         | English value      |
|--------------------|-----------------------|--------------------|
| `RoleName`         | ADMIN, FARMACIA, CIUDADANO | ADMIN, PHARMACY, CITIZEN |
| `RiskLevel`        | VERDE, AMARILLO, NARANJA, ROJO | GREEN, YELLOW, ORANGE, RED |
| `AlertOrigin`      | OBSERVADO, PREDICHO   | OBSERVED, PREDICTED |
| `VolcanoLevel`     | VERDE … ROJO          | GREEN … RED        |
| `VolcanicEventType`| BOLETIN, CAIDA_CENIZA, EMISION_GASES, SISMO | BULLETIN, ASH_FALL, GAS_EMISSION, EARTHQUAKE |
| `ProductCategory`  | ANTIGRIPALES, ANTIPIRETICOS, SALES_REHIDRATACION, INHALADORES, TAPABOCAS, REPELENTES | COLD_FLU, ANTIPYRETICS, ORAL_REHYDRATION, INHALERS, FACE_MASKS, REPELLENTS |

Disease codes (`IRA`, `EDA`, `DENGUE`, `RESP_CENIZA`) are catalogue data defined by the
Colombian health authority, not code, so they keep their official names.

CSV uploads still accept the Spanish category and enum values (`ANTIGRIPALES`, `CAIDA_CENIZA`…):
the importers translate them, so the templates that pharmacies already use keep working.

## Services

| Spanish (old)            | English            | Role                                          |
|--------------------------|--------------------|-----------------------------------------------|
| API REST                 | `gateway`          | Public HTTP API (REST + SSE)                  |
| Motor de predicción gRPC | `engine`           | Models in memory, training, forecasts         |
| —                        | `realtime`         | WebSocket hub: live alerts, simulator, presence |
| —                        | `edge`             | Caddy reverse proxy, the only public port     |
