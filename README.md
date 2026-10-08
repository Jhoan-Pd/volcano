# Predictor de Brotes de Enfermedades · Pasto y zona del Volcán Galeras

Plataforma web que cruza **datos públicos** (clima, búsquedas de síntomas en internet, reportes de farmacias y actividad del Volcán Galeras) para **anticipar picos** de gripe/IRA, enfermedad diarreica aguda (EDA), dengue y afecciones respiratorias por ceniza en Pasto y cinco municipios vecinos de Nariño, y emitir **alertas tempranas**.

> Proyecto final de *Programación Orientada a la Web*. Es una evolución de **SentinelaIA Nariño** (ETL + XGBoost + Streamlit) hacia una arquitectura web full-stack con API REST, roles y despliegue en la nube.

| | |
|---|---|
| **Frontend** | React 19 · Vite · TypeScript · TailwindCSS 4 · Recharts · React Router · Axios |
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic 2 · Alembic · pandas/numpy (scikit-learn en la Fase 2) |
| **Base de datos** | PostgreSQL (Neon o Supabase, plan gratuito) · SQLite para desarrollo rápido |
| **Despliegue** | Vercel (frontend) · Render (backend) · Neon/Supabase (BD) · GitHub Actions (cron, Fase 3) |

---

## Estado por fases

| Fase | Contenido | Estado |
|---|---|---|
| **1 · Revisión del 50 %** | Estructura, BD con 13 tablas + migraciones + seed, auth JWT con roles, Open-Meteo, CRUD admin, dashboard con gráficas, despliegue | ✅ Lista |
| 2 | Google Trends (pytrends + caché + CSV), SIVIGILA (Socrata), módulo farmacias, modelo predictivo (promedio móvil vs. RF/GB) y semáforo predictivo | ⏳ |
| 3 | Alertas (+ correo Resend), mapa Leaflet, explicabilidad, reportes PDF/CSV, cron diario, más tests, README final | ⏳ |

---

## Arquitectura

```
┌──────────── Vercel ────────────┐        ┌──────────────────────── Render ─────────────────────────┐
│ React SPA (Vite + TS)          │ HTTPS  │ FastAPI                                                 │
│  pages → components → api/     │ ─────► │  routers  (HTTP, validación de entrada, roles)          │
│  Axios + JWT (Bearer)          │  JSON  │  services (reglas de negocio, canal endémico)           │
└────────────────────────────────┘        │  repositories (acceso a datos con SQLAlchemy)          │
                                          │  models (ORM) · schemas (Pydantic)                      │
       GitHub Actions (cron diario) ────► │  fuentes/ FuenteDatos (ABC) ── Strategy + Adapter       │
       POST /api/v1/jobs/actualizar-datos │     ├─ OpenMeteoFuente  → api.open-meteo.com           │
       cabecera X-Cron-Secret             │     ├─ TrendsFuente     → Google Trends     (Fase 2)   │
                                          │     ├─ SivigilaFuente   → datos.gov.co      (Fase 2)   │
                                          │     └─ FarmaciaFuente   → reportes en BD    (Fase 2)   │
                                          └───────────────────────────┬─────────────────────────────┘
                                                                      ▼
                                                        PostgreSQL (Neon / Supabase)
```

### Estructura de carpetas

```
sentinela-predictor/
├── render.yaml                    # Blueprint de Render (backend)
├── backend/
│   ├── app/
│   │   ├── main.py                # App FastAPI, CORS, routers, /health
│   │   ├── core/                  # config (.env), security (bcrypt+JWT), deps (roles), errors, epi (semanas)
│   │   ├── db/                    # Base declarativa, engine y sesión
│   │   ├── models/                # 13 tablas SQLAlchemy + enums
│   │   ├── schemas/               # Pydantic (entrada/salida y validaciones)
│   │   ├── repositories/          # BaseRepository genérico + repos por entidad
│   │   ├── services/              # CrudService genérico, usuarios/auth, catálogos, clima, riesgo, dashboard
│   │   ├── fuentes/               # FuenteDatos (abstracta) + OpenMeteoFuente
│   │   ├── routers/               # auth, usuarios, catálogos (fábrica CRUD), clima, dashboard, jobs
│   │   └── seed/                  # python -m app.seed  (catálogo, generador, datos CSV)
│   ├── alembic/                   # migraciones (0001: esquema inicial de 13 tablas)
│   ├── tests/                     # pytest: auth, CRUD, canal endémico, Open-Meteo, migraciones
│   ├── requirements.txt · requirements-dev.txt · .env.example · .python-version
└── frontend/
    ├── src/
    │   ├── api/                   # cliente Axios (JWT, errores) + servicios + tipos
    │   ├── context/               # AuthContext (sesión/roles) · ThemeContext (claro/oscuro)
    │   ├── components/            # ui, Layout, RutaProtegida, dashboard/*, admin/CrudTable
    │   └── pages/                 # Dashboard (público), Login, Admin, Farmacia
    ├── vercel.json · .env.example · vite.config.ts
```

---

## Diagrama entidad-relación

```mermaid
erDiagram
    roles ||--o{ usuarios : "tiene"
    municipios ||--o{ usuarios : "reside"
    municipios ||--o{ farmacias : "ubica"
    usuarios |o--o| farmacias : "reporta por"
    farmacias ||--o{ reportes_farmacia : "envía"
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
    enfermedades { int id PK  string codigo UK  string nombre  string codigo_cie10  text recomendaciones  string terminos_busqueda  int umbral_amarillo_pct  int umbral_naranja_pct  int umbral_rojo_pct  bool activo }
    registros_clima { int id PK  int municipio_id FK  date fecha  float temp_max_c  float temp_min_c  float temp_media_c  float precipitacion_mm  float humedad_relativa_pct  bool es_pronostico  bool es_simulado  string fuente }
    tendencias_busqueda { int id PK  string termino  string region  int anio  int semana_epi  date fecha_semana  float indice  string fuente  bool es_simulado }
    farmacias { int id PK  string nombre  string nit UK  int municipio_id FK  int usuario_id FK  bool activa }
    reportes_farmacia { int id PK  int farmacia_id FK  int anio  int semana_epi  string categoria  int unidades  bool es_simulado }
    casos_oficiales { int id PK  int municipio_id FK  int enfermedad_id FK  int anio  int semana_epi  int casos  string fuente  bool es_simulado }
    eventos_volcanicos { int id PK  string tipo  string nivel_actividad  date fecha_inicio  date fecha_fin  int municipio_id FK  int intensidad_ceniza  float so2_ton_dia  string url_boletin  bool es_simulado  int registrado_por_id FK }
    modelos_entrenados { int id PK  int enfermedad_id FK  string algoritmo  string version  datetime fecha_entrenamiento  float mae_base  float rmse_base  float mae_modelo  float rmse_modelo  json importancias  bytes artefacto  bool activo }
    predicciones { int id PK  int modelo_id FK  int municipio_id FK  int enfermedad_id FK  int anio  int semana_epi  int horizonte  float casos_esperados  float limite_inferior  float limite_superior  string nivel_riesgo  json explicacion }
    alertas { int id PK  int municipio_id FK  int enfermedad_id FK  int prediccion_id FK  int anio  int semana_epi  string nivel_riesgo  text mensaje  bool activa  bool notificada_email }
```

Restricciones únicas importantes: `registros_clima(municipio_id, fecha)`, `casos_oficiales(municipio_id, enfermedad_id, anio, semana_epi)`, `tendencias_busqueda(termino, region, anio, semana_epi)` y `reportes_farmacia(farmacia_id, anio, semana_epi, categoria)`. Con ellas no hay datos duplicados aunque el cron corra dos veces.

---

## Semáforo de riesgo (canal endémico)

Para la semana *S* del año *A* se toman los casos de las semanas *S−1, S, S+1* de los **5 años anteriores** (hasta 15 valores) y se calculan percentiles:

| Nivel | Condición (umbrales por defecto, configurables por enfermedad) |
|---|---|
| 🟢 Bajo | casos ≤ P50 |
| 🟡 Moderado | P50 < casos ≤ P75 |
| 🟠 Alto | P75 < casos ≤ P90 |
| 🔴 Muy alto | casos > P90 |

El nivel solo sube de verde si hay **al menos 3 casos**. Ese piso evita falsas alarmas con conteos bajos; por ejemplo, el dengue en Pasto tiene P90 = 0. En la Fase 2 el mismo semáforo se aplica a los **casos predichos** de las próximas 4 semanas.

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
alembic upgrade head                # crea las 13 tablas
python -m app.seed                  # carga datos de prueba (tarda ~1 min si baja clima real)
uvicorn app.main:app --reload       # http://localhost:8000/docs
```

En macOS/Linux, `source .venv/bin/activate` y `cp .env.example .env`.

Sin internet puedes usar `python -m app.seed --sin-red`. Para empezar de cero, `python -m app.seed --reset`.

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
pytest                              # 25 pruebas: auth, CRUD, canal endémico, Open-Meteo, migraciones
```

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

**Frontend** (`frontend/.env.example`): `VITE_API_URL` es la URL pública del backend, sin `/` final.

---

## Despliegue paso a paso (todo gratis)

### Paso 0 · Subir el código a GitHub

```powershell
cd sentinela-predictor
git init
git add .
git commit -m "Fase 1: estructura, BD, auth, Open-Meteo, CRUD y dashboard"
# Crea un repositorio vacío en github.com (sin README) y luego:
git remote add origin https://github.com/TU_USUARIO/sentinela-predictor.git
git branch -M main
git push -u origin main
```

### Paso 1 · Base de datos en Neon (recomendado)

1. Entra a <https://neon.tech> → **Sign up** con GitHub → **Create project**.
   - Nombre: `predictor-brotes`. Postgres 16 o 17. Región: **AWS US West 2 (Oregon)**, la misma región donde `render.yaml` crea el backend (menos latencia).
2. En **Dashboard → Connect**, desactiva **Connection pooling** y copia la cadena. Se ve así:
   `postgresql://neondb_owner:XXXX@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require`
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
   - `CORS_ORIGINS`: de momento `http://localhost:5173`; la actualizas en el paso 4.
   - `ADMIN_PASSWORD` y `DEMO_PASSWORD`: contraseñas con letras y números.
   - `JWT_SECRET` y `CRON_SECRET` se generan solos.
4. **Apply**. El primer despliegue tarda unos 5 minutos: instala dependencias, corre las migraciones y el seed (con clima real de Open-Meteo).
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
`CORS_ORIGINS=https://sentinela-predictor.vercel.app,http://localhost:5173` y guarda. Render se redepliega solo.

Si quieres que funcionen las URLs de *preview*, agrega `CORS_ORIGIN_REGEX=https://sentinela-predictor.*\.vercel\.app`.

### Paso 5 · Verificación final

- [ ] La URL de Vercel muestra el dashboard con semáforo, histórico, volcán, clima y pronóstico.
- [ ] El botón de modo oscuro funciona.
- [ ] **Ingresar** con `admin@predictor.co` lleva al panel de administración. Crea y edita un evento volcánico.
- [ ] En **Datos y modelo → Sincronizar clima** se guardan registros, y el pronóstico deja de decir "simulado".
- [ ] `ciudadano@demo.co` no ve "Administración", y la API le responde 403 si lo intenta.

---

## Datos: qué es real y qué es simulado

| Dato | Fase 1 | Marcado en BD |
|---|---|---|
| Municipios, coordenadas, altitud | Reales (aprox.). Población reutilizada del sistema anterior | — |
| Clima histórico y pronóstico | **Real (Open-Meteo)** si hay internet durante el seed; si no, simulado | `es_simulado`, `fuente` |
| Nivel del Galeras | Último boletín **real** del SGC (25–31 ago 2026: Alerta Amarilla). El histórico semanal y el SO₂ son estimados | `es_simulado` |
| Caídas de ceniza | Simuladas (9 episodios 2020-2025) | `es_simulado` |
| Casos semanales | **Simulados**, calibrados con las medias IRA/EDA del dataset anterior y generados con un modelo Poisson-Gamma que depende del clima con rezagos, la ceniza y el SO₂ | `es_simulado`, `fuente` |
| Farmacias | Ficticias ("Droguería Demo …") | — |

La interfaz muestra la etiqueta **"Datos simulados"** donde corresponde. En la Fase 2, `SivigilaFuente` reemplaza los casos simulados por los de datos.gov.co donde existan.

---

## Decisiones técnicas (para la sustentación)

1. **Se cambia Streamlit por React + FastAPI.** Streamlit no ofrece autenticación multiusuario con roles, sus formularios CRUD son limitados y no expone una API REST para que GitHub Actions dispare actualizaciones. Separar frontend y backend permite desplegar cada parte donde es gratis: Vercel para estáticos y Render para el servidor Python.
2. **Arquitectura por capas.** `routers` solo traduce HTTP, `services` contiene las reglas (por ejemplo "no borrar un municipio con histórico" o "una caída de ceniza exige municipio"), `repositories` encapsula SQLAlchemy y `schemas` valida con Pydantic. Cada capa se prueba por separado.
3. **POO y patrones.**
   - *Strategy/Adapter*: `FuenteDatos` es una clase abstracta y cada fuente adapta su formato externo a filas de nuestras tablas. El servicio de clima recibe la fuente por inyección, y los tests le pasan un transporte HTTP falso.
   - *Repository genérico*: `BaseRepository[Model]`.
   - *Template Method*: `CrudService` con los ganchos `validar()` y `antes_de_eliminar()`.
   - *Factory*: `crear_router_crud()` genera los 5 endpoints de cada catálogo.
4. **Seguridad.**
   - Contraseñas con **bcrypt** (12 rondas).
   - **JWT** HS256 con expiración y rol en el token.
   - Autorización en el **backend** con `requiere_roles()`; el frontend solo oculta menús.
   - Login con mensaje genérico, para no revelar qué correos existen.
   - Endpoint del cron protegido con secreto en la cabecera.
5. **Errores centralizados.** Todas las respuestas de error usan el formato `{"error": {"codigo", "mensaje", "detalles"}}` en español. Las violaciones de unicidad devuelven 409, no un error 500.
6. **Migraciones con Alembic.** El esquema queda versionado, igual en local (SQLite) y en la nube (PostgreSQL); una prueba automática verifica que la migración crea las 13 tablas.
7. **Semana epidemiológica real.** Se usa la librería `epiweeks` (semanas que inician en domingo, como el INS, con semana 53 cuando corresponde). El sistema anterior asumía 52 semanas fijas.
8. **Se corrigieron dos problemas del sistema anterior.**
   - El XGBoost tenía **fuga de datos**: predecía terciles de `tasa_x_100k` usando `tasa_x_100k` como variable, de ahí probabilidades de 0,999. La Fase 2 predice *casos futuros* solo con información pasada (rezagos) y validación temporal.
   - El DIVIPOLA de La Florida estaba mal: era 52299 y el correcto es **52381**.
9. **Dengue y altitud.** El *Aedes aegypti* casi no sobrevive por encima de ~1.800 m. Por eso el riesgo de dengue se concentra en Consacá y Sandoná, y en Pasto representa sobre todo casos importados.
10. **Visualización accesible.**
    - El semáforo siempre combina **icono + texto + color**, nunca solo color.
    - Ninguna gráfica tiene dos ejes Y: temperatura y lluvia van en gráficas separadas.
    - Los colores se definen como tokens con variantes para modo claro y oscuro.

---

## Capturas

| Dashboard (claro) | Dashboard (oscuro) |
|---|---|
| ![Dashboard claro](docs/capturas/dashboard_claro.png) | ![Dashboard oscuro](docs/capturas/dashboard_oscuro.png) |

| Panel de administración | Móvil |
|---|---|
| ![Admin](docs/capturas/admin.png) | ![Móvil](docs/capturas/movil.png) |

---

## API (resumen)

La documentación interactiva completa está en `/docs` (Swagger) y `/redoc`.

| Método | Ruta | Acceso |
|---|---|---|
| POST | `/api/v1/auth/login` · `/auth/registro` · GET `/auth/me` | público / autenticado |
| GET | `/api/v1/dashboard/resumen` · `/serie` · `/riesgo-municipios` · `/volcan` | público |
| GET | `/api/v1/clima/{id}/actual` · `/pronostico` · `/semanal` | público |
| POST | `/api/v1/clima/sincronizar` | ADMIN |
| CRUD | `/api/v1/municipios` · `/enfermedades` · `/eventos-volcanicos` | lectura pública, escritura ADMIN |
| CRUD | `/api/v1/farmacias` · `/usuarios` | ADMIN |
| POST | `/api/v1/jobs/actualizar-datos` | cabecera `X-Cron-Secret` |
