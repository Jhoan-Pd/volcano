"""
SentinelaIA Nariño — Modelo XGBoost de Clasificación de Riesgo Epidemiológico
Ejecutar desde BI_Health_Nari-o/:
    python src/models/modelo_xgboost.py
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "final" / "dataset_final_municipio_semana.csv"
MODEL_DIR = BASE_DIR / "src" / "models"
OUTPUT_CSV = BASE_DIR / "data" / "final" / "predicciones_riesgo.csv"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    print("[WARN] xgboost no disponible — usando GradientBoosting de sklearn")
    XGBOOST_AVAILABLE = False

print("=" * 60)
print("  SentinelaIA Nariño — Pipeline XGBoost")
print("=" * 60)

df = pd.read_csv(DATA_PATH)
print(f"\n[1] Dataset: {len(df):,} filas × {df.shape[1]} columnas")
print(f"    Columnas: {list(df.columns)}")
print(f"    Municipios: {df['municipio'].unique().tolist()}")
print(f"    Años: {sorted(df['anio'].unique().tolist())}")

# Target
if "nivel_riesgo" not in df.columns:
    df["nivel_riesgo"] = pd.qcut(
        df["tasa_x_100k"], q=3,
        labels=["bajo", "medio", "alto"], duplicates="drop"
    )
    print(f"\n[2] Variable 'nivel_riesgo' creada por terciles de tasa_x_100k")
else:
    print(f"\n[2] Variable 'nivel_riesgo' ya existe")
print(f"    Distribución:\n{df['nivel_riesgo'].value_counts()}")

# Feature engineering
df["semana_sin"] = np.sin(2 * np.pi * df["semana_epidemiologica"] / 52)
df["semana_cos"] = np.cos(2 * np.pi * df["semana_epidemiologica"] / 52)
df["evento_bin"] = (df["evento_estandar"] == "IRA").astype(int)

FEATURES_DESEADAS = [
    "semana_epidemiologica", "anio", "poblacion", "tasa_x_100k",
    "precipitacion_mm", "temperatura_max_c",
    "so2_flux_ton_dia", "irca_pct", "distancia_crater_km",
]
FEATURES_DERIVADAS = ["semana_sin", "semana_cos", "evento_bin"]

features_disponibles = [f for f in FEATURES_DESEADAS if f in df.columns]
features_todas = features_disponibles + FEATURES_DERIVADAS
print(f"\n[3] Features ({len(features_todas)}): {features_todas}")

# Encoding
le = LabelEncoder()
df["nivel_riesgo_enc"] = le.fit_transform(df["nivel_riesgo"].astype(str))

X = df[features_todas].fillna(0)
y = df["nivel_riesgo_enc"]
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\n[4] Train: {len(X_train):,} | Test: {len(X_test):,}")

# Entrenamiento
if XGBOOST_AVAILABLE:
    model = XGBClassifier(
        n_estimators=150, max_depth=4, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="mlogloss", random_state=42, n_jobs=-1,
    )
else:
    from sklearn.ensemble import GradientBoostingClassifier
    model = GradientBoostingClassifier(
        n_estimators=150, max_depth=4, learning_rate=0.1, random_state=42
    )

print("\n[5] Entrenando...")
model.fit(X_train, y_train)
print("    OK Listo")

# Evaluación
y_pred = model.predict(X_test)
print("\n[6] Métricas:")
print(classification_report(y_test, y_pred, target_names=le.classes_))

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
print(f"    CV 5-fold accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
print(f"\n    Confusion matrix:\n{confusion_matrix(y_test, y_pred)}")

if hasattr(model, "feature_importances_"):
    fi = pd.Series(model.feature_importances_, index=features_todas).sort_values(ascending=False)
    print(f"\n    Top features:\n{fi.head(5).to_string()}")

# Exportar modelo
joblib.dump(model, MODEL_DIR / "modelo_riesgo_xgboost.pkl")
joblib.dump(le, MODEL_DIR / "label_encoder.pkl")
joblib.dump(features_todas, MODEL_DIR / "features.pkl")
print(f"\n[7] Modelo guardado en {MODEL_DIR.name}")

# Predicciones sobre todo el dataset histórico
print("\n[8] Generando predicciones históricas...")
X_all = df[features_todas].fillna(0)
pred_labels = le.inverse_transform(model.predict(X_all))
max_proba = (
    model.predict_proba(X_all).max(axis=1)
    if hasattr(model, "predict_proba")
    else np.ones(len(df)) * 0.75
)

pred_df = pd.DataFrame({
    "cod_divipola": df["cod_divipola"].values,
    "municipio": df["municipio"].values,
    "semana_epidemiologica": df["semana_epidemiologica"].values,
    "anio": df["anio"].values,
    "evento_estandar": df["evento_estandar"].values,
    "nivel_riesgo_predicho": pred_labels,
    "probabilidad": max_proba.round(3),
})

# ── Predicciones futuras: 2025 y 2026 ──────────────────────────────────────
print("\n[9] Generando predicciones futuras (2025-2026)...")

ANOS_FUTUROS = [2025, 2026]
SEMANAS = list(range(1, 53))

# Referencia por municipio + evento: promedios de los últimos 2 años disponibles
anio_max = df["anio"].max()
df_ref = df[df["anio"] >= anio_max - 1].copy()
ref = (
    df_ref.groupby(["municipio", "cod_divipola", "evento_estandar"])
    .agg(
        tasa_ref=("tasa_x_100k", "mean"),
        pob_ref=("poblacion", "last"),
        so2_ref=("so2_flux_ton_dia", "mean") if "so2_flux_ton_dia" in df.columns else ("poblacion", "last"),
    )
    .reset_index()
)

filas_futuras = []
for anio in ANOS_FUTUROS:
    for semana in SEMANAS:
        for _, r in ref.iterrows():
            fila = {
                "cod_divipola": r["cod_divipola"],
                "municipio": r["municipio"],
                "semana_epidemiologica": semana,
                "anio": anio,
                "evento_estandar": r["evento_estandar"],
                "poblacion": r["pob_ref"],
                "tasa_x_100k": r["tasa_ref"],
            }
            if "so2_flux_ton_dia" in features_todas:
                fila["so2_flux_ton_dia"] = r.get("so2_ref", 0)
            filas_futuras.append(fila)

df_fut = pd.DataFrame(filas_futuras)
df_fut["semana_sin"] = np.sin(2 * np.pi * df_fut["semana_epidemiologica"] / 52)
df_fut["semana_cos"] = np.cos(2 * np.pi * df_fut["semana_epidemiologica"] / 52)
df_fut["evento_bin"] = (df_fut["evento_estandar"] == "IRA").astype(int)

X_fut = df_fut[features_todas].fillna(0)
fut_labels = le.inverse_transform(model.predict(X_fut))
fut_proba = (
    model.predict_proba(X_fut).max(axis=1)
    if hasattr(model, "predict_proba")
    else np.ones(len(df_fut)) * 0.75
)

pred_fut_df = pd.DataFrame({
    "cod_divipola": df_fut["cod_divipola"].values,
    "municipio": df_fut["municipio"].values,
    "semana_epidemiologica": df_fut["semana_epidemiologica"].values,
    "anio": df_fut["anio"].values,
    "evento_estandar": df_fut["evento_estandar"].values,
    "nivel_riesgo_predicho": fut_labels,
    "probabilidad": fut_proba.round(3),
})
print(f"    OK {len(pred_fut_df):,} predicciones futuras generadas")

# ── Combinar histórico + futuro ──────────────────────────────────────────────
pred_df = pd.concat([pred_df, pred_fut_df], ignore_index=True)
pred_df.to_csv(OUTPUT_CSV, index=False)
print(f"\n[10] Total guardado: {len(pred_df):,} predicciones en {OUTPUT_CSV.name}")
print(f"     Años: {sorted(pred_df['anio'].unique().tolist())}")
print(f"     Distribución nivel:\n{pred_df['nivel_riesgo_predicho'].value_counts()}")

print("\n" + "=" * 60)
print("  Pipeline completado OK")
print("=" * 60)
