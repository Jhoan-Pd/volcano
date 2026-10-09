"""
SentinelaIA Nariño — Modelo XGBoost de Clasificación de Riesgo Epidemiológico
Fase 5 — Concurso Datos al Ecosistema 2026 (MinTIC)

Ejecutar desde la raíz del proyecto:
    python src/models/modelo_xgboost.py

Requiere:
    pip install xgboost scikit-learn pandas numpy joblib
"""

import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# 1. CONFIGURACIÓN
# ─────────────────────────────────────────────
DATA_PATH   = "data/final/dataset_final_eda_municipio_semana.csv"
MODEL_DIR   = "src/models"
OUTPUT_CSV  = "data/final/predicciones_riesgo.csv"

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs("data/final", exist_ok=True)

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    print("[WARN] xgboost no disponible — usando GradientBoosting de sklearn como fallback")
    from sklearn.ensemble import GradientBoostingClassifier
    XGBOOST_AVAILABLE = False

# ─────────────────────────────────────────────
# 2. CARGA Y PREPARACIÓN DE DATOS
# ─────────────────────────────────────────────
print("=" * 60)
print("  SentinelaIA Nariño — Pipeline XGBoost")
print("=" * 60)

df = pd.read_csv(DATA_PATH)
print(f"\n[1] Dataset cargado: {len(df):,} filas × {df.shape[1]} columnas")
print(f"    Columnas: {list(df.columns)}")
print(f"    Municipios: {df['municipio'].unique().tolist()}")
print(f"    Años: {sorted(df['anio'].unique().tolist())}")

# Crear variable target si no existe
if "nivel_riesgo" not in df.columns:
    df["nivel_riesgo"] = pd.qcut(
        df["tasa_x_100k"],
        q=3,
        labels=["bajo", "medio", "alto"],
        duplicates="drop"
    )
    print(f"\n[2] Variable target 'nivel_riesgo' creada por terciles de tasa_x_100k")
else:
    print(f"\n[2] Variable target 'nivel_riesgo' ya existe en el dataset")

print(f"    Distribución:\n{df['nivel_riesgo'].value_counts()}")

# ─────────────────────────────────────────────
# 3. FEATURE ENGINEERING
# ─────────────────────────────────────────────
# Features deseadas (las disponibles en el dataset se usan automáticamente)
FEATURES_DESEADAS = [
    "semana_epidemiologica",
    "anio",
    "poblacion",
    "tasa_x_100k",
    "precipitacion_mm",
    "temperatura_max_c",
    "so2_flux_ton_dia",
    "irca_pct",
    "distancia_crater_km",
]

# Features adicionales derivadas
df["semana_sin"] = np.sin(2 * np.pi * df["semana_epidemiologica"] / 52)
df["semana_cos"] = np.cos(2 * np.pi * df["semana_epidemiologica"] / 52)
df["evento_bin"]  = (df["evento_estandar"] == "IRA").astype(int)

FEATURES_DERIVADAS = ["semana_sin", "semana_cos", "evento_bin"]

features_disponibles = [f for f in FEATURES_DESEADAS if f in df.columns]
features_todas = features_disponibles + FEATURES_DERIVADAS

print(f"\n[3] Features utilizadas ({len(features_todas)}): {features_todas}")

# ─────────────────────────────────────────────
# 4. ENCODING Y SPLIT
# ─────────────────────────────────────────────
le = LabelEncoder()
df["nivel_riesgo_enc"] = le.fit_transform(df["nivel_riesgo"].astype(str))

X = df[features_todas].fillna(0)
y = df["nivel_riesgo_enc"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\n[4] Train: {len(X_train):,} | Test: {len(X_test):,}")

# ─────────────────────────────────────────────
# 5. ENTRENAMIENTO
# ─────────────────────────────────────────────
if XGBOOST_AVAILABLE:
    model = XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )
else:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.multiclass import OneVsRestClassifier
    model = GradientBoostingClassifier(
        n_estimators=150, max_depth=4, learning_rate=0.1, random_state=42
    )

print("\n[5] Entrenando modelo...")
model.fit(X_train, y_train)
print("    ✓ Entrenamiento completado")

# ─────────────────────────────────────────────
# 6. EVALUACIÓN
# ─────────────────────────────────────────────
y_pred = model.predict(X_test)
print("\n[6] Métricas de evaluación:")
print(classification_report(y_test, y_pred, target_names=le.classes_))

# Cross-validation
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
print(f"    Accuracy CV 5-fold: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

# Confusion matrix
cm = confusion_matrix(y_test, y_pred)
print(f"\n    Matriz de confusión:\n{cm}")

# Feature importance
if hasattr(model, "feature_importances_"):
    fi = pd.Series(model.feature_importances_, index=features_todas).sort_values(ascending=False)
    print(f"\n    Top-5 features más importantes:")
    print(fi.head(5).to_string())

# ─────────────────────────────────────────────
# 7. EXPORTAR MODELO
# ─────────────────────────────────────────────
joblib.dump(model, os.path.join(MODEL_DIR, "modelo_riesgo_xgboost.pkl"))
joblib.dump(le,    os.path.join(MODEL_DIR, "label_encoder.pkl"))
print(f"\n[7] Modelo guardado en {MODEL_DIR}/modelo_riesgo_xgboost.pkl")

# ─────────────────────────────────────────────
# 8. GENERAR PREDICCIONES COMPLETAS
# ─────────────────────────────────────────────
print("\n[8] Generando predicciones sobre todo el dataset...")

X_all = df[features_todas].fillna(0)
pred_labels = le.inverse_transform(model.predict(X_all))

if hasattr(model, "predict_proba"):
    proba_all = model.predict_proba(X_all)
    max_proba = proba_all.max(axis=1)
else:
    max_proba = np.ones(len(df)) * 0.75

pred_df = pd.DataFrame({
    "cod_divipola":           df["cod_divipola"].values,
    "municipio":              df["municipio"].values,
    "semana_epidemiologica":  df["semana_epidemiologica"].values,
    "anio":                   df["anio"].values,
    "evento_estandar":        df["evento_estandar"].values,
    "nivel_riesgo_predicho":  pred_labels,
    "probabilidad":           max_proba.round(3),
})

pred_df.to_csv(OUTPUT_CSV, index=False)
print(f"    ✓ Predicciones guardadas en {OUTPUT_CSV}")
print(f"    Filas: {len(pred_df):,}")
print(f"\n    Distribución predicciones:\n{pred_df['nivel_riesgo_predicho'].value_counts()}")

print("\n" + "=" * 60)
print("  Pipeline completado exitosamente ✓")
print("=" * 60)
