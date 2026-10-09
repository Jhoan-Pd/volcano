from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
FINAL_DIR = BASE_DIR / "data" / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

SALUD_FILE = PROCESSED_DIR / "salud_municipio_semana.csv"
DANE_FILE = PROCESSED_DIR / "dane_poblacion_2023_2025_galeras.csv"

TARGET_CODES = {
    "52001": "PASTO",
    "52207": "CONSACA",
    "52381": "LA FLORIDA",
    "52480": "NARINO",
    "52683": "SANDONA",
    "52885": "YACUANQUER",
}

EVENTO_ORIGEN = {
    "EDA": "MORBILIDAD POR EDA",
    "IRA": "MORBILIDAD POR IRA",
}


def build_grid(eventos, years, weeks):
    """Construye el grid completo municipio × año × semana × evento."""
    frames = []
    for evento in eventos:
        g = pd.MultiIndex.from_product(
            [list(TARGET_CODES.keys()), years, weeks],
            names=["cod_divipola", "anio", "semana_epidemiologica"],
        ).to_frame(index=False)
        g["municipio"] = g["cod_divipola"].map(TARGET_CODES)
        g["departamento"] = "NARINO"
        g["evento_estandar"] = evento
        g["evento_origen"] = EVENTO_ORIGEN.get(evento, evento)
        frames.append(g)
    return pd.concat(frames, ignore_index=True)


def main():
    if not SALUD_FILE.exists():
        raise FileNotFoundError(f"No existe: {SALUD_FILE}")
    if not DANE_FILE.exists():
        raise FileNotFoundError(f"No existe: {DANE_FILE}")

    salud = pd.read_csv(SALUD_FILE)
    dane = pd.read_csv(DANE_FILE)

    salud["cod_divipola"] = salud["cod_divipola"].astype(str).str.zfill(5)
    salud["anio"] = pd.to_numeric(salud["anio"], errors="coerce").astype("Int64")
    salud["semana_epidemiologica"] = pd.to_numeric(
        salud["semana_epidemiologica"], errors="coerce"
    ).astype("Int64")
    salud["casos"] = pd.to_numeric(salud["casos"], errors="coerce").fillna(0)

    dane["cod_divipola"] = dane["cod_divipola"].astype(str).str.zfill(5)
    dane["anio"] = pd.to_numeric(dane["anio"], errors="coerce").astype("Int64")
    dane["poblacion"] = pd.to_numeric(dane["poblacion"], errors="coerce")

    # Incluir EDA e IRA; descartar variantes secundarias (IRA_VIRUS_NUEVO_346, etc.)
    salud = salud[salud["evento_estandar"].isin(["EDA", "IRA"])].copy()

    eventos = sorted(salud["evento_estandar"].dropna().unique().tolist())
    years = sorted(salud["anio"].dropna().unique().tolist())
    weeks = list(range(1, 53))

    grid = build_grid(eventos, years, weeks)

    salud_merge = salud[
        [
            "evento_estandar",
            "evento_origen",
            "cod_divipola",
            "municipio",
            "departamento",
            "anio",
            "semana_epidemiologica",
            "casos",
        ]
    ].copy()

    dataset = grid.merge(
        salud_merge,
        on=[
            "evento_estandar",
            "evento_origen",
            "cod_divipola",
            "municipio",
            "departamento",
            "anio",
            "semana_epidemiologica",
        ],
        how="left",
    )

    dataset["casos"] = dataset["casos"].fillna(0)

    dataset = dataset.merge(
        dane[["cod_divipola", "anio", "poblacion"]],
        on=["cod_divipola", "anio"],
        how="left",
    )

    dataset["tasa_x_100k"] = (dataset["casos"] / dataset["poblacion"]) * 100000
    dataset["tasa_x_100k"] = dataset["tasa_x_100k"].round(4)

    dataset = dataset.sort_values(
        ["evento_estandar", "cod_divipola", "anio", "semana_epidemiologica"]
    ).reset_index(drop=True)

    # Salida combinada (IRA + EDA)
    combined_path = FINAL_DIR / "dataset_final_municipio_semana.csv"
    dataset.to_csv(combined_path, index=False, encoding="utf-8-sig")

    # Salidas por evento
    for evento in eventos:
        subset = dataset[dataset["evento_estandar"] == evento].copy()
        slug = evento.lower()
        subset.to_csv(
            FINAL_DIR / f"dataset_final_{slug}_municipio_semana.csv",
            index=False,
            encoding="utf-8-sig",
        )

    resumen = (
        dataset.groupby(["evento_estandar", "municipio", "anio"], as_index=False)
        .agg(
            casos_totales=("casos", "sum"),
            poblacion=("poblacion", "max"),
            tasa_anual_x_100k=("tasa_x_100k", "sum"),
        )
        .sort_values(["evento_estandar", "municipio", "anio"])
    )
    resumen.to_csv(
        FINAL_DIR / "resumen_final_anual.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("Archivos generados:")
    print("-", combined_path)
    for evento in eventos:
        slug = evento.lower()
        print("-", FINAL_DIR / f"dataset_final_{slug}_municipio_semana.csv")
    print("-", FINAL_DIR / "resumen_final_anual.csv")

    print(f"\nEventos: {eventos}")
    print(f"Total filas: {len(dataset):,}")
    for evento in eventos:
        n = (dataset["evento_estandar"] == evento).sum()
        print(f"  {evento}: {n:,} filas")


if __name__ == "__main__":
    main()
