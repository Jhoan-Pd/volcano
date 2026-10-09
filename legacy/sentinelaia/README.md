# SentinelaIA Nariño

Repositorio de trabajo para la construcción de una base analítica territorial enfocada en IRA y EDA en municipios del área de influencia del Volcán Galeras, Nariño, Colombia.

## Arquitectura
raw/ → clean_salud.py → processed/ → build_dataset_final.py → final/ → Power BI

## Municipios objetivo
- Pasto
- Sandoná
- Consacá
- La Florida
- Yacuanquer
- Nariño

## Objetivo actual
En esta etapa no se implementará IA. El foco es:

- Descarga automática de fuentes oficiales
- Limpieza de datos
- Integración con población DANE
- Construcción del dataset final unificado

## Stack técnico
- Python
- Pandas
- Selenium (solo para fuentes sin descarga directa)
- PostgreSQL o BigQuery
- Streamlit

## Estructura
sentinela_narino/
- data/
  - raw/
  - processed/
  - final/
- src/
  - etl/
- notebooks/
- docs/

## Fuentes iniciales
- DIVIPOLA
- Población municipal DANE
- INS / Sivigila
- IRA / EDA
- RIPS
- REPS
- IDEAM
- SGC / Galeras

## Instalación
1. Crear entorno virtual
2. Activarlo
3. Instalar dependencias:
   - requests
   - pandas
   - openpyxl
   - selenium

## Equipo
Proyecto académico SentinelaIA Nariño.

---

## Despliegue

El proyecto tiene **dos piezas que se despliegan en sitios distintos**, porque no son la misma
clase de aplicacion:

| Pieza | Que es | Donde va |
|---|---|---|
| `public/index.html` | Portal institucional estatico con el reporte Power BI embebido | **Vercel** |
| `src/dashboard/app.py` | Dashboard interactivo **Streamlit** (mapas, canal endemico, XGBoost) | **Streamlit Community Cloud** |

> **Importante:** Streamlit **no puede desplegarse en Vercel**. Streamlit necesita un servidor
> persistente con WebSockets y Vercel solo ejecuta funciones serverless de vida corta. Por eso
> `vercel.json` y `.vercelignore` fuerzan a Vercel a publicar unicamente la carpeta `public/`
> como sitio estatico; si no, Vercel detecta los `.py` y `requirements.txt` y falla con
> `No python entrypoint found`.

### 1. Vercel (portal estatico)

Configuracion ya incluida en `vercel.json`:

- Framework Preset: **Other**
- Build Command: ninguno (no-op)
- Output Directory: `public`

En el panel de Vercel: *Add New > Project > importar este repositorio*. No hay que tocar nada mas,
`vercel.json` manda. Si Vercel insiste en detectar Python, entrar a *Settings > General* y poner
**Framework Preset = Other**.

### 2. Streamlit Community Cloud (dashboard)

1. Entrar a https://share.streamlit.io e iniciar sesion con GitHub.
2. *New app* y seleccionar este repositorio.
3. **Main file path:** `src/dashboard/app.py`
4. Elegir la URL `sentinelaia-narino` (es la que el portal ya enlaza en el boton
   "Dashboard IA"; si se usa otra, actualizar ese `href` en `public/index.html`).
5. Deploy.

El tema oscuro esta en `.streamlit/config.toml` y las dependencias en `requirements.txt`.

### Datos

El dashboard lee de `data/final/`. Esos tres CSV **si estan versionados** (son ~500 KB) para que
la app tenga datos en produccion. `data/raw/` y `data/processed/` siguen ignorados: se regeneran
con el pipeline ETL local.

```
python src/etl/download_sources.py
python src/etl/clean_salud.py
python src/etl/build_dataset_final.py
python src/models/modelo_xgboost.py
```

### Ejecutar en local

```
pip install -r requirements.txt
streamlit run src/dashboard/app.py
```

