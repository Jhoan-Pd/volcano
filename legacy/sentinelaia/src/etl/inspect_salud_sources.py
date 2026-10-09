from pathlib import Path
import pandas as pd
import unicodedata
import re

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw" / "salud"
OUT_DIR = BASE_DIR / "data" / "processed" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    RAW_DIR / "Datos_2023_998.xlsx",
    RAW_DIR / "Datos_2024_346.xlsx",
    RAW_DIR / "Datos_2024_998.xlsx",
]

def normalize_text(text):
    text = str(text).strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")

def detect_key_columns(columns):
    columns_lower = [c.lower() for c in columns]

    patterns = {
        "cod_divipola": ["divipola", "codigo_municipio", "cod_mpio", "cod_municipio", "codigo"],
        "municipio": ["municipio", "nom_mpio", "nombre_municipio", "mpio"],
        "departamento": ["departamento", "depto", "nom_depto"],
        "fecha": ["fecha", "fecha_notificacion", "fecha_evento", "fecha_consulta"],
        "anio": ["anio", "ano", "vigencia", "year"],
        "semana_epidemiologica": ["semana_epidemiologica", "semana_epi", "semana", "sem_epi"],
        "casos": ["casos", "n_casos", "cantidad", "conteo", "frecuencia", "total"],
        "sexo": ["sexo"],
        "edad": ["edad"],
    }

    results = []
    for key, candidates in patterns.items():
        found = [col for col in columns_lower if any(c in col for c in candidates)]
        results.append({
            "tipo_variable": key,
            "columnas_detectadas": " | ".join(found)
        })
    return pd.DataFrame(results)

def inspect_excel(file_path: Path):
    print("=" * 90)
    print(f"Archivo: {file_path.name}")
    print("=" * 90)

    xls = pd.ExcelFile(file_path)
    print("Hojas encontradas:")
    for i, sheet in enumerate(xls.sheet_names, start=1):
        print(f"  {i}. {sheet}")

    summary_rows = []

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        except Exception as e:
            print(f"[ERROR] Hoja {sheet_name}: {e}")
            continue

        print("\n" + "-" * 90)
        print(f"Hoja: {sheet_name}")
        print(f"Filas: {df.shape[0]} | Columnas: {df.shape[1]}")
        print("-" * 90)

        original_cols = [str(c) for c in df.columns.tolist()]
        normalized_cols = [normalize_text(c) for c in original_cols]

        print("Columnas:")
        for col in original_cols:
            print(f"  - {col}")

        print("\nPrimeras 5 filas:")
        print(df.head().to_string())

        summary_cols = pd.DataFrame({
            "archivo": file_path.name,
            "hoja": sheet_name,
            "columna_original": original_cols,
            "columna_normalizada": normalized_cols,
            "tipo_dato": [str(df[col].dtype) for col in df.columns],
            "n_nulos": [int(df[col].isna().sum()) for col in df.columns],
            "n_unicos": [int(df[col].nunique(dropna=True)) for col in df.columns],
        })

        key_cols = detect_key_columns(normalized_cols)
        key_cols["archivo"] = file_path.name
        key_cols["hoja"] = sheet_name

        out_cols = OUT_DIR / f"{file_path.stem}__{normalize_text(sheet_name)}__columnas.csv"
        out_keys = OUT_DIR / f"{file_path.stem}__{normalize_text(sheet_name)}__claves.csv"
        out_preview = OUT_DIR / f"{file_path.stem}__{normalize_text(sheet_name)}__preview.csv"

        summary_cols.to_csv(out_cols, index=False, encoding="utf-8-sig")
        key_cols.to_csv(out_keys, index=False, encoding="utf-8-sig")
        df.head(20).to_csv(out_preview, index=False, encoding="utf-8-sig")

        summary_rows.append({
            "archivo": file_path.name,
            "hoja": sheet_name,
            "n_filas": df.shape[0],
            "n_columnas": df.shape[1],
            "archivo_columnas": out_cols.name,
            "archivo_claves": out_keys.name,
            "archivo_preview": out_preview.name,
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_file = OUT_DIR / f"{file_path.stem}__resumen_hojas.csv"
    summary_df.to_csv(summary_file, index=False, encoding="utf-8-sig")
    print(f"\nResumen guardado en: {summary_file}")

def main():
    for file_path in FILES:
        if file_path.exists():
            inspect_excel(file_path)
        else:
            print(f"[NO ENCONTRADO] {file_path}")

if __name__ == "__main__":
    main()