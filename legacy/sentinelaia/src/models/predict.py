"""
SentinelaIA Nariño — Inferencia con modelo XGBoost entrenado
Uso:
    python src/models/predict.py --municipio 52001 --semana 35 --anio 2025
    python src/models/predict.py  # predice próximas 4 semanas para todos los municipios
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import argparse
import pandas as pd
import numpy as np
import joblib

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "src" / "models"
DATA_PATH = BASE_DIR / "data" / "final" / "dataset_final_municipio_semana.csv"
OUTPUT_CSV = BASE_DIR / "data" / "final" / "predicciones_proximas.csv"

MUNICIPIOS = {
    "52001": "Pasto", "52683": "Sandoná", "52207": "Consacá",
    "52299": "La Florida", "52885": "Yacuanquer", "52480": "Nariño"
}
POBLACIONES = {
    "52001": 450000, "52683": 30000, "52207": 15000,
    "52299": 18000, "52885": 12000, "52480": 20000
}
DISTANCIAS = {
    "52001": 9, "52683": 18, "52207": 15,
    "52299": 22, "52885": 16, "52480": 25
}


def cargar_modelo():
    model = joblib.load(MODEL_DIR / "modelo_riesgo_xgboost.pkl")
    le = joblib.load(MODEL_DIR / "label_encoder.pkl")
    features = joblib.load(MODEL_DIR / "features.pkl")
    return model, le, features


def construir_fila(cod, semana, anio, evento="EDA", so2=None, features=None):
    semana_sin = np.sin(2 * np.pi * semana / 52)
    semana_cos = np.cos(2 * np.pi * semana / 52)
    evento_bin = 1 if evento == "IRA" else 0

    raw = {
        "semana_epidemiologica": semana,
        "anio": anio,
        "poblacion": POBLACIONES.get(str(cod), 20000),
        "tasa_x_100k": 0.0,
        "so2_flux_ton_dia": so2 if so2 is not None else 300.0,
        "distancia_crater_km": DISTANCIAS.get(str(cod), 20),
        "semana_sin": semana_sin,
        "semana_cos": semana_cos,
        "evento_bin": evento_bin,
    }
    if features:
        return {k: raw.get(k, 0) for k in features}
    return raw


def predecir_proximas_semanas(semanas_adelante=4):
    df = pd.read_csv(DATA_PATH)
    semana_actual = int(df["semana_epidemiologica"].max())
    anio_actual = int(df["anio"].max())
    model, le, features = cargar_modelo()

    resultados = []
    for i in range(1, semanas_adelante + 1):
        semana_fut = (semana_actual + i - 1) % 52 + 1
        anio_fut = anio_actual if (semana_actual + i) <= 52 else anio_actual + 1

        for cod, nombre in MUNICIPIOS.items():
            for evento in ["EDA", "IRA"]:
                fila = construir_fila(cod, semana_fut, anio_fut, evento, features=features)
                X = pd.DataFrame([fila])
                pred = le.inverse_transform(model.predict(X))[0]
                proba = model.predict_proba(X)[0].max()
                resultados.append({
                    "cod_divipola": cod,
                    "municipio": nombre,
                    "semana_epidemiologica": semana_fut,
                    "anio": anio_fut,
                    "evento_estandar": evento,
                    "nivel_riesgo_predicho": pred,
                    "probabilidad": round(proba, 3),
                })

    df_pred = pd.DataFrame(resultados)
    df_pred.to_csv(OUTPUT_CSV, index=False)
    print(f"✓ {len(df_pred)} predicciones guardadas en {OUTPUT_CSV}")
    print(df_pred.to_string(index=False))
    return df_pred


def predecir_punto(cod, semana, anio, evento="EDA", so2=None):
    model, le, features = cargar_modelo()
    fila = construir_fila(cod, semana, anio, evento, so2, features)
    X = pd.DataFrame([fila])
    pred = le.inverse_transform(model.predict(X))[0]
    probas = model.predict_proba(X)[0]
    clases = le.classes_

    print(f"\nPredicción — {MUNICIPIOS.get(str(cod), cod)}, Sem {semana}/{anio}, {evento}")
    print(f"  Nivel riesgo: {pred.upper()}")
    for c, p in zip(clases, probas):
        bar = "█" * int(p * 20)
        print(f"  {c:6s}: {p:.1%}  {bar}")
    return pred


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SentinelaIA — Predicción de riesgo")
    parser.add_argument("--municipio", help="Código DIVIPOLA (ej: 52001)")
    parser.add_argument("--semana", type=int, help="Semana epidemiológica (1-52)")
    parser.add_argument("--anio", type=int, help="Año")
    parser.add_argument("--evento", default="EDA", choices=["IRA", "EDA"])
    parser.add_argument("--so2", type=float, help="SO₂ flux en t/día")
    args = parser.parse_args()

    if not (MODEL_DIR / "modelo_riesgo_xgboost.pkl").exists():
        print("ERROR: modelo no entrenado. Ejecuta primero: python src/models/modelo_xgboost.py")
        exit(1)

    if args.municipio and args.semana and args.anio:
        predecir_punto(args.municipio, args.semana, args.anio, args.evento, args.so2)
    else:
        print("Predicciones para las próximas 4 semanas:")
        predecir_proximas_semanas(4)
