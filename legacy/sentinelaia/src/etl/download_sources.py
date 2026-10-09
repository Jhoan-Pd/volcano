from pathlib import Path
import sys
import time
import requests

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw"

TIMEOUT = 120
CHUNK_SIZE = 1024 * 512
RETRIES = 3
SLEEP_BETWEEN_RETRIES = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SentinelaIA-Narino/1.0"
}

SOURCES = [
    {
        "name": "divipola_municipios",
        "category": "territorio",
        "status": "active",
        "url": "https://geoportal.dane.gov.co/descargas/divipola/DIVIPOLA_Municipios.xlsx",
        "filename": "DIVIPOLA_Municipios.xlsx",
        "description": "Catalogo oficial DIVIPOLA municipios"
    },
    {
        "name": "poblacion_municipal",
        "category": "dane",
        "status": "active",
        "url": "https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2018-2042_VP.xlsx",
        "filename": "poblacion_municipal.xlsx",
        "description": "Proyecciones de poblacion municipal DANE"
    },

    # INS / Sivigila recientes:
    # Se dejan como pending hasta resolver descarga automatica oficial
    # desde Microdatos o Buscador.
    {
        "name": "ins_microdatos_2023_2025",
        "category": "salud",
        "status": "pending",
        "url": "",
        "filename": "README_INS_PENDIENTE.txt",
        "description": "Pendiente: descarga automatica desde Portal Sivigila Microdatos"
    },
]

def ensure_dirs():
    (RAW_DIR / "territorio").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "dane").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "salud").mkdir(parents=True, exist_ok=True)

def get_output_path(source: dict) -> Path:
    return RAW_DIR / source["category"] / source["filename"]

def human_size(num_bytes: int) -> str:
    if num_bytes is None:
        return "desconocido"
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024

def should_skip_download(output_path: Path) -> bool:
    return output_path.exists() and output_path.stat().st_size > 0

def download_file(url: str, output_path: Path):
    last_error = None

    for attempt in range(1, RETRIES + 1):
        try:
            with requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT) as response:
                response.raise_for_status()

                content_length = response.headers.get("Content-Length")
                total_bytes = int(content_length) if content_length and content_length.isdigit() else None

                tmp_path = output_path.with_suffix(output_path.suffix + ".part")
                downloaded = 0

                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                tmp_path.replace(output_path)
                print(f"    OK: {output_path.name} | tamaño: {human_size(downloaded if downloaded else total_bytes)}")
                return True

        except Exception as e:
            last_error = e
            print(f"    intento {attempt}/{RETRIES} falló: {e}")
            if attempt < RETRIES:
                time.sleep(SLEEP_BETWEEN_RETRIES)

    raise last_error

def write_pending_readme():
    readme_path = RAW_DIR / "salud" / "README_INS_PENDIENTE.txt"
    content = """Portal INS pendiente de automatizacion.
Fuente oficial:
- https://portalsivigila.ins.gov.co/
- https://portalsivigila.ins.gov.co/Paginas/Buscador.aspx
- https://portalsivigila.ins.gov.co/Microdatos/Forms/AllItems.aspx

Pendiente resolver:
- IRA 2024
- EDA 2024
- IRA 2025
- EDA 2025

Nota:
No usar URLs inventadas. La descarga reciente debe salir del portal oficial.
"""
    readme_path.write_text(content, encoding="utf-8")
    print(f"    OK: archivo de pendiente creado -> {readme_path}")

def print_header():
    print("=" * 70)
    print("SentinelaIA Nariño - Descarga automática de fuentes")
    print("=" * 70)
    print(f"Directorio base: {BASE_DIR}")
    print(f"Directorio raw : {RAW_DIR}")
    print()

def print_summary(downloaded, skipped, pending, failed):
    print()
    print("=" * 70)
    print("Resumen")
    print("=" * 70)
    print(f"Descargados : {downloaded}")
    print(f"Saltados    : {skipped}")
    print(f"Pendientes  : {pending}")
    print(f"Fallidos    : {failed}")
    print("=" * 70)

def main():
    ensure_dirs()
    print_header()

    downloaded = 0
    skipped = 0
    pending = 0
    failed = 0

    for source in SOURCES:
        name = source["name"]
        status = source["status"]
        output_path = get_output_path(source)
        description = source.get("description", "")

        print(f"[{name}]")
        print(f"  descripción: {description}")
        print(f"  salida     : {output_path}")

        if status == "pending" or not source.get("url"):
            if source["category"] == "salud":
                write_pending_readme()
            else:
                print("    PENDIENTE: falta URL directa oficial")
            pending += 1
            print()
            continue

        if should_skip_download(output_path):
            print("    SKIP: ya existe")
            skipped += 1
            print()
            continue

        try:
            download_file(source["url"], output_path)
            downloaded += 1
        except Exception as e:
            print(f"    ERROR: no se pudo descargar -> {e}")
            failed += 1

        print()

    print_summary(downloaded, skipped, pending, failed)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()