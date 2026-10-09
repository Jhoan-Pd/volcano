# Predictor de Brotes de Enfermedades · Pasto y zona del Volcán Galeras

Plataforma web que cruza **datos públicos** (clima, búsquedas de síntomas en internet, reportes de farmacias y actividad del Volcán Galeras) para **anticipar picos** de gripe/IRA, enfermedad diarreica aguda (EDA), dengue y afecciones respiratorias por ceniza en Pasto y cinco municipios vecinos de Nariño, y emitir **alertas tempranas**.

> Proyecto final de *Programación Orientada a la Web*. Es una evolución de **SentinelaIA Nariño** (ETL + XGBoost + Streamlit) hacia una arquitectura web full-stack con API REST, roles, modelo predictivo validado y despliegue en la nube.

| | |
|---|---|
| **Frontend** | React 19 · Vite · TypeScript · TailwindCSS 4 · Recharts · React-Leaflet · React Router · Axios |
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic 2 · Alembic · scikit-learn · pandas · ReportLab |
| **Base de datos** | PostgreSQL (Neon o Supabase, plan gratuito) · SQLite para desarrollo rápido |
| **Automatización** | GitHub Actions: actualización diaria (cron) e integración continua |
| **Despliegue** | Vercel (frontend) · Render (backend) · Neon/Supabase (BD) |

---

## Estado por fases

| Versión | Fase | Contenido | Estado |
|---|---|---|---|
| `v0.5.0` | **1 · Revisión del 50 %** | Estructura, BD con 13 tablas + migraciones + seed, auth JWT con roles, Open-Meteo, CRUD admin, dashboard con gráficas, despliegue | ✅ |
| `v0.8.0` | **2** | Google Trends (pytrends + caché + CSV), SIVIGILA (Socrata), módulo de farmacias, modelo predictivo (promedio móvil vs. Random Forest/Gradient Boosting), semáforo predictivo, carga de CSV | ✅ |
| `v1.0.0` | **3** | Alertas (banner + correo con Resend), mapa Leaflet, explicabilidad, reportes PDF/CSV, cron diario, CI, 76 pruebas, README final | ✅ |

Cada versión es una etiqueta (*tag*) de git. El historial completo de ramas y commits está descrito en [Trazabilidad](#trazabilidad-del-desarrollo-git).

---

## Arquitectura

```
┌──────────── Vercel ────────────┐        ┌──────────────────────── Render ─────────────────────────┐
│ React SPA (Vite + TS)          │ HTTPS  │ FastAPI                                                 │
│  pages → components → api/     │ ─────► │  routers   HTTP, validación de entrada, roles           │
│  Axios + JWT (Bearer)          │  JSON  │  services  reglas de negocio (riesgo, alertas, reportes)│
│  Recharts · Leaflet            │        │  repositories  acceso a datos con SQLAlchemy            │
└────────────────────────────────┘        │  models (ORM) · schemas (Pydantic)                      │
                                          │  ml/       dataset · modelos · entrenador · explicador  │
 GitHub Actions (cron 6:00 a. m.) ──────► │  fuentes/  FuenteDatos (ABC) ── Strategy + Adapter      │
 POST /api/v1/jobs/actualizar-datos       │     ├─ OpenMeteoFuente  → api.open-meteo.com            │
 cabecera X-Cron-Secret                   │     ├─ TrendsFuente     → Google Trends (+ CSV)         │
                                          │     ├─ SivigilaFuente   → datos.gov.co (Socrata)        │
                                          │     └─ FarmaciaFuente   → reportes de farmacias en BD   │
                                          │  notificaciones/  NotificadorCorreo ── ResendNotificador│ ──► Resend
                                          └───────────────────────────┬─────────────────────────────┘
                                                                      ▼
                                                        PostgreSQL (Neon / Supabase)
```

**Flujo de datos:** las fuentes se sincronizan a la BD → `ml/dataset.py` arma una tabla semanal municipio × semana con rezagos → el entrenador compara algoritmos y guarda el mejor en `modelos_entrenados` → se generan `predicciones` de 4 semanas → el servicio de alertas revisa riesgo observado y predicho → el dashboard, los reportes y los correos leen esas tablas.

### Estructura de carpetas

```
sentinela-predictor/
├── .github/workflows/
│   ├── actualizar-datos.yml       # cron diario que llama al backend
│   └── ci.yml                     # pytest + alembic check + build del frontend
├── render.yaml                    # Blueprint de Render (backend)
├── docs/                          # Paso 0, capturas, plantillas CSV, reporte PDF de ejemplo
├── legacy/sentinelaia/            # sistema anterior (ETL + XGBoost + Streamlit), sin cambios, como referencia
├── backend/
│   ├── app/
│   │   ├── main.py                # App FastAPI, CORS, routers, /health, entrenamiento inicial
│   │   ├── core/                  # config (.env), security (bcrypt+JWT), deps (roles), errors, epi (semanas)
│   │   ├── db/                    # Base declarativa, engine y sesión
│   │   ├── models/                # 13 tablas SQLAlchemy + enums
│   │   ├── schemas/               # Pydantic (entrada/salida y validaciones)
│   │   ├── repositories/          # BaseRepository genérico + repos por entidad
│   │   ├── services/              # CRUD, auth, clima, Trends, SIVIGILA, farmacias, predicción,
│   │   │                          #   alertas, importación CSV, reportes, actualización diaria
│   │   ├── fuentes/               # FuenteDatos (abstracta) + 4 adaptadores
│   │   ├── ml/                    # dataset sin fuga, modelos (Strategy), entrenador, explicador
│   │   ├── notificaciones/        # NotificadorCorreo (abstracto) + Resend
│   │   ├── routers/               # auth, usuarios, catálogos, clima, dashboard, datos, farmacia,
│   │   │                          #   modelo, alertas, reportes, jobs
│   │   └── seed/                  # python -m app.seed  (catálogo, generadores, CSV)
│   ├── alembic/versions/          # 0001 esquema · 0002 mapeos de fuentes · 0003 alertas
│   ├── data/trends/               # CSV de respaldo de Google Trends
│   ├── tests/                     # 76 pruebas pytest
│   └── requirements.txt · requirements-dev.txt · .env.example
└── frontend/
    ├── src/
    │   ├── api/                   # cliente Axios (JWT, errores) + servicios + tipos
    │   ├── context/               # AuthContext (sesión/roles) · ThemeContext (claro/oscuro)
    │   ├── components/            # ui, Layout, BannerAlertas, dashboard/*, admin/*
    │   └── pages/                 # Dashboard (público), Login, Farmacia, Admin
    └── vercel.json · .env.example · vite.config.ts
```

---

## Diagrama entidad-relación

```mermaid
erDiagram
    roles ||--o{ usuarios : "tiene"
    municipios |o--o{ usuarios : "reside"
    municipios ||--o{ farmacias : "ubica"
    usuarios |o--o| farmacias : "administra"
    farmacias ||--o{ reportes_farmacia : "envía"
    usuarios |o--o{ reportes_farmacia : "registra"
    municipios ||--o{ registros_clima : "clima diario"
    municipios ||--o{ casos_oficiales : "notifica"
    enfermedades ||--o{ casos_oficiales : "de"
    municipios |o--o{ eventos_volcanicos : "afectado por ceniza"
    usuarios |o--o{ eventos_volcanicos : "registra"
    enfermedades ||--o{ modelos_entrenados : "modela"
    modelos_entrenados ||--o{ predicciones : "genera"
    municipios ||--o{ predicciones : "para"
    enfermedades ||--o{ predicciones : "de"
    predicciones |o--o{ alertas : "origina"
    municipios ||--o{ alertas : "en"
    enfermedades ||--o{ alertas : "de"

    roles { int id PK  string nombre UK  string descripcion }
    usuarios { int id PK  string nombre  string email UK  string password_hash  bool activo  int rol_id FK  int municipio_id FK }
    municipios { int id PK  string codigo_divipola UK  string nombre  float latitud  float longitud  int altitud_m  int poblacion  float distancia_crater_km  bool activo }
    enfermedades { int id PK  string codigo UK  string nombre  string codigo_cie10  text recomendaciones  string terminos_busqueda  string codigos_sivigila  string categorias_farmacia  string color  int umbral_amarillo_pct  int umbral_naranja_pct  int umbral_rojo_pct  bool activo }
    registros_clima { int id PK  int municipio_id FK  date fecha  float temp_max_c  float temp_min_c  float temp_media_c  float precipitacion_mm  float humedad_relativa_pct  bool es_pronostico  bool es_simulado  string fuente }
    tendencias_busqueda { int id PK  string termino  string region  int anio  int semana_epi  date fecha_semana  float indice  string fuente  bool es_simulado }
    farmacias { int id PK  string nombre  string nit UK  int municipio_id FK  int usuario_id FK  bool activa }
    reportes_farmacia { int id PK  int farmacia_id FK  int anio  int semana_epi  string categoria  int unidades  int reportado_por_id FK  bool es_simulado }
    casos_oficiales { int id PK  int municipio_id FK  int enfermedad_id FK  int anio  int semana_epi  int casos  string fuente  bool es_simulado }
    eventos_volcanicos { int id PK  string tipo  string nivel_actividad  date fecha_inicio  date fecha_fin  int municipio_id FK  int intensidad_ceniza  float so2_ton_dia  string url_boletin  bool es_simulado  int registrado_por_id FK }
    modelos_entrenados { int id PK  int enfermedad_id FK  string algoritmo  string version  datetime fecha_entrenamiento  float mae_base  float rmse_base  float mae_modelo  float rmse_modelo  int n_muestras  json importancias  json parametros  bytes artefacto  bool activo }
    predicciones { int id PK  int modelo_id FK  int municipio_id FK  int enfermedad_id FK  int anio  int semana_epi  int horizonte  float casos_esperados  float limite_inferior  float limite_superior  string nivel_riesgo  json explicacion }
    alertas { int id PK  int municipio_id FK  int enfermedad_id FK  int prediccion_id FK  int anio  int semana_epi  string nivel_riesgo  string origen  text mensaje  bool activa  bool notificada_email  datetime cerrada_en }
```

Restricciones únicas importantes: `registros_clima(municipio_id, fecha)`, `casos_oficiales(municipio_id, enfermedad_id, anio, semana_epi)`, `tendencias_busqueda(termino, region, anio, semana_epi)` y `reportes_farmacia(farmacia_id, anio, semana_epi, categoria)`. Con ellas no hay datos duplicados aunque el cron corra dos veces o se suba el mismo CSV.

---

## Cómo funciona la predicción

### 1. Semáforo de riesgo (canal endémico)

Para la semana *S* del año *A* se toman los casos de las semanas *S−1, S, S+1* de los **5 años anteriores** (hasta 15 valores) y se calculan percentiles:

| Nivel | Condición (umbrales por defecto, configurables por enfermedad en el panel) |
|---|---|
| 🟢 Bajo | casos ≤ P50 |
| 🟡 Moderado | P50 < casos ≤ P75 |
| 🟠 Alto | P75 < casos ≤ P90 |
| 🔴 Muy alto | casos > P90 |

El nivel solo sube de verde si hay **al menos 3 casos**, para evitar falsas alarmas con conteos bajos (el dengue en Pasto tiene P90 = 0). El mismo semáforo se aplica a los **casos predichos**.

### 2. Dataset semanal sin fuga de datos (`app/ml/dataset.py`)

Una fila = lo que se sabe **al cerrar la semana *t*** en un municipio. Objetivos: casos de *t+1 … t+4*.

| Grupo | Variables |
|---|---|
| Casos recientes | log(1+casos) con rezagos 0-3, promedios móviles de 4 y 8 semanas, tasa por 100 mil |
| Estacionalidad | casos de las mismas semanas del año anterior, seno/coseno de la semana |
| Clima | temperatura (rezagos 0, 2 y 4-6), lluvia (0, 1 y 2-6), humedad (0, 1) — para dengue importan los rezagos de 2 a 6 semanas |
| Búsquedas en internet | índice de Google Trends de los términos de la enfermedad y su variación frente a 8 semanas |
| Ventas en farmacias | índice de ventas de las categorías asociadas (100 = nivel habitual de cada farmacia) |
| Actividad volcánica | SO₂ del boletín y caída de ceniza en el municipio (rezagos 0-1 y 2-3) |
| Municipio | población y altitud |

Una prueba automática cambia los casos **futuros** y verifica que las variables de la semana *t* no cambien.

### 3. Entrenamiento y comparación (`app/ml/entrenador.py`)

- **Validación temporal**: las últimas 52 semanas son prueba; nunca se mezcla el futuro con el pasado.
- **Estrategia directa**: un modelo por horizonte (1, 2, 3 y 4 semanas).
- Se comparan **promedio móvil de 4 semanas (línea base)**, **Random Forest** y **Gradient Boosting** con **MAE** y **RMSE**. Se elige el de menor MAE y se reentrena con todos los datos.
- **Intervalo del 80 %**: percentiles 10 y 90 de los errores en prueba (escala logarítmica).
- **Importancia global**: por permutación (cuánto empeora el MAE al desordenar cada variable).
- Cada entrenamiento queda en `modelos_entrenados` con fecha, métricas, importancias y el modelo serializado (solo el vigente conserva el binario, para no llenar la BD gratuita).

Resultados con los datos de demostración (MAE en casos por semana y municipio):

| Enfermedad | Línea base | Modelo elegido | Mejora |
|---|---|---|---|
| IRA | 6,00 | Random Forest 5,20 | −13 % |
| EDA | 3,53 | Random Forest 2,99 | −15 % |
| Dengue | 0,39 | Gradient Boosting 0,32 | −18 % |
| Afección por ceniza | 0,82 | Random Forest 0,62 | −25 % |

### 4. Explicabilidad: «¿por qué subió el riesgo?» (`app/ml/explicador.py`)

Para cada predicción se reemplaza un grupo de variables por su **valor típico en ese municipio** (mediana histórica) y se vuelve a predecir. La diferencia es cuántos casos aporta ese grupo (método de **oclusión por grupos**). La interfaz muestra barras hacia arriba y hacia abajo, y frases como *«Las búsquedas de "fiebre, dengue" en Nariño están +40 % respecto a su nivel habitual»*.

### 5. Alertas tempranas (`app/services/alerta_service.py`)

Se registra una alerta cuando el riesgo llega a **alto o muy alto**:

- **Observado**: los casos de la última semana ya superan el P75/P90.
- **Predicho**: el modelo espera ese nivel en alguna de las próximas 4 semanas.

La evaluación es idempotente: no duplica alertas, actualiza el nivel si empeora, cierra solas las que ya no aplican y respeta las que un administrador cerró (solo se reabren si el riesgo sube). Las alertas nuevas aparecen en un **banner** en todas las páginas y se envían por **correo (Resend)** a `ALERTAS_EMAIL_DESTINO` y a cada ciudadano registrado en el municipio afectado (un correo por persona).

---

## Módulos y pantallas

| Pantalla | Rol | Qué hace |
|---|---|---|
| **Dashboard** | público | Semáforo actual y de las próximas 4 semanas por enfermedad, histórico vs. predicción con intervalo, panel «¿por qué?», mapa de riesgo (actual/predicho), estado del Galeras, clima actual y pronóstico de 16 días, recomendaciones, descarga de reportes |
| **Farmacia** | FARMACIA (y ADMIN) | Reporte semanal de ventas por categoría con validaciones, historial, edición y gráfica |
| **Administración** | ADMIN | CRUD de enfermedades (con umbrales), municipios, farmacias, usuarios y eventos volcánicos · Fuentes de datos (sincronizar clima, Trends y SIVIGILA, carga de CSV, estado de tablas) · Modelo (reentrenar, métricas, comparación, importancias, historial) · Alertas (evaluar, cerrar, exportar) |
| **Login / registro** | — | Los ciudadanos se registran con su municipio para recibir alertas |

---

## Instalación local

Requisitos: **Python 3.12+**, **Node.js 22 LTS** (mínimo 20.19) y Git. PostgreSQL es opcional, porque en local se puede usar SQLite.

### 1. Backend (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1          # en CMD: .venv\Scripts\activate.bat
pip install -r requirements-dev.txt
copy .env.example .env              # por defecto usa SQLite: no hay que instalar PostgreSQL
alembic upgrade head                # crea las 13 tablas (3 migraciones)
python -m app.seed --entrenar       # datos de prueba + entrena los 4 modelos + alertas (~1 min)
uvicorn app.main:app --reload       # http://localhost:8000/docs
```

En macOS/Linux, `source .venv/bin/activate` y `cp .env.example .env`.

Opciones del seed: `--sin-red` (no consulta Open-Meteo), `--reset` (borra todo y vuelve a cargar). Si arrancas sin `--entrenar`, el backend entrena en segundo plano al iniciar (`ENTRENAR_AL_INICIO=true`).

### 2. Frontend

```powershell
cd frontend
npm install
copy .env.example .env              # VITE_API_URL=http://localhost:8000
npm run dev                         # http://localhost:5173
```

### 3. Pruebas

```powershell
cd backend
pytest                              # 76 pruebas
```

| Archivo | Qué prueba |
|---|---|
| `test_auth.py` | login, registro, JWT, roles y secreto del cron |
| `test_crud_municipios.py` | CRUD completo y reglas de negocio de catálogos |
| `test_prediccion.py` | dataset sin fuga, línea base, el modelo aprende señales, entrenamiento, intervalos y endpoints |
| `test_alertas.py` | alertas idempotentes, cierre manual y automático, correo (Resend simulado), ciudadanos |
| `test_reportes.py` | CSV con BOM y filtros, PDF |
| `test_importacion.py` | carga de CSV: inserción, actualización, errores por fila, permisos |
| `test_jobs.py` | actualización diaria con fuentes falsas y pasos aislados |
| `test_open_meteo.py`, `test_trends.py`, `test_sivigila.py` | adaptadores de fuentes con HTTP simulado, caché y respaldo CSV |
| `test_farmacia.py`, `test_seed_senales.py`, `test_canal_endemico.py`, `test_migraciones.py` | módulo de farmacias, datos semilla, semáforo, `alembic check` |

### Usuarios de demostración (creados por el seed)

| Rol | Correo | Contraseña (por defecto) |
|---|---|---|
| ADMIN | `admin@predictor.co` | `Admin2026*` (variable `ADMIN_PASSWORD`) |
| FARMACIA | `farmacia@demo.co` | `Demo2026*` (variable `DEMO_PASSWORD`) |
| CIUDADANO | `ciudadano@demo.co` | `Demo2026*` |

> En producción cambia `ADMIN_PASSWORD` y `DEMO_PASSWORD` en Render **antes** del primer arranque.

---

## Variables de entorno

**Backend** (`backend/.env.example`):

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Cadena de conexión. Acepta `postgres://`, `postgresql://` o `sqlite:///` (se normaliza a `postgresql+psycopg://`) |
| `JWT_SECRET` | Secreto para firmar los tokens (32 caracteres o más) |
| `JWT_EXPIRE_MINUTES` | Duración de la sesión (480 = 8 h) |
| `CRON_SECRET` | Secreto que envía GitHub Actions en la cabecera `X-Cron-Secret` |
| `CORS_ORIGINS` | URLs del frontend separadas por coma, sin `/` final |
| `CORS_ORIGIN_REGEX` | Opcional, para los *previews* de Vercel |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DEMO_PASSWORD` | Usuarios que crea el seed |
| `SEED_CLIMA_REAL` | `true`: el seed descarga el clima histórico **real** de Open-Meteo |
| `TRENDS_HABILITADO`, `TRENDS_REGION`, `TRENDS_CSV_DIR` | Google Trends (`CO-NAR`) y carpeta de CSV de respaldo |
| `SOCRATA_URL`, `SOCRATA_APP_TOKEN`, `SIVIGILA_DEPARTAMENTO` | Dataset de SIVIGILA en datos.gov.co; el token es opcional |
| `ENTRENAR_AL_INICIO` | Si no hay modelos, entrenarlos en segundo plano al arrancar |
| `RESEND_API_KEY` | API key de Resend. Sin ella no se envían correos (las alertas igual se ven en el banner) |
| `ALERTAS_EMAIL_DESTINO` | Correos que reciben todas las alertas, separados por coma |
| `ALERTAS_A_CIUDADANOS` | `true`: cada ciudadano registrado recibe las alertas de su municipio |
| `FRONTEND_URL` | URL pública del frontend, para el enlace de los correos |

**Frontend** (`frontend/.env.example`): `VITE_API_URL` es la URL pública del backend, sin `/` final.

---

## Despliegue paso a paso (todo gratis)

### Paso 0 · Subir el repositorio a GitHub

El código vive en <https://github.com/Jhoan-Pd/volcano>. La reforma se integró sobre el historial anterior de SentinelaIA (no se reescribe nada de lo que ya estaba publicado), así que basta con un *push* normal desde la carpeta `sentinela-predictor`:

```powershell
git remote -v                       # origin debe ser https://github.com/Jhoan-Pd/volcano.git
git push origin main
git push origin --all               # sube también las ramas de cada funcionalidad
git push origin --tags              # sube v0.5.0, v0.8.0 y v1.0.0
```

> Si antes desplegaste el portal estático de SentinelaIA en Vercel desde este repositorio, ese proyecto usaba `public/` en la raíz. Ese código ahora está en `legacy/sentinelaia/`: cambia el **Root Directory** del proyecto de Vercel a `frontend` (paso 3) o crea un proyecto nuevo.

### Paso 1 · Base de datos en Neon (recomendado)

1. Entra a <https://neon.tech> → **Sign up** con GitHub → **Create project**.
   - Nombre: `predictor-brotes`. Postgres 16 o 17. Región: **AWS US West 2 (Oregon)**, la misma región donde `render.yaml` crea el backend (menos latencia).
2. En **Dashboard → Connect**, desactiva **Connection pooling** y copia la cadena. Se ve así:
   `postgresql://neondb_owner:XXXX@ep-xxxx.us-west-2.aws.neon.tech/neondb?sslmode=require`
3. Guárdala: es tu `DATABASE_URL`. No hace falta crear tablas, porque Alembic las crea al arrancar el backend.

<details>
<summary><b>Alternativa: Supabase</b></summary>

1. <https://supabase.com> → **New project** → define una contraseña de BD y elige la región `West US (North California)`.
2. **Connect** (botón superior) → **Session pooler** → copia la URI:
   `postgresql://postgres.REF:TU_CLAVE@aws-0-us-west-1.pooler.supabase.com:5432/postgres`
3. **Importante:** no uses la "Direct connection". Es solo IPv6 y Render (plan gratis) no la alcanza.
</details>

### Paso 2 · Backend en Render

1. <https://render.com> → **Sign up** con GitHub.
2. **New → Blueprint** y selecciona tu repositorio. Render lee `render.yaml` y propone el servicio `predictor-brotes-api`.
3. Completa las variables que pide:
   - `DATABASE_URL`: la cadena de Neon del paso 1.
   - `CORS_ORIGINS` y `FRONTEND_URL`: de momento `http://localhost:5173`; las actualizas en el paso 4.
   - `ADMIN_PASSWORD` y `DEMO_PASSWORD`: contraseñas con letras y números.
   - `RESEND_API_KEY` y `ALERTAS_EMAIL_DESTINO`: opcionales (paso 6). Puedes dejarlas vacías.
   - `JWT_SECRET` y `CRON_SECRET` se generan solos.
4. **Apply**. El primer despliegue tarda unos 5 minutos: instala dependencias, corre las migraciones y el seed (con clima real de Open-Meteo). Al arrancar, entrena los modelos en segundo plano (unos minutos en el plan gratis).
5. Comprueba que funciona:
   - `https://predictor-brotes-api.onrender.com/health` debe responder `{"status":"ok","bd":"ok"}`.
   - `https://predictor-brotes-api.onrender.com/docs` muestra Swagger.

> **Sin Blueprint:** New → Web Service → repo → *Root Directory* `backend`, *Build* `pip install -r requirements.txt`, *Start* `alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port $PORT`, *Instance type* Free. Agrega las mismas variables y además `PYTHON_VERSION=3.12.8`.
>
> El plan gratuito **se duerme tras 15 min sin uso**; la primera visita tarda ~50 s en despertar. Antes de presentar, abre `/health` un minuto antes.

### Paso 3 · Frontend en Vercel

1. <https://vercel.com> → **Sign up** con GitHub → **Add New → Project** → importa el repositorio.
2. **Root Directory**: `frontend`. Vercel detecta Vite; `vercel.json` ya define el build y las rutas del SPA.
3. **Environment Variables**: `VITE_API_URL` = `https://predictor-brotes-api.onrender.com`, sin `/` final.
4. **Deploy**. Obtendrás una URL como `https://sentinela-predictor.vercel.app`.

### Paso 4 · Conectar ambos (CORS)

En Render → tu servicio → **Environment**, cambia
`CORS_ORIGINS=https://sentinela-predictor.vercel.app,http://localhost:5173` y `FRONTEND_URL=https://sentinela-predictor.vercel.app`, y guarda. Render se redepliega solo.

Si quieres que funcionen las URLs de *preview*, agrega `CORS_ORIGIN_REGEX=https://sentinela-predictor.*\.vercel\.app`.

### Paso 5 · Actualización diaria con GitHub Actions

1. En Render → **Environment**, copia el valor de `CRON_SECRET`.
2. En GitHub → tu repositorio → **Settings → Secrets and variables → Actions → New repository secret**, crea:
   - `API_URL` = `https://predictor-brotes-api.onrender.com`
   - `CRON_SECRET` = el valor copiado.
3. Pestaña **Actions → Actualizar datos → Run workflow** para probarlo. El resumen muestra cada paso (clima, búsquedas, predicciones, alertas) con ✅ o ❌.

Desde entonces corre solo todos los días a las 6:00 a. m. (hora de Colombia). Los lunes también descarga SIVIGILA y reentrena el modelo. GitHub pausa los cron de repositorios sin actividad durante 60 días; si pasa, basta con reactivarlo en **Actions**.

El workflow **CI** corre las pruebas, `alembic check` y el build del frontend en cada *push*.

### Paso 6 (opcional) · Correos de alerta con Resend

1. <https://resend.com> → **Sign up** → **API Keys → Create API key**.
2. En Render agrega `RESEND_API_KEY` y `ALERTAS_EMAIL_DESTINO` (por ejemplo, tu correo).
3. Con el remitente de prueba `onboarding@resend.dev`, Resend solo entrega al correo de tu cuenta. Para enviar a cualquier ciudadano, verifica un dominio en Resend y cambia `ALERTAS_EMAIL_REMITENTE`.
4. Prueba: **Administración → Alertas → Evaluar ahora**.

### Paso 7 · Verificación final

- [ ] La URL de Vercel muestra el semáforo con «Próximas 4 semanas», la gráfica con la predicción, el panel «¿Por qué?» y el mapa.
- [ ] El banner de alertas aparece si hay riesgo alto, y «Ver detalle» lo explica.
- [ ] **Descargar → Reporte PDF** baja el PDF del municipio.
- [ ] El modo oscuro funciona y el sitio se ve bien en el celular.
- [ ] Con `admin@predictor.co`: **Modelo → Reentrenar** muestra el progreso y luego las métricas MAE/RMSE.
- [ ] Con `farmacia@demo.co`: se puede registrar y editar el reporte de una semana.
- [ ] `ciudadano@demo.co` no ve «Administración», y la API le responde 403 si lo intenta.
- [ ] GitHub Actions → «Actualizar datos» termina en verde.

---

## Datos: qué es real y qué es simulado

| Dato | Origen | Marcado en BD |
|---|---|---|
| Municipios, coordenadas, altitud | Reales (aprox.). Población del sistema anterior (DANE) | — |
| Clima histórico y pronóstico | **Real (Open-Meteo)** si hay internet durante el seed y en cada actualización; si no, simulado | `es_simulado`, `fuente` |
| Búsquedas de síntomas | **Google Trends real** con `pytrends` cuando Google responde; si no, caché en BD y CSV de respaldo. La semilla es simulada | `es_simulado`, `fuente` |
| Casos semanales | Semilla **simulada** (modelo Poisson-Gamma calibrado con las medias IRA/EDA del sistema anterior, dependiente del clima, la ceniza y el SO₂). Se reemplazan con **SIVIGILA real** al sincronizar o con un CSV oficial | `es_simulado`, `fuente` |
| Reportes de farmacias | No existen datos públicos: semilla simulada que se adelanta 1-2 semanas a los casos. Las farmacias registradas reportan las semanas reales | `es_simulado` |
| Nivel del Galeras | Último boletín **real** del SGC (Alerta Amarilla). Histórico semanal, SO₂ y caídas de ceniza estimados | `es_simulado` |

La interfaz muestra la etiqueta **«Datos simulados»** donde corresponde y el panel **Fuentes de datos** muestra el porcentaje simulado de cada tabla. El dataset de SIVIGILA en datos.gov.co se publica con rezago (cubre hasta 2022), por eso la demostración usa la semilla para las semanas recientes.

---

## Decisiones técnicas (para la sustentación)

1. **Se cambia Streamlit por React + FastAPI.** Streamlit no ofrece autenticación multiusuario con roles, sus formularios CRUD son limitados y no expone una API REST para que GitHub Actions dispare actualizaciones. Separar frontend y backend permite desplegar cada parte donde es gratis.
2. **Arquitectura por capas.** `routers` solo traduce HTTP, `services` contiene las reglas, `repositories` encapsula SQLAlchemy y `schemas` valida con Pydantic. Cada capa se prueba por separado.
3. **POO y patrones.**
   - *Strategy/Adapter*: `FuenteDatos` es abstracta y cada fuente adapta su formato externo a filas de nuestras tablas. Igual con `ModeloPronostico` (promedio móvil, Random Forest, Gradient Boosting), `NotificadorCorreo` (Resend o nulo) y los importadores de CSV.
   - *Repository genérico*: `BaseRepository[Model]`.
   - *Template Method*: `CrudService` con los ganchos `validar()` y `antes_de_eliminar()`.
   - *Factory*: `crear_router_crud()` genera los 5 endpoints de cada catálogo.
   - *Inyección de dependencias*: los servicios reciben la fuente o el notificador, así las pruebas usan versiones falsas sin internet.
4. **Seguridad.** Contraseñas con **bcrypt** (12 rondas), **JWT** HS256 con expiración y rol, autorización en el **backend** con `requiere_roles()`, login con mensaje genérico, secreto del cron comparado en tiempo constante, correos individuales a ciudadanos (nadie ve las direcciones de otros).
5. **Errores centralizados.** Todas las respuestas de error usan `{"error": {"codigo", "mensaje", "detalles"}}` en español. Las violaciones de unicidad devuelven 409. En la carga de CSV, las filas con error se informan con su número de línea sin detener la carga.
6. **Migraciones con Alembic.** Tres migraciones versionadas; una prueba y el CI ejecutan `alembic check` para garantizar que los modelos y las migraciones coinciden.
7. **Modelo sin fuga de datos y con línea base.** El XGBoost anterior predecía terciles de `tasa_x_100k` usando `tasa_x_100k` como variable (probabilidad 0,999). Ahora se predicen casos futuros solo con información pasada, con validación temporal, y el modelo debe ganarle a un promedio móvil para tener sentido. Se entrena sobre log(1+casos) para que Pasto (450 000 hab.) y Yacuanquer (13 000) pesen parecido.
8. **Entrenamiento en segundo plano.** En el plan gratis de Render (0,1 CPU) entrenar tarda minutos: la petición responde 202 y el panel consulta el estado cada 3 segundos.
9. **Explicabilidad por oclusión.** Es más fácil de explicar que SHAP y no necesita librerías extra; se combina con frases que describen cada señal.
10. **Fuentes que fallan.** `pytrends` no es oficial: hay caché en BD, CSV de respaldo y pasos aislados en el cron (si falla Trends, el clima y las alertas se actualizan igual).
11. **Semana epidemiológica real.** Se usa `epiweeks` (semanas que inician en domingo, como el INS, con semana 53). El sistema anterior asumía 52 semanas fijas. También se corrigió el DIVIPOLA de La Florida (52299 → **52381**).
12. **Dengue y altitud.** El *Aedes aegypti* casi no sobrevive por encima de ~1.800 m; por eso el riesgo de dengue se concentra en Consacá y Sandoná.
13. **Visualización accesible.** El semáforo siempre combina icono + texto + color; ninguna gráfica tiene dos ejes Y; los colores son tokens con variantes para claro y oscuro; el mapa de Leaflet se carga aparte para no hacer más lento el dashboard.

---

## Trazabilidad del desarrollo (git)

El desarrollo se hizo con ramas por funcionalidad que se integran a `main` con *merge* explícito (`--no-ff`), de modo que el grafo muestra cada funcionalidad como un bloque:

```powershell
git log --oneline --graph --all     # grafo completo
git tag -n                          # versiones por fase
git log v0.5.0..v0.8.0 --oneline    # lo que se hizo en la Fase 2
```

- **Ramas:** `feature/*` (funcionalidades), `fix/*` (correcciones), `chore/*`, `docs/*`, `test/*`.
- **Mensajes:** [Conventional Commits](https://www.conventionalcommits.org/es/) en español: `feat(alcance): …`, `fix`, `test`, `docs`, `build`, `ci`, `style`, `perf`, `chore`.
- **Etiquetas:** `v0.5.0` (Fase 1), `v0.8.0` (Fase 2), `v1.0.0` (Fase 3).
- **Sistema anterior:** el historial de SentinelaIA (abril-septiembre de 2026) se conserva; la reforma se unió a él con un *merge* y el código previo quedó en `legacy/sentinelaia/`.

---

## Capturas

| Dashboard (claro) | Dashboard (oscuro) |
|---|---|
| ![Dashboard claro](docs/capturas/dashboard_claro.png) | ![Dashboard oscuro](docs/capturas/dashboard_oscuro.png) |

| Modelo predictivo (admin) | Alertas (admin) |
|---|---|
| ![Modelo](docs/capturas/admin.png) | ![Alertas](docs/capturas/alertas.png) |

| Fuentes de datos (admin) | Panel de farmacia | Móvil |
|---|---|---|
| ![Fuentes](docs/capturas/fuentes.png) | ![Farmacia](docs/capturas/farmacia.png) | ![Móvil](docs/capturas/movil.png) |

Reporte PDF de ejemplo: [`docs/ejemplo_reporte_pasto.pdf`](docs/ejemplo_reporte_pasto.pdf).

> Las capturas se tomaron en un entorno sin acceso a los mosaicos de OpenStreetMap/CARTO, por eso el mapa aparece sin el fondo de calles; en el navegador el mapa base carga normalmente.

---

## API (resumen)

La documentación interactiva completa está en `/docs` (Swagger) y `/redoc`.

| Método | Ruta | Acceso |
|---|---|---|
| POST · GET | `/api/v1/auth/login` · `/auth/registro` · `/auth/me` | público / autenticado |
| GET | `/api/v1/dashboard/resumen` · `/serie` · `/riesgo-municipios` · `/volcan` · `/prediccion` · `/explicacion` | público |
| GET | `/api/v1/clima/{id}/actual` · `/pronostico` · `/semanal` | público |
| POST | `/api/v1/clima/sincronizar` | ADMIN |
| CRUD | `/api/v1/municipios` · `/enfermedades` · `/eventos-volcanicos` | lectura pública, escritura ADMIN |
| CRUD | `/api/v1/farmacias` · `/usuarios` | ADMIN |
| GET · POST · PUT · DELETE | `/api/v1/farmacia/mi-farmacia` · `/farmacia/reportes[/{anio}/{semana}]` | FARMACIA, ADMIN |
| GET | `/api/v1/farmacia/indice` · `/datos/tendencias` | público |
| POST · GET | `/api/v1/datos/sincronizar/tendencias` · `/sincronizar/sivigila` · `/importar/{tipo}` · `/estado` | ADMIN |
| POST · GET | `/api/v1/modelo/reentrenar` · `/estado` · `/predecir` | ADMIN |
| GET | `/api/v1/modelo/historial` | público |
| GET | `/api/v1/alertas/activas` | público |
| GET · POST · PATCH | `/api/v1/alertas` · `/alertas/evaluar` · `/alertas/{id}/cerrar` | ADMIN |
| GET | `/api/v1/reportes/casos.csv` · `/predicciones.csv` · `/alertas.csv` · `/resumen.pdf` | público |
| POST | `/api/v1/jobs/actualizar-datos` | cabecera `X-Cron-Secret` |
