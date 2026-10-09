"""
SentinelaIA Nariño — Descarga automática de microdatos Sivigila (INS)
Descarga IRA (995) + EDA (998) para los años 2023, 2024 y 2025.

Ejecutar desde BI_Health_Nari-o/:
    python src/etl/download_ins_dataset.py

Requiere: selenium, requests
    pip install selenium requests
"""

from pathlib import Path
import time
import requests
import csv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw" / "salud"
REPORTS_DIR = BASE_DIR / "data" / "processed" / "reports"
RAW_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Todos los eventos y años a descargar
DOWNLOAD_TARGETS = [
    ("Morbilidad por IRA", "2023", "IRA_2023_995.xlsx"),
    ("Morbilidad por IRA", "2024", "IRA_2024_995.xlsx"),
    ("Morbilidad por IRA", "2025", "IRA_2025_995.xlsx"),
    ("Morbilidad por EDA", "2023", "EDA_2023_998.xlsx"),
    ("Morbilidad por EDA", "2024", "EDA_2024_998.xlsx"),
    ("Morbilidad por EDA", "2025", "EDA_2025_998.xlsx"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SentinelaIA-Narino/1.0"
}

possible_browsers = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def get_browser_path():
    for path in possible_browsers:
        if Path(path).exists():
            return path
    raise FileNotFoundError("No se encontró Chrome ni Edge instalado.")


def clean_text(text):
    return " ".join((text or "").split()).strip()


def download_file(url: str, output_path: Path):
    response = requests.get(url, headers=HEADERS, timeout=120, stream=True)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)


def save_report(row: dict):
    report_file = REPORTS_DIR / "ins_download_log.csv"
    exists = report_file.exists()
    with open(report_file, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["event_name", "year_value", "output_file", "result_href", "status"],
        )
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def click_buscar(driver):
    selectors = [
        (By.XPATH, "//button[contains(normalize-space(.), 'Buscar')]"),
        (By.XPATH, "//input[contains(@value, 'Buscar')]"),
        (By.XPATH, "//*[contains(normalize-space(.), 'Buscar')]"),
    ]
    for by, selector in selectors:
        for el in driver.find_elements(by, selector):
            try:
                if el.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", el)
                    return True
            except Exception:
                continue
    return False


def dump_debug(driver, stage_name: str):
    html_file = REPORTS_DIR / f"ins_debug_{stage_name}.html"
    screenshot_file = REPORTS_DIR / f"ins_debug_{stage_name}.png"
    html_file.write_text(driver.page_source, encoding="utf-8")
    driver.save_screenshot(str(screenshot_file))
    print(f"  Debug guardado: {html_file}")


def find_result_link(driver):
    candidate_xpaths = [
        "//a[contains(@href, '.xlsx')]",
        "//a[contains(translate(normalize-space(.), 'XLSX', 'xlsx'), 'xlsx')]",
        "//a[contains(., 'Datos_')]",
        "//*[contains(normalize-space(.), 'Datos_')]/ancestor::a[1]",
        "//*[contains(normalize-space(.), 'Formato')]/following::a[1]",
    ]
    for xpath in candidate_xpaths:
        for el in driver.find_elements(By.XPATH, xpath):
            try:
                href = el.get_attribute("href") or ""
                if href:
                    return clean_text(el.text), href
            except Exception:
                continue
    return None, None


def download_one(driver, event_name: str, year_value: str, output_name: str) -> bool:
    """Descarga un archivo del portal INS. Retorna True si fue exitoso."""
    output_path = RAW_DIR / output_name
    if output_path.exists():
        print(f"  [EXISTENTE] {output_name} — omitiendo")
        return True

    print(f"\n  Descargando: {event_name} {year_value} → {output_name}")

    driver.get("https://portalsivigila.ins.gov.co/Paginas/Buscador.aspx")
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.ID, "lstEvento")))
    wait.until(EC.presence_of_element_located((By.ID, "lstYear")))

    try:
        Select(driver.find_element(By.ID, "lstEvento")).select_by_visible_text(event_name)
    except NoSuchElementException:
        print(f"  [OMITIDO] Evento '{event_name}' no disponible en el portal")
        save_report({"event_name": event_name, "year_value": year_value,
                     "output_file": output_name, "result_href": "", "status": "SKIP_NO_EVENT"})
        return True

    try:
        Select(driver.find_element(By.ID, "lstYear")).select_by_visible_text(year_value)
    except NoSuchElementException:
        print(f"  [OMITIDO] Año {year_value} no disponible para '{event_name}' — puede que aún no esté publicado")
        save_report({"event_name": event_name, "year_value": year_value,
                     "output_file": output_name, "result_href": "", "status": "SKIP_NO_YEAR"})
        return True
    time.sleep(2)

    if not click_buscar(driver):
        print(f"  [ERROR] No se pudo hacer clic en Buscar para {event_name} {year_value}")
        save_report({"event_name": event_name, "year_value": year_value,
                     "output_file": output_name, "result_href": "", "status": "ERROR_BUSCAR"})
        return False

    time.sleep(5)

    result_text, result_href = find_result_link(driver)
    if not result_href:
        stage = f"{event_name.replace(' ', '_')}_{year_value}"
        dump_debug(driver, stage)
        print(f"  [ERROR] No se encontró enlace de descarga — ver debug en reports/")
        save_report({"event_name": event_name, "year_value": year_value,
                     "output_file": output_name, "result_href": "", "status": "ERROR_NO_LINK"})
        return False

    download_file(result_href, output_path)
    print(f"  [OK] Guardado en: {output_path}")
    save_report({"event_name": event_name, "year_value": year_value,
                 "output_file": output_name, "result_href": result_href, "status": "OK"})
    return True


def main():
    print("=" * 60)
    print("  SentinelaIA Nariño — Descarga Sivigila (INS)")
    print("=" * 60)

    browser_path = get_browser_path()
    print(f"Navegador: {browser_path}")

    options = Options()
    options.binary_location = browser_path

    driver = webdriver.Chrome(options=options)

    results = {"ok": 0, "skip": 0, "error": 0}

    try:
        for event_name, year_value, output_name in DOWNLOAD_TARGETS:
            output_path = RAW_DIR / output_name
            if output_path.exists():
                print(f"\n  [EXISTENTE] {output_name}")
                results["skip"] += 1
                continue
            ok = download_one(driver, event_name, year_value, output_name)
            if ok:
                results["ok"] += 1
            else:
                results["error"] += 1
            time.sleep(2)
    finally:
        driver.quit()

    print("\n" + "=" * 60)
    print(f"  Descargados: {results['ok']} | Existentes: {results['skip']} | Errores: {results['error']}")
    print(f"  Archivos en: {RAW_DIR}")
    print(f"  Log en: {REPORTS_DIR / 'ins_download_log.csv'}")
    print("  Próximo paso: python src/etl/clean_salud.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
