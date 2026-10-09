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

def safe_attr(el, name):
    try:
        return el.get_attribute(name)
    except Exception:
        return ""

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
    print("\nURL actual:", driver.current_url)
    print("Título:", driver.title)

    elements_rows = []

    # INPUTS
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for i, el in enumerate(inputs, start=1):
        elements_rows.append({
            "tipo_elemento": "input",
            "indice": i,
            "tag": "input",
            "type": safe_attr(el, "type"),
            "id": safe_attr(el, "id"),
            "name": safe_attr(el, "name"),
            "class": safe_attr(el, "class"),
            "value": safe_attr(el, "value"),
            "placeholder": safe_attr(el, "placeholder"),
            "text": clean_text(el.text),
        })

    # SELECTS + OPTIONS
    selects = driver.find_elements(By.TAG_NAME, "select")
    for i, el in enumerate(selects, start=1):
        row = {
            "tipo_elemento": "select",
            "indice": i,
            "tag": "select",
            "type": "",
            "id": safe_attr(el, "id"),
            "name": safe_attr(el, "name"),
            "class": safe_attr(el, "class"),
            "value": safe_attr(el, "value"),
            "placeholder": "",
            "text": clean_text(el.text),
        }
        elements_rows.append(row)

        try:
            sel = Select(el)
            for j, opt in enumerate(sel.options, start=1):
                elements_rows.append({
                    "tipo_elemento": "select_option",
                    "indice": f"{i}.{j}",
                    "tag": "option",
                    "type": "",
                    "id": safe_attr(el, "id"),
                    "name": safe_attr(el, "name"),
                    "class": safe_attr(opt, "class"),
                    "value": safe_attr(opt, "value"),
                    "placeholder": "",
                    "text": clean_text(opt.text),
                })
        except Exception:
            pass

    # BUTTONS
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for i, el in enumerate(buttons, start=1):
        elements_rows.append({
            "tipo_elemento": "button",
            "indice": i,
            "tag": "button",
            "type": safe_attr(el, "type"),
            "id": safe_attr(el, "id"),
            "name": safe_attr(el, "name"),
            "class": safe_attr(el, "class"),
            "value": safe_attr(el, "value"),
            "placeholder": "",
            "text": clean_text(el.text),
        })

    # LINKS
    anchors = driver.find_elements(By.TAG_NAME, "a")
    for i, el in enumerate(anchors, start=1):
        text = clean_text(el.text)
        href = safe_attr(el, "href")
        if text or href:
            elements_rows.append({
                "tipo_elemento": "link",
                "indice": i,
                "tag": "a",
                "type": "",
                "id": safe_attr(el, "id"),
                "name": safe_attr(el, "name"),
                "class": safe_attr(el, "class"),
                "value": href,
                "placeholder": "",
                "text": text,
            })

    out_file = OUT_DIR / "ins_buscador_elementos.csv"
    with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "tipo_elemento",
                "indice",
                "tag",
                "type",
                "id",
                "name",
                "class",
                "value",
                "placeholder",
                "text",
            ],
        )
        writer.writeheader()
        writer.writerows(elements_rows)

    print(f"\nArchivo generado: {out_file}")
    print(f"Total elementos guardados: {len(elements_rows)}")

    print("\nSELECTS encontrados:")
    for row in elements_rows:
        if row["tipo_elemento"] == "select":
            print(
                f"- id={row['id']!r} | name={row['name']!r} | class={row['class']!r} | texto={row['text'][:120]!r}"
            )

    print("\nBUTTONS encontrados:")
    for row in elements_rows:
        if row["tipo_elemento"] == "button":
            print(
                f"- id={row['id']!r} | name={row['name']!r} | type={row['type']!r} | texto={row['text']!r}"
            )

    input("\nPresiona Enter para cerrar el navegador... ")

finally:
    driver.quit()