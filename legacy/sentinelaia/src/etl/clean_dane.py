import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import pandas as pd
import unicodedata
import re

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_FILE = BASE_DIR / "data" / "raw" / "dane" / "poblacion_municipal.xlsx"
RAW_FILE_CSV = BASE_DIR / "data" / "raw" / "dane" / "poblacion_api.csv"
OUT_DIR = BASE_DIR / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_CODES = {
    "52001": "PASTO",
    "52207": "CONSACA",
    "52381": "LA FLORIDA",
    "52480": "NARINO",
    "52683": "SANDONA",
    "52885": "YACUANQUER",
}

TARGET_YEARS = [2023, 2024, 2025]

def normalize_text(text):
    text = str(text).strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")

def clean_text(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("utf-8")
    value = re.sub(r"\s+", " ", value)
    return value.upper()

def main():
    # Use pre-built API CSV directly when the DANE xlsx is not available
    if not RAW_FILE.exists() and RAW_FILE_CSV.exists():
        print(f"[INFO] poblacion_municipal.xlsx no encontrado — usando {RAW_FILE_CSV.name}")
        dane_final = pd.read_csv(RAW_FILE_CSV, dtype={"cod_divipola": str})
        dane_final["cod_divipola"] = dane_final["cod_divipola"].str.zfill(5)
        dane_final["municipio"] = dane_final["cod_divipola"].map(TARGET_CODES).fillna(dane_final["municipio"])
        dane_final["departamento"] = "NARINO"
        dane_final = dane_final[dane_final["anio"].isin(TARGET_YEARS)].copy()
        dane_final = dane_final[["cod_divipola", "municipio", "departamento", "anio", "poblacion"]]
        dane_final = dane_final.sort_values(["cod_divipola", "anio"]).reset_index(drop=True)
        dane_final.to_csv(OUT_DIR / "dane_poblacion_2023_2025_galeras.csv", index=False, encoding="utf-8-sig")
        print(f"    OK → {OUT_DIR / 'dane_poblacion_2023_2025_galeras.csv'}")
        return

    if not RAW_FILE.exists():
        raise FileNotFoundError(f"No existe el archivo: {RAW_FILE}\nNi el fallback: {RAW_FILE_CSV}")

    df = pd.read_excel(RAW_FILE, sheet_name="PobMunicipalxÁrea", header=7)
    df.columns = [normalize_text(c) for c in df.columns]

    print("Columnas detectadas:")
    for c in df.columns:
        print("-", c)

    required = ["dp", "dpnom", "mpio", "dpmp", "ano", "area_geografica", "total"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas esperadas: {missing}")

    dane = pd.DataFrame(index=df.index)
    dane["cod_divipola"] = (
        pd.to_numeric(df["mpio"], errors="coerce")
        .astype("Int64")
        .astype(str)
        .str.replace("<NA>", "", regex=False)
        .str.zfill(5)
    )
    dane["municipio"] = df["dpmp"].apply(clean_text)
    dane["departamento"] = df["dpnom"].apply(clean_text)
    dane["anio"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")
    dane["area_geografica"] = df["area_geografica"].apply(clean_text)
    dane["poblacion"] = pd.to_numeric(df["total"], errors="coerce")

    # limpiar filas vacías
    dane = dane[
        dane["cod_divipola"].ne("") &
        dane["anio"].notna() &
        dane["poblacion"].notna()
    ].copy()

    # filtrar años objetivo
    dane = dane[dane["anio"].isin(TARGET_YEARS)].copy()

    # quedarnos con TOTAL
    dane = dane[dane["area_geografica"].fillna("").str.contains("TOTAL", na=False)].copy()

    # filtrar municipios foco
    dane = dane[dane["cod_divipola"].isin(TARGET_CODES.keys())].copy()

    # normalizar nombres finales
    dane["municipio"] = dane["cod_divipola"].map(TARGET_CODES)
    dane["departamento"] = "NARINO"

    dane_final = dane[
        ["cod_divipola", "municipio", "departamento", "anio", "poblacion"]
    ].sort_values(["cod_divipola", "anio"]).reset_index(drop=True)

    dane_final.to_csv(
        OUT_DIR / "dane_poblacion_2023_2025_galeras.csv",
        index=False,
        encoding="utf-8-sig"
    )

    resumen = (
        dane_final.groupby("municipio", as_index=False)["poblacion"]
        .sum()
        .sort_values("municipio")
    )
    resumen.to_csv(
        OUT_DIR / "dane_resumen_poblacion.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("\nArchivos generados:")
    print("-", OUT_DIR / "dane_poblacion_2023_2025_galeras.csv")
    print("-", OUT_DIR / "dane_resumen_poblacion.csv")

if __name__ == "__main__":
    main()