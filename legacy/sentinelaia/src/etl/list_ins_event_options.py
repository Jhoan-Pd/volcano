from pathlib import Path
import csv
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_DIR = BASE_DIR / "data" / "processed" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

possible_browsers = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

browser_path = None
for path in possible_browsers:
    if Path(path).exists():
        browser_path = path
        break

if browser_path is None:
    raise FileNotFoundError("No se encontró Chrome ni Edge instalado.")

print(f"Navegador encontrado: {browser_path}")

options = Options()
options.binary_location = browser_path

driver = webdriver.Chrome(options=options)

KEYWORDS = [
    "ira",
    "eda",
    "respir",
    "diarre",
    "gastro",
    "346",
    "998",
]

def clean_text(text):
    return " ".join((text or "").split()).strip()

try:
    driver.get("https://portalsivigila.ins.gov.co/")
    print("Portal abierto:", driver.current_url)
    time.sleep(5)

    print("\nHaz esto manualmente:")
    print("1. Haz clic en 'Microdatos'")
    print("2. Quédate en la página del buscador")
    print("3. Luego vuelve aquí y presiona Enter")
    input("\nPresiona Enter cuando estés en el buscador... ")

    time.sleep(2)

    evento_select = Select(driver.find_element(By.ID, "lstEvento"))

    rows = []
    for i, opt in enumerate(evento_select.options, start=1):
        text = clean_text(opt.text)
        value = opt.get_attribute("value") or ""
        combined = f"{text} {value}".lower()
        relevant = any(k in combined for k in KEYWORDS)

        rows.append({
            "indice": i,
            "text": text,
            "value": value,
            "relevant": relevant,
        })

    out_file = OUT_DIR / "ins_event_options.csv"
    with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["indice", "text", "value", "relevant"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nArchivo generado: {out_file}")
    print(f"Total opciones: {len(rows)}")

    relevantes = [r for r in rows if r["relevant"]]
    print("\nOpciones candidatas para IRA / EDA:")
    for row in relevantes:
        print(f"- indice={row['indice']} | value={row['value']!r} | text={row['text']!r}")

    input("\nPresiona Enter para cerrar el navegador... ")

finally:
    driver.quit()