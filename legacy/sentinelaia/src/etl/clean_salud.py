import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import pandas as pd
import unicodedata
import re

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw" / "salud"
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

# Mapeo sufijo de archivo → evento estándar
# Soporta naming legacy (Datos_YYYY_998.xlsx) y nuevo (EDA_YYYY_998.xlsx / IRA_YYYY_995.xlsx)
SUFFIX_TO_EVENTO = {
    "_998.xlsx": "EDA",
    "_995.xlsx": "IRA",
    "_346.xlsx": "IRA_VIRUS_NUEVO_346",
}

EVENTO_ORIGEN_DEFAULT = {
    "EDA": "MORBILIDAD POR EDA",
    "IRA": "MORBILIDAD POR IRA",
    "IRA_VIRUS_NUEVO_346": "IRA POR VIRUS NUEVO",
}


def clean_text(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("utf-8")
    value = re.sub(r"\s+", " ", value)
    return value.upper()


def normalize_col(col):
    col = str(col).strip()
    col = unicodedata.normalize("NFKD", col).encode("ascii", "ignore").decode("utf-8")
    col = col.lower()
    col = re.sub(r"[^a-z0-9]+", "_", col)
    return col.strip("_")


def safe_to_datetime(series):
    return pd.to_datetime(series, errors="coerce")


def safe_to_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def zfill_series(series, n):
    return series.astype("Int64").astype(str).str.replace("<NA>", "", regex=False).str.zfill(n)


def build_divipola(depto_series, mun_series):
    depto = safe_to_numeric(depto_series)
    mun = safe_to_numeric(mun_series)
    return zfill_series(depto, 2) + zfill_series(mun, 3)


def find_first_existing(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def process_morbidity_file(path: Path, evento_estandar: str):
    """Procesa un archivo de morbilidad Sivigila (EDA código 998, IRA código 995).
    Ambos tienen la misma estructura de columnas en los microdatos del INS.
    """
    xls = pd.ExcelFile(path)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [normalize_col(c) for c in df.columns]

    col_cod = find_first_existing(df, ["cod_mun", "cod_mun_"])
    col_fecha = find_first_existing(df, ["fec_not"])
    col_semana = find_first_existing(df, ["semana"])
    col_anio = find_first_existing(df, ["ano", "a_o", "anio"])
    col_casos = find_first_existing(df, ["cas_conc"])
    col_hombres = find_first_existing(df, ["hombres"])
    col_mujeres = find_first_existing(df, ["mujeres"])
    col_mun = find_first_existing(df, ["nmun_proce", "nmun_notif"])
    col_dep = find_first_existing(df, ["ndep_proce", "ndep_notif"])
    col_evento = find_first_existing(df, ["nom_eve"])

    # If week and year columns are both missing it's a UPGD characterization file, not case data
    if col_semana is None and col_anio is None:
        print(f"  [OMITIDO] {path.name} — no contiene columnas de semana/año (parece ser un archivo UPGD de caracterización, no microdatos de casos)")
        return None

    out = pd.DataFrame(index=df.index)
    out["fuente_archivo"] = path.name
    out["evento_estandar"] = evento_estandar
    out["evento_origen"] = (
        df[col_evento].astype(str) if col_evento
        else EVENTO_ORIGEN_DEFAULT.get(evento_estandar, evento_estandar)
    )

    out["cod_divipola"] = (
        safe_to_numeric(df[col_cod]).astype("Int64").astype(str)
        .str.replace("<NA>", "", regex=False).str.zfill(5)
    )
    out["fecha_evento"] = safe_to_datetime(df[col_fecha]) if col_fecha else pd.NaT
    out["anio"] = (
        safe_to_numeric(df[col_anio]) if col_anio
        else out["fecha_evento"].dt.year
    )
    out["semana_epidemiologica"] = (
        safe_to_numeric(df[col_semana]) if col_semana
        else out["fecha_evento"].dt.isocalendar().week.astype("Int64")
    )
    out["departamento"] = df[col_dep].apply(clean_text) if col_dep else None
    out["municipio"] = df[col_mun].apply(clean_text) if col_mun else None

    _zeros = pd.Series(0, index=df.index, dtype=float)
    if col_casos:
        out["casos"] = safe_to_numeric(df[col_casos])
    else:
        hombres = safe_to_numeric(df[col_hombres]) if col_hombres else _zeros
        mujeres = safe_to_numeric(df[col_mujeres]) if col_mujeres else _zeros
        out["casos"] = hombres.fillna(0) + mujeres.fillna(0)

    if col_hombres or col_mujeres:
        hombres = safe_to_numeric(df[col_hombres]) if col_hombres else _zeros
        mujeres = safe_to_numeric(df[col_mujeres]) if col_mujeres else _zeros
        total_hm = hombres.fillna(0) + mujeres.fillna(0)
        out["casos"] = out["casos"].fillna(total_hm)

    return out


def process_346_file(path: Path):
    xls = pd.ExcelFile(path)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [normalize_col(c) for c in df.columns]

    col_mun_code = find_first_existing(df, ["cod_mun_n"])
    col_dep_code = find_first_existing(df, ["cod_dpto_n"])
    col_fecha = find_first_existing(df, ["fec_not", "fec_con", "ini_sin"])
    col_semana = find_first_existing(df, ["semana"])
    col_anio = find_first_existing(df, ["ano", "anio"])
    col_mun = find_first_existing(df, ["municipio_notificacion"])
    col_dep = find_first_existing(df, ["departamento_notificacion"])
    col_evento = find_first_existing(df, ["nombre_evento"])
    col_confirmados = find_first_existing(df, ["confirmados"])

    out = pd.DataFrame(index=df.index)
    out["fuente_archivo"] = path.name
    out["evento_estandar"] = "IRA_VIRUS_NUEVO_346"
    out["evento_origen"] = df[col_evento].astype(str) if col_evento else "IRA POR VIRUS NUEVO"
    out["cod_divipola"] = build_divipola(df[col_dep_code], df[col_mun_code])
    out["fecha_evento"] = safe_to_datetime(df[col_fecha]) if col_fecha else pd.NaT
    out["anio"] = safe_to_numeric(df[col_anio]) if col_anio else out["fecha_evento"].dt.year
    out["semana_epidemiologica"] = (
        safe_to_numeric(df[col_semana]) if col_semana
        else out["fecha_evento"].dt.isocalendar().week.astype("Int64")
    )
    out["departamento"] = df[col_dep].apply(clean_text) if col_dep else None
    out["municipio"] = df[col_mun].apply(clean_text) if col_mun else None
    out["casos"] = safe_to_numeric(df[col_confirmados]).fillna(1) if col_confirmados else 1

    return out


def detect_evento(path: Path):
    """Determina el evento estándar a partir del sufijo del nombre de archivo."""
    name = path.name
    for suffix, evento in SUFFIX_TO_EVENTO.items():
        if name.endswith(suffix):
            return evento
    return None


def discover_files():
    """Descubre todos los xlsx de salud en RAW_DIR por sufijo, sin hardcodear nombres."""
    found = []
    for path in sorted(RAW_DIR.glob("*.xlsx")):
        evento = detect_evento(path)
        if evento is not None:
            found.append((path, evento))
        else:
            print(f"  [OMITIDO] {path.name} — sufijo no reconocido")
    return found


def filter_target_codes(df):
    return df[df["cod_divipola"].isin(TARGET_CODES.keys())].copy()


def fill_target_names(df):
    df["municipio"] = df["cod_divipola"].map(TARGET_CODES)
    df["departamento"] = "NARINO"
    return df


def aggregate_weekly(df):
    keys = [
        "evento_estandar", "evento_origen", "cod_divipola",
        "municipio", "departamento", "anio", "semana_epidemiologica",
    ]
    return (
        df.groupby(keys, dropna=False, as_index=False)["casos"]
        .sum()
        .sort_values(["evento_estandar", "cod_divipola", "anio", "semana_epidemiologica"])
    )


def main():
    files = discover_files()

    if not files:
        print(f"[ADVERTENCIA] No se encontraron archivos xlsx en {RAW_DIR}")
        print("  Ejecuta primero: python src/etl/download_ins_dataset.py")
        return

    frames = []
    for path, evento in files:
        print(f"[PROCESANDO] {path.name} → evento={evento}")
        if evento == "IRA_VIRUS_NUEVO_346":
            df = process_346_file(path)
        else:
            df = process_morbidity_file(path, evento)
        if df is None:
            continue
        frames.append(df)

    if not frames:
        print("\n[ADVERTENCIA] Ningún archivo contenía microdatos de casos procesables.")
        print("  Los archivos IRA_*_995.xlsx descargados son reportes UPGD (caracterización de unidades),")
        print("  no microdatos de casos. Para datos de casos IRA descarga el evento 'Infección Respiratoria Aguda'")
        print("  desde el portal de Datos Abiertos del INS o usa el dataset existente en data/final/.")
        return

    salud = pd.concat(frames, ignore_index=True)

    salud["anio"] = safe_to_numeric(salud["anio"]).astype("Int64")
    salud["semana_epidemiologica"] = safe_to_numeric(salud["semana_epidemiologica"]).astype("Int64")
    salud["casos"] = safe_to_numeric(salud["casos"]).fillna(0)
    salud["cod_divipola"] = salud["cod_divipola"].astype(str).str.zfill(5)

    salud_foco = filter_target_codes(salud)
    salud_foco = fill_target_names(salud_foco)

    salud_foco.to_csv(OUT_DIR / "salud_estandarizada_filas.csv", index=False, encoding="utf-8-sig")

    salud_municipio_semana = aggregate_weekly(salud_foco)
    salud_municipio_semana.to_csv(OUT_DIR / "salud_municipio_semana.csv", index=False, encoding="utf-8-sig")

    # Exportes por evento
    for evento in salud_municipio_semana["evento_estandar"].unique():
        subset = salud_municipio_semana[salud_municipio_semana["evento_estandar"] == evento].copy()
        slug = evento.lower().replace("_", "")
        subset.to_csv(OUT_DIR / f"{slug}_municipio_semana.csv", index=False, encoding="utf-8-sig")

    resumen = (
        salud_municipio_semana.groupby(["evento_estandar", "municipio"], dropna=False, as_index=False)["casos"]
        .sum()
        .sort_values(["evento_estandar", "municipio"])
    )
    resumen.to_csv(OUT_DIR / "resumen_salud_municipios.csv", index=False, encoding="utf-8-sig")

    print("\nArchivos generados:")
    print("-", OUT_DIR / "salud_estandarizada_filas.csv")
    print("-", OUT_DIR / "salud_municipio_semana.csv")
    for evento in salud_municipio_semana["evento_estandar"].unique():
        slug = evento.lower().replace("_", "")
        print("-", OUT_DIR / f"{slug}_municipio_semana.csv")
    print("-", OUT_DIR / "resumen_salud_municipios.csv")

    eventos_procesados = salud_municipio_semana["evento_estandar"].unique().tolist()
    print(f"\nEventos procesados: {eventos_procesados}")
    print(f"Total filas: {len(salud_municipio_semana):,}")


if __name__ == "__main__":
    main()
