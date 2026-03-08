"""
ITLA - Auto Completar Encuestas de Calificación
================================================
Navegadores soportados: Chrome, Brave, Edge, Firefox, Opera, Opera GX

REQUISITOS:
  - Python 3.x  →  https://www.python.org/downloads/
  - Al menos uno de los navegadores mencionados instalado

INSTRUCCIONES:
  1. Ejecuta:  python itla_encuestas.py
  2. Elige tu navegador
  3. Inicia sesión cuando se abra el navegador
  4. Presiona ENTER y el script hace el resto
"""

import subprocess, sys, importlib, os, time, re, zipfile, stat
import urllib.request

# ─── Auto-instalación de dependencias ─────────────────────────────────────────
def instalar(paquete):
    subprocess.check_call([sys.executable, "-m", "pip", "install", paquete, "--quiet"])

def verificar_dependencias():
    for modulo, pip_name in {"selenium": "selenium", "requests": "requests"}.items():
        try:
            importlib.import_module(modulo)
        except ImportError:
            print(f"  → Instalando {pip_name}...")
            instalar(pip_name)

print("=" * 58)
print("   ITLA — Auto Completar Encuestas  |  Multi-Navegador")
print("=" * 58)
print("\n[*] Verificando dependencias...")
verificar_dependencias()
print("[✓] Dependencias listas.\n")

# ─── Imports post-instalación ─────────────────────────────────────────────────
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options  import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options    import Options as EdgeOptions
from selenium.webdriver.chrome.service  import Service as ChromeService
from selenium.webdriver.edge.service    import Service as EdgeService
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    StaleElementReferenceException, WebDriverException
)

# ─── Obtener versión del navegador ────────────────────────────────────────────
def obtener_version_chromium(exe_path):
    """Lee la versión real del ejecutable de un navegador Chromium."""
    try:
        result = subprocess.run(
            [exe_path, "--version"],
            capture_output=True, text=True, timeout=5
        )
        match = re.search(r"(\d+)\.\d+\.\d+\.\d+", result.stdout + result.stderr)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    # Fallback: leer desde el archivo de versión junto al exe
    try:
        base = os.path.dirname(exe_path)
        ver_file = os.path.join(base, "VERSION") if os.path.exists(os.path.join(base, "VERSION")) else None
        if not ver_file:
            for fname in os.listdir(base):
                if re.match(r"\d+\.\d+\.\d+\.\d+", fname) and os.path.isdir(os.path.join(base, fname)):
                    match = re.match(r"(\d+)", fname)
                    if match:
                        return int(match.group(1))
    except Exception:
        pass
    return None

# ─── Descarga de ChromeDriver correcto ────────────────────────────────────────
DRIVER_CACHE = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "itla_drivers")

def descargar_chromedriver(major_version):
    """Descarga el ChromeDriver que coincide con la versión mayor del navegador."""
    driver_path = os.path.join(DRIVER_CACHE, f"chromedriver_{major_version}", "chromedriver.exe")
    if os.path.exists(driver_path):
        return driver_path

    os.makedirs(os.path.dirname(driver_path), exist_ok=True)
    print(f"  → Descargando ChromeDriver para versión {major_version}...")

    # Para versiones >= 115 usar el nuevo endpoint de Chrome for Testing
    if major_version >= 115:
        url_json = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
        try:
            resp = requests.get(url_json, timeout=15)
            data = resp.json()
            versions = data.get("versions", [])
            # Buscar la última versión que coincida con el major
            candidatos = [
                v for v in versions
                if v["version"].startswith(f"{major_version}.")
            ]
            if not candidatos:
                raise Exception(f"No se encontró ChromeDriver para versión {major_version}")
            candidato = candidatos[-1]
            downloads = candidato.get("downloads", {}).get("chromedriver", [])
            win_url = next((d["url"] for d in downloads if "win32" in d["url"]), None)
            if not win_url:
                win_url = next((d["url"] for d in downloads if "win64" in d["url"]), None)
            if not win_url:
                raise Exception("No se encontró URL de descarga para Windows")
        except Exception as e:
            raise Exception(f"Error consultando versiones de ChromeDriver: {e}")
    else:
        # Versiones < 115: endpoint antiguo
        url_ver = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major_version}"
        try:
            ver = requests.get(url_ver, timeout=10).text.strip()
            win_url = f"https://chromedriver.storage.googleapis.com/{ver}/chromedriver_win32.zip"
        except Exception as e:
            raise Exception(f"Error obteniendo versión de ChromeDriver legacy: {e}")

    # Descargar y extraer
    zip_path = driver_path.replace(".exe", ".zip")
    try:
        urllib.request.urlretrieve(win_url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.namelist():
                if member.endswith("chromedriver.exe"):
                    with z.open(member) as src, open(driver_path, "wb") as dst:
                        dst.write(src.read())
                    break
        os.remove(zip_path)
        os.chmod(driver_path, stat.S_IRWXU)
        print(f"  [✓] ChromeDriver {major_version} listo.")
        return driver_path
    except Exception as e:
        raise Exception(f"Error descargando ChromeDriver: {e}")

def descargar_geckodriver():
    """Descarga la última versión de GeckoDriver para Firefox."""
    driver_path = os.path.join(DRIVER_CACHE, "geckodriver", "geckodriver.exe")
    if os.path.exists(driver_path):
        return driver_path

    os.makedirs(os.path.dirname(driver_path), exist_ok=True)
    print("  → Descargando GeckoDriver para Firefox...")

    try:
        api = requests.get(
            "https://api.github.com/repos/mozilla/geckodriver/releases/latest",
            timeout=15, headers={"Accept": "application/vnd.github+json"}
        ).json()
        assets = api.get("assets", [])
        win_asset = next(
            (a for a in assets if "win64" in a["name"] and a["name"].endswith(".zip")),
            None
        ) or next(
            (a for a in assets if "win32" in a["name"] and a["name"].endswith(".zip")),
            None
        )
        if not win_asset:
            raise Exception("No se encontró GeckoDriver para Windows")

        zip_path = driver_path.replace(".exe", ".zip")
        urllib.request.urlretrieve(win_asset["browser_download_url"], zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.namelist():
                if member.endswith("geckodriver.exe"):
                    with z.open(member) as src, open(driver_path, "wb") as dst:
                        dst.write(src.read())
                    break
        os.remove(zip_path)
        os.chmod(driver_path, stat.S_IRWXU)
        print("  [✓] GeckoDriver listo.")
        return driver_path
    except Exception as e:
        raise Exception(f"Error descargando GeckoDriver: {e}")

def descargar_edgedriver():
    """Descarga el EdgeDriver que coincide con la versión instalada de Edge."""
    try:
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        return EdgeChromiumDriverManager().install()
    except Exception as e:
        raise Exception(f"Error con EdgeDriver: {e}")

# ─── Detección de navegadores ─────────────────────────────────────────────────
NAVEGADORES = {
    "1": {
        "nombre": "Google Chrome",
        "rutas": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ],
        "tipo": "chrome",
        "puerto": 9222,
    },
    "2": {
        "nombre": "Brave Browser",
        "rutas": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ],
        "tipo": "chrome",
        "puerto": 9223,
    },
    "3": {
        "nombre": "Microsoft Edge",
        "rutas": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        ],
        "tipo": "edge",
        "puerto": 9224,
    },
    "4": {
        "nombre": "Mozilla Firefox",
        "rutas": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Mozilla Firefox\firefox.exe"),
        ],
        "tipo": "firefox",
        "puerto": None,
    },
    "5": {
        "nombre": "Opera",
        "rutas": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
            r"C:\Program Files\Opera\opera.exe",
        ],
        "tipo": "chrome",
        "puerto": 9225,
    },
    "6": {
        "nombre": "Opera GX",
        "rutas": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe"),
            r"C:\Program Files\Opera GX\opera.exe",
        ],
        "tipo": "chrome",
        "puerto": 9226,
    },
}

def encontrar_ejecutable(nav_info):
    return next((r for r in nav_info["rutas"] if os.path.exists(r)), None)

def mostrar_menu():
    print("Navegadores detectados en tu PC:\n")
    disponibles = {}
    for key, nav in NAVEGADORES.items():
        exe = encontrar_ejecutable(nav)
        if exe:
            print(f"  [{key}] {nav['nombre']}")
            disponibles[key] = nav
        else:
            print(f"  [{key}] {nav['nombre']}  (no instalado)")
    print()
    while True:
        eleccion = input("Elige el número de tu navegador: ").strip()
        if eleccion in disponibles:
            return disponibles[eleccion]
        elif eleccion in NAVEGADORES:
            print(f"[!] {NAVEGADORES[eleccion]['nombre']} no está instalado.")
        else:
            print("[!] Opción inválida.")

# ─── Iniciar driver ───────────────────────────────────────────────────────────
def _esperar_login():
    print("\n┌─────────────────────────────────────────────────┐")
    print("│  1. Inicia sesión en la página que se abrió      │")
    print("│  2. Ve a la sección de calificaciones            │")
    print("│  3. Cuando estés listo, presiona ENTER aquí ↓    │")
    print("└─────────────────────────────────────────────────┘")
    input()

def _cerrar_pestana_extra(driver):
    """Cierra pestanas vacias dejando solo la de ITLA."""
    url_objetivo = "perfil.itla.edu.do"
    for _ in range(20):
        time.sleep(0.5)
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                if url_objetivo in driver.current_url:
                    break
            except Exception:
                pass
        else:
            continue
        break
    for handle in list(driver.window_handles):
        try:
            driver.switch_to.window(handle)
            if url_objetivo not in driver.current_url:
                driver.close()
        except Exception:
            pass
    for handle in driver.window_handles:
        try:
            driver.switch_to.window(handle)
            if url_objetivo in driver.current_url:
                break
        except Exception:
            pass

def iniciar_driver(nav_info):
    tipo   = nav_info["tipo"]
    exe    = encontrar_ejecutable(nav_info)
    url    = "https://perfil.itla.edu.do/#/qualification-student"
    puerto = nav_info["puerto"]

    # ── Firefox: Selenium lo controla directo ────────────────────────────────
    if tipo == "firefox":
        from selenium.webdriver.firefox.service import Service as FirefoxService
        gecko = descargar_geckodriver()
        opts = FirefoxOptions()
        opts.binary_location = exe
        driver = webdriver.Firefox(service=FirefoxService(gecko), options=opts)
        driver.get(url)
        print(f"\n[OK] {nav_info['nombre']} abierto.")
        _esperar_login()
        return driver

    # ── Chromium-based: cerrar instancia abierta y relanzar con perfil real ──
    # Usando el perfil real del usuario para que se vea como el navegador normal
    perfiles_usuario = {
        "Google Chrome":  os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
        "Brave Browser":  os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data"),
        "Microsoft Edge": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data"),
        "Opera":          os.path.expandvars(r"%APPDATA%\Opera Software\Opera Stable"),
        "Opera GX":       os.path.expandvars(r"%APPDATA%\Opera Software\Opera GX Stable"),
    }
    nombre_proceso = {
        "Google Chrome":  "chrome.exe",
        "Brave Browser":  "brave.exe",
        "Microsoft Edge": "msedge.exe",
        "Opera":          "opera.exe",
        "Opera GX":       "opera.exe",
    }.get(nav_info["nombre"], "chrome.exe")

    perfil_real = perfiles_usuario.get(nav_info["nombre"])

    print(f"\n[!] ATENCIÓN: Se cerrará {nav_info['nombre']} para poder automatizarlo.")
    print("[!] Guarda cualquier trabajo pendiente en tus pestañas.")
    input("Presiona ENTER para continuar o Ctrl+C para cancelar...")
    print()
    for i in range(5, 0, -1):
        print(f"  Cerrando en {i}...", end="\r")
    time.sleep(1) 
    print() 

    print(f"  [i] Cerrando {nav_info['nombre']}...")  
    subprocess.run(["taskkill", "/F", "/IM", nombre_proceso], capture_output=True)
    time.sleep(1.5)

    cmd = [exe, f"--remote-debugging-port={puerto}"]
    if perfil_real and os.path.exists(perfil_real):
        cmd.append(f"--user-data-dir={perfil_real}")
        print(f"  [i] Usando perfil real del usuario.")
    else:
        perfil_tmp = os.path.join(os.environ.get("TEMP", "C:\\Temp"), f"itla_debug_{puerto}")
        os.makedirs(perfil_tmp, exist_ok=True)
        cmd.append(f"--user-data-dir={perfil_tmp}")
        print(f"  [i] Usando perfil temporal.")
    cmd.append(url)

    subprocess.Popen(cmd)
    time.sleep(2.5)

    # ── Conectar Selenium ─────────────────────────────────────────────────────
    if tipo == "edge":
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        opts = EdgeOptions()
        opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{puerto}")
        driver = webdriver.Edge(
            service=EdgeService(EdgeChromiumDriverManager().install()),
            options=opts
        )
    else:
        major = obtener_version_chromium(exe)
        if major is None:
            raise Exception(f"No se pudo detectar la version de {nav_info['nombre']}.")
        print(f"  [i] Version detectada: {nav_info['nombre']} {major}.x")
        chromedriver_path = descargar_chromedriver(major)
        opts = ChromeOptions()
        opts.binary_location = exe
        opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{puerto}")
        driver = webdriver.Chrome(service=ChromeService(chromedriver_path), options=opts)

    _cerrar_pestana_extra(driver)
    print(f"\n[OK] Conectado a {nav_info['nombre']}.")
    _esperar_login()
    return driver

# ─── Lógica de encuestas ──────────────────────────────────────────────────────
def seleccionar_calificacion_5(driver):
    labels = driver.find_elements(
        By.XPATH,
        "//app-complete-survey//label[normalize-space(text())='5'] | "
        "//mat-dialog-container//label[normalize-space(text())='5']"
    )
    if labels:
        for label in labels:
            try:
                driver.execute_script("arguments[0].click();", label)
                time.sleep(0.15)
            except StaleElementReferenceException:
                continue
        print(f"    [✓] {len(labels)} pregunta(s) calificadas con 5.")
        return

    preguntas = driver.find_elements(
        By.CSS_SELECTOR,
        "app-complete-survey .mb-4, mat-dialog-container .mb-4"
    )
    for pregunta in preguntas:
        try:
            radios = pregunta.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            if radios:
                driver.execute_script("arguments[0].click();", radios[-1])
                time.sleep(0.15)
        except StaleElementReferenceException:
            continue
    print(f"    [✓] {len(preguntas)} pregunta(s) calificadas con 5.")


def completar_encuestas(driver):
    wait = WebDriverWait(driver, 10)
    completadas = 0
    # Verificar que el usuario está en la página correcta antes de continuar.
    #Si no hay encuestas pendientes, salir sin modificar nada
    if "qualification-student" not in driver.current_url:
        print("\n[!] Error: No te encuentras en la sección de encuestas.")
        print("    Asegúrate de estar en: https://perfil.itla.edu.do/#/qualification-student")
        return 0
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "i.flaticon-proceso-3"))
        )
    except TimeoutException:
        print("\n[i] No se detectaron encuestas pendientes en la página actual.")
        return 0

    print("\n[*] Buscando encuestas pendientes...\n")

    while True:
        time.sleep(1)

        try:
            botones = driver.find_elements(By.CSS_SELECTOR, "i.flaticon-proceso-3")
            visibles = [b for b in botones if b.is_displayed()]

            if not visibles:
                print(
                    f"\n[✓] ¡Listo! {completadas} encuesta(s) completadas."
                    if completadas > 0
                    else "\n[!] No hay encuestas pendientes. Verifica que estás en la página correcta."
                )
                break

            icono = visibles[0]
            try:
                clickeable = icono.find_element(By.XPATH, "ancestor::button[1] | ancestor::a[1]")
            except NoSuchElementException:
                clickeable = icono

            print(f"[→] Abriendo encuesta #{completadas + 1}...")
            driver.execute_script("arguments[0].click();", clickeable)

        except StaleElementReferenceException:
            continue

        try:
            wait.until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "app-complete-survey, mat-dialog-container")
            ))
        except TimeoutException:
            print("    [!] Modal no apareció, reintentando...")
            continue

        time.sleep(0.8)
        seleccionar_calificacion_5(driver)

        time.sleep(0.4)
        try:
            btn = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "app-complete-survey button.btn-success, "
                "mat-dialog-container button.btn-success, "
                "button.btn-primary.btn-success"
            )))
            driver.execute_script("arguments[0].click();", btn)
            print(f"    [✓] Clic en 'Completar'.")

            # ── Confirmación SweetAlert2 "¿Está seguro?" ────────────────────
            try:
                btn_ok = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "button.swal2-confirm")
                    )
                )
                driver.execute_script("arguments[0].click();", btn_ok)
                print(f"    [✓] Confirmación 'OK' aceptada.")
            except TimeoutException:
                pass  # No siempre aparece, seguimos normal

            completadas += 1
            print(f"    [✓] Encuesta #{completadas} enviada.\n")
            time.sleep(2)
        except TimeoutException:
            print("    [!] No encontré 'Completar'. Cerrando modal...")
            try:
                driver.find_element(
                    By.CSS_SELECTOR, "button.dynamicBtnCloseModal, button.btn-danger"
                ).click()
            except Exception:
                pass
            time.sleep(1)

    return completadas

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    nav_info = mostrar_menu()

    print(f"\n[*] Iniciando {nav_info['nombre']}...")
    try:
        driver = iniciar_driver(nav_info)
    except Exception as e:
        print(f"\n[✗] Error al iniciar el navegador:\n    {e}")
        sys.exit(1)

    if "perfil.itla.edu.do" not in driver.current_url:
        print(f"[!] URL actual: {driver.current_url}")
        input("    Navega a la página de calificaciones y presiona ENTER...")

    try:
        completar_encuestas(driver)
    except KeyboardInterrupt:
        print("\n\n[!] Interrumpido.")
    except Exception as e:
        print(f"\n[✗] Error inesperado: {e}")
        import traceback; traceback.print_exc()
    finally:
        print("\n[*] Listo. El navegador queda abierto para que revises.")

if __name__ == "__main__":
    main()
