from pathlib import Path
import csv
import time
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

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
    "2023",
    "2024",
    "2025",
    "ira",
    "eda",
    "346",
    "998",
    ".xlsx",
    ".xls",
    ".csv",
]

def looks_relevant(text: str, href: str) -> bool:
    combined = f"{text} {href}".lower()
    return any(k in combined for k in KEYWORDS)

try:
    # Abrimos el portal principal
    driver.get("https://portalsivigila.ins.gov.co/")
    print("Portal abierto:", driver.current_url)

    # Da tiempo a que cargue
    time.sleep(5)

    print("\nAhora haz esto manualmente en el navegador que se abrió:")
    print("1. Haz clic en 'Microdatos'")
    print("2. Si ves una página con archivos/listado, déjala abierta")
    print("3. Cuando estés en esa página, vuelve aquí y presiona Enter")
    input("\nPresiona Enter cuando ya estés en la página correcta... ")

    time.sleep(2)

    current_url = driver.current_url
    print("\nURL actual:", current_url)

    anchors = driver.find_elements(By.TAG_NAME, "a")

    rows = []
    for a in anchors:
        try:
            text = (a.text or "").strip()
            href = (a.get_attribute("href") or "").strip()

            if href:
                href = urljoin(current_url, href)

            rows.append({
                "page_url": current_url,
                "text": text,
                "href": href,
                "relevant": looks_relevant(text, href),
            })
        except Exception:
            continue

    # Guardar todo
    all_links_file = OUT_DIR / "ins_all_links.csv"
    with open(all_links_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["page_url", "text", "href", "relevant"])
        writer.writeheader()
        writer.writerows(rows)

    # Guardar filtrados
    filtered = [r for r in rows if r["relevant"]]
    filtered_file = OUT_DIR / "ins_candidate_links.csv"
    with open(filtered_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["page_url", "text", "href", "relevant"])
        writer.writeheader()
        writer.writerows(filtered)

    print("\nResumen:")
    print(f"Total links encontrados: {len(rows)}")
    print(f"Links candidatos: {len(filtered)}")
    print(f"Archivo completo: {all_links_file}")
    print(f"Archivo filtrado: {filtered_file}")

    print("\nPrimeros links candidatos:")
    for i, row in enumerate(filtered[:20], start=1):
        print(f"{i}. text={row['text']!r}")
        print(f"   href={row['href']}")
        print()

    input("Presiona Enter para cerrar el navegador... ")

finally:
    driver.quit()