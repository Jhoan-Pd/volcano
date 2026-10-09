"""
SentinelaIA Nariño — Descarga automática de datasets
Municipios área Galeras: Pasto, Sandoná, Consacá, La Florida, Yacuanquer, Nariño

Ejecutar desde BI_Health_Nari-o/:
    python src/etl/download_data.py
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import requests
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
(RAW_DIR / "salud").mkdir(exist_ok=True)
(RAW_DIR / "dane").mkdir(exist_ok=True)

MUNICIPIOS_DIVIPOLA = ["52001", "52683", "52207", "52299", "52885", "52480"]
MUNICIPIOS_NOMBRES = {
    "52001": "Pasto", "52683": "Sandoná", "52207": "Consacá",
    "52299": "La Florida", "52885": "Yacuanquer", "52480": "Nariño"
}
POBLACIONES_BASE = {
    "52001": 450000, "52683": 30000, "52207": 15000,
    "52299": 18000, "52885": 12000, "52480": 20000
}
DISTANCIAS_CRATER = {
    "52001": 9, "52683": 18, "52207": 15,
    "52299": 22, "52885": 16, "52480": 25
}


def _get(url, params=None, timeout=30):
    try:
        r = requests.get(url, params=params or {}, timeout=timeout)
        if r.status_code == 200:
            return r
    except Exception as e:
        print(f"  [WARN] {e}")
    return None


# ─── SIVIGILA ────────────────────────────────────────────────────────────────

def download_sivigila():
    print("\n[1] Descargando SIVIGILA (INS — datos.gov.co)...")
    endpoints = [
        ("https://www.datos.gov.co/resource/uay3-ffpn.json",
         {"$limit": 50000, "$where": "cod_dpto_o='52'", "$order": "semana_epi ASC"}),
        ("https://www.datos.gov.co/resource/qvnt-2igj.json",
         {"$limit": 50000, "$where": "departamento='NARIÑO'"}),
        ("https://www.datos.gov.co/resource/rdxq-mnrs.json",
         {"$limit": 50000, "$where": "departamento='NARIÑO'"}),
    ]
    for url, params in endpoints:
        r = _get(url, params)
        if r:
            data = r.json()
            if data:
                df = pd.DataFrame(data)
                out = RAW_DIR / "sivigila_narino.csv"
                df.to_csv(out, index=False)
                print(f"  ✓ {len(df)} registros → {out.name}")
                return df

    print("  ⚠ No se pudo descargar SIVIGILA — generando dataset sintético")
    return _generar_salud_sintetico()


def _generar_salud_sintetico():
    """Genera datos sintéticos que reflejan la estacionalidad real de IRA/EDA."""
    rng = np.random.default_rng(42)
    rows = []
    for anio in range(2023, 2025):
        for semana in range(1, 53):
            for cod, nombre in MUNICIPIOS_NOMBRES.items():
                pob = POBLACIONES_BASE[cod]
                factor = pob / 450000

                # IRA pico en semanas frías (1-10, 30-45)
                if semana <= 10 or semana >= 40:
                    casos_ira = int(rng.poisson(35 * factor))
                else:
                    casos_ira = int(rng.poisson(15 * factor))

                # EDA pico en temporada lluvias (15-30)
                if 15 <= semana <= 30:
                    casos_eda = int(rng.poisson(20 * factor))
                else:
                    casos_eda = int(rng.poisson(8 * factor))

                for evento, casos in [("IRA", casos_ira), ("EDA", casos_eda)]:
                    rows.append({
                        "cod_mun_o": cod, "nmun_proce": nombre,
                        "ndep_proce": "NARINO", "ano": anio,
                        "semana": semana, "nom_eve": evento,
                        "cas_conc": casos
                    })

    df = pd.DataFrame(rows)
    out = RAW_DIR / "sivigila_narino.csv"
    df.to_csv(out, index=False)
    print(f"  ✓ Sintético: {len(df)} filas → {out.name}")
    return df


# ─── DANE POBLACIÓN ──────────────────────────────────────────────────────────

def download_dane_poblacion():
    print("\n[2] Descargando DANE Población (datos.gov.co)...")
    endpoints = [
        ("https://www.datos.gov.co/resource/deus-2xe9.json",
         {"$limit": 10000, "$where": "cod_dpto='52'", "$order": "vigencia DESC"}),
        ("https://www.datos.gov.co/resource/jp7h-8ywr.json",
         {"$limit": 10000, "$where": "cod_dpto='52'"}),
    ]
    for url, params in endpoints:
        r = _get(url, params)
        if r:
            data = r.json()
            if data:
                df = pd.DataFrame(data)
                out = RAW_DIR / "dane" / "poblacion_api.csv"
                df.to_csv(out, index=False)
                print(f"  ✓ {len(df)} registros → {out.name}")
                return df

    print("  ⚠ No se pudo descargar DANE — generando tabla base")
    return _generar_dane_sintetico()


def _generar_dane_sintetico():
    rows = []
    for anio in [2023, 2024, 2025]:
        for cod, nombre in MUNICIPIOS_NOMBRES.items():
            rows.append({
                "cod_divipola": cod, "municipio": nombre,
                "departamento": "NARINO", "anio": anio,
                "poblacion": POBLACIONES_BASE[cod]
            })
    df = pd.DataFrame(rows)
    out = RAW_DIR / "dane" / "poblacion_api.csv"
    df.to_csv(out, index=False)
    print(f"  ✓ Sintético DANE: {len(df)} filas → {out.name}")
    return df


# ─── DIVIPOLA ─────────────────────────────────────────────────────────────────

def download_divipola():
    print("\n[3] Descargando DIVIPOLA (datos.gov.co)...")
    r = _get(
        "https://www.datos.gov.co/resource/gdxc-w37w.json",
        {"$limit": 5000, "$where": "c_digo_dane_del_departamento='52'"}
    )
    if r:
        data = r.json()
        if data:
            df = pd.DataFrame(data)
            out = RAW_DIR / "divipola.csv"
            df.to_csv(out, index=False)
            print(f"  ✓ {len(df)} municipios Nariño → {out.name}")
            return df

    print("  ⚠ Generando DIVIPOLA local")
    df = pd.DataFrame([
        {"cod_divipola": k, "municipio": v, "departamento": "NARINO",
         "distancia_crater_km": DISTANCIAS_CRATER[k]}
        for k, v in MUNICIPIOS_NOMBRES.items()
    ])
    df.to_csv(RAW_DIR / "divipola.csv", index=False)
    return df


# ─── IDEAM CLIMA ─────────────────────────────────────────────────────────────

def download_ideam():
    print("\n[4] Descargando IDEAM clima (datos.gov.co)...")
    r = _get(
        "https://www.datos.gov.co/resource/s54a-sgyg.json",
        {"$limit": 50000, "$where": "departamento='NARIÑO'", "$order": "fecha ASC"}
    )
    if r:
        data = r.json()
        if data:
            df = pd.DataFrame(data)
            out = RAW_DIR / "ideam_narino.csv"
            df.to_csv(out, index=False)
            print(f"  ✓ {len(df)} registros climáticos → {out.name}")
            return df

    print("  ⚠ Generando datos climáticos sintéticos Galeras")
    return _generar_clima_sintetico()


def _generar_clima_sintetico():
    rng = np.random.default_rng(7)
    rows = []
    for anio in range(2020, 2025):
        for semana in range(1, 53):
            # Lluvias altas en semanas 15-30 y 35-45
            if 15 <= semana <= 30 or 35 <= semana <= 45:
                precip = round(float(rng.uniform(60, 200)), 1)
            else:
                precip = round(float(rng.uniform(10, 60)), 1)
            rows.append({
                "anio": anio,
                "semana_epidemiologica": semana,
                "precipitacion_mm": precip,
                "temperatura_max_c": round(float(rng.uniform(18, 28)), 1),
                "temperatura_min_c": round(float(rng.uniform(8, 15)), 1),
                "humedad_relativa_pct": round(float(rng.uniform(60, 90)), 1),
                "fuente": "IDEAM_estimado",
            })
    df = pd.DataFrame(rows)
    out = RAW_DIR / "ideam_narino.csv"
    df.to_csv(out, index=False)
    print(f"  ✓ Sintético IDEAM: {len(df)} filas → {out.name}")
    return df


# ─── SO₂ GALERAS ─────────────────────────────────────────────────────────────

def download_galeras_so2():
    print("\n[5] Descargando SO₂ Galeras (SGC/NOVAC)...")
    try:
        r = _get(
            "https://novac.chalmers.se/api/v1/measurements",
            {"volcano": "Galeras", "format": "json"},
            timeout=15
        )
        if r and r.json():
            df = pd.DataFrame(r.json())
            out = RAW_DIR / "galeras_so2_novac.csv"
            df.to_csv(out, index=False)
            print(f"  ✓ NOVAC: {len(df)} registros")
            return df
    except Exception:
        pass

    print("  ⚠ NOVAC no disponible — generando serie histórica SGC estimada")
    return _generar_so2_sintetico()


def _generar_so2_sintetico():
    """
    Valores de SO₂ basados en los rangos históricos del SGC para Galeras:
    nivel verde 100-400 t/día, amarillo 400-800, naranja/rojo >800.
    """
    rng = np.random.default_rng(99)
    rows = []
    for anio in range(2020, 2025):
        for semana in range(1, 53):
            # Actividad elevada 2020-2021 y pico 2023
            if anio in (2020, 2021):
                base_so2 = float(rng.uniform(200, 700))
            elif anio == 2023:
                base_so2 = float(rng.uniform(300, 900))
            else:
                base_so2 = float(rng.uniform(100, 500))

            nivel = (
                "naranja" if base_so2 > 700
                else "amarillo" if base_so2 > 400
                else "verde"
            )
            rows.append({
                "anio": anio,
                "semana_epidemiologica": semana,
                "so2_flux_ton_dia": round(base_so2, 1),
                "nivel_actividad_volcanica": nivel,
                "fuente": "SGC_estimado",
            })
    df = pd.DataFrame(rows)
    out = RAW_DIR / "galeras_actividad.csv"
    df.to_csv(out, index=False)
    print(f"  ✓ Sintético SO₂ Galeras: {len(df)} filas → {out.name}")
    return df


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SentinelaIA Nariño — Descarga de Datos")
    print("=" * 60)
    download_sivigila()
    download_dane_poblacion()
    download_divipola()
    download_ideam()
    download_galeras_so2()
    print("\n" + "=" * 60)
    print("  Descarga completa ✓")
    print("  Próximo paso: python src/etl/clean_salud.py")
    print("=" * 60)
