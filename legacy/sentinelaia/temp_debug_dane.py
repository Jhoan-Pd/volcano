# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path
import unicodedata
import re

def norm(x):
    x = str(x).strip()
    x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("utf-8")
    x = re.sub(r"\s+", "_", x)
    return x.upper()

file = Path("data/raw/dane/poblacion_municipal.xlsx")
xls = pd.ExcelFile(file)

print("Hojas disponibles:")
for i, s in enumerate(xls.sheet_names):
    print(i, s)
print()

target_sheet = None
for s in xls.sheet_names:
    if "PobMunicipal" in s or "PobMunicipalx" in s or "PobMunicipalxArea" in s:
        target_sheet = s
        break

if target_sheet is None:
    target_sheet = xls.sheet_names[1]

print("Hoja objetivo:", target_sheet)
print()

df = pd.read_excel(file, sheet_name=target_sheet, header=7)
df.columns = [norm(c) for c in df.columns]

print("Columnas reales:")
print(df.columns.tolist())
print()

print("Primeras 10 filas:")
print(df.head(10).to_string())
print()

print("Valores únicos de DPMP (primeros 30):")
print(df["DPMP"].dropna().astype(str).unique()[:30] if "DPMP" in df.columns else "No existe DPMP")
print()

print("Filas donde el departamento parece Nariño:")
if "DPNOM" in df.columns:
    mask = df["DPNOM"].astype(str).str.upper().str.contains("NARI", na=False)
    cols = [c for c in ["DP", "DPNOM", "MPIO", "DPMP", "ANO", "AREA_GEOGRAFICA", "TOTAL"] if c in df.columns]
    print(df.loc[mask, cols].head(30).to_string())
else:
    print("No existe columna DPNOM")
