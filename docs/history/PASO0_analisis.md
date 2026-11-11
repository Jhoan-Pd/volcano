# Paso 0 · Análisis del sistema anterior y plan de reforma

Sistema analizado: carpeta `Final/` y repositorio `BI_Health_Nari-o` (SentinelaIA Nariño). Lo componen un ETL en Python (pandas + Selenium), un modelo XGBoost clasificador, un dashboard en Streamlit y un portal HTML estático en Vercel. Los datos son archivos CSV con 6 municipios de la zona del Galeras e IRA/EDA de 2020 a 2024.

## Qué se reutiliza, modifica, elimina y agrega

| Categoría | Elemento | Justificación |
|---|---|---|
| **Se reutiliza tal cual** | Los 6 municipios con su población DANE y la distancia al cráter | Base de la tabla `municipios` |
| | Las series semanales IRA/EDA 2020-2024 | Calibran la semilla de `casos_oficiales`: medias y estacionalidad por municipio |
| | La serie de SO₂ del Galeras (`galeras_actividad.csv`) | Semilla de `eventos_volcanicos` (`app/seed/data/galeras_so2_semanal.csv`) |
| | La consulta Socrata a datos.gov.co (`download_data.py`) | Base de `SivigilaFuente` (Fase 2) |
| | La idea del canal endémico y la paleta volcánica (#D4873A) | Servicio de riesgo y tema visual |
| **Se modifica** | Modelo XGBoost con **fuga de datos**: el objetivo eran terciles de `tasa_x_100k`, que también era variable de entrada (probabilidad media 0,999) | Regresión de casos futuros con rezagos y validación temporal, comparada contra una línea base |
| | DIVIPOLA de La Florida: 52299 | Se corrige a 52381 |
| | Semanas 1-52 fijas | Calendario epidemiológico real con semana 53 (`epiweeks`) |
| | Clima "IDEAM_estimado" (simulado) | Open-Meteo real: histórico y pronóstico de 16 días |
| | Scripts sueltos con rutas relativas | Clases `FuenteDatos` (Strategy/Adapter) |
| | CSV como almacenamiento | PostgreSQL con migraciones Alembic |
| | Nivel volcánico verde/naranja en el CSV | El SGC mantuvo al Galeras en Alerta Amarilla; se registra así |
| **Se elimina** (del sistema nuevo; el código original se conserva en `legacy/sentinelaia/`) | Streamlit `app.py` | No tiene JWT ni roles, sus formularios CRUD son limitados, no expone API REST y no corre en Vercel |
| | Scraping con Selenium del portal INS y los scripts `inspect_*`, `test_selenium.py`, `temp_debug_dane.py`, `list_ins_event_options.py`, `discover_ins_links.py` | Frágiles y no corren en Render; la API Socrata los reemplaza |
| | Archivos `.pkl` sueltos | Los modelos se guardan en la tabla `modelos_entrenados` con fecha y métricas |
| | Duplicados en la raíz de `Final/` y el Power BI embebido | Desorden y dependencia de licencia |
| **Es nuevo** | API FastAPI por capas, JWT con 3 roles, 13 tablas, Alembic y seed | |
| | SPA React + TypeScript + Tailwind con modo claro/oscuro | |
| | Enfermedades nuevas: dengue y afección respiratoria por ceniza | |
| | Fuentes nuevas: Google Trends y reportes de farmacias | |
| | Alertas, mapa, explicabilidad, reportes PDF/CSV, cron en GitHub Actions y pruebas pytest | |

## Arquitectura final

Ver el diagrama y la estructura en el [README](../README.md#arquitectura).
