# Modelo de Datos — SentinelaIA Nariño

## Dataset maestro: `dataset_final_eda_municipio_semana.csv`

| Columna | Tipo | Descripción |
|---|---|---|
| `cod_divipola` | int | Código DIVIPOLA del municipio |
| `municipio` | str | Nombre del municipio |
| `departamento` | str | Departamento (Nariño) |
| `anio` | int | Año epidemiológico |
| `semana_epidemiologica` | int | Semana 1–52 |
| `evento_estandar` | str | IRA o EDA |
| `casos` | int | Casos notificados en la semana |
| `poblacion` | int | Población municipal anual (DANE) |
| `tasa_x_100k` | float | Incidencia por 100.000 hab. |
| `so2_flux_ton_dia` | float | Emisión SO₂ Galeras (t/día, SGC) |

## Dataset de predicciones: `predicciones_riesgo.csv`

| Columna | Tipo | Descripción |
|---|---|---|
| `cod_divipola` | int | Código DIVIPOLA |
| `municipio` | str | Municipio |
| `semana_epidemiologica` | int | Semana |
| `anio` | int | Año |
| `evento_estandar` | str | IRA / EDA |
| `nivel_riesgo_predicho` | str | bajo / medio / alto |
| `probabilidad` | float | Confianza del modelo (0–1) |

## Municipios objetivo

| Municipio | DIVIPOLA | Distancia cráter |
|---|---|---|
| Pasto | 52001 | 9 km |
| Consacá | 52207 | 15 km |
| La Florida | 52299 | 22 km |
| Nariño | 52480 | 25 km |
| Sandoná | 52683 | 18 km |
| Yacuanquer | 52885 | 16 km |

## Modelo XGBoost

- **Tipo:** Clasificación multiclase (bajo / medio / alto)
- **Target:** `nivel_riesgo` (terciles de `tasa_x_100k`)
- **Features garantizadas:** `semana_epidemiologica`, `anio`, `poblacion`, `tasa_x_100k`, `semana_sin`, `semana_cos`, `evento_bin`
- **Features opcionales:** `precipitacion_mm`, `temperatura_max_c`, `so2_flux_ton_dia`, `irca_pct`, `distancia_crater_km`
- **Validación:** StratifiedKFold 5 pliegues
