from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

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

# Opcional: deja comentada esta línea para ver el navegador
# options.add_argument("--headless=new")

driver = webdriver.Chrome(options=options)

try:
    driver.get("https://portalsivigila.ins.gov.co/")
    print("Título:", driver.title)
    print("URL actual:", driver.current_url)
    input("Presiona Enter para cerrar el navegador...")
finally:
    driver.quit()