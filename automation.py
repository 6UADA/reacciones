import requests
import random
import time
import traceback
import json
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import os
from dotenv import load_dotenv
from logger_shared import log_to_web

load_dotenv()


# ================= CONFIG =================
def normalize_computer_id(value):
    if not value:
        return ''
    return re.sub(r'[^a-z0-9_]', '', value.strip().lower().replace('-', '_').replace(' ', '_'))


def detect_computer_id():
    explicit = (
        os.getenv('CURRENT_COMPUTER')
        or os.getenv('CURRENT_COMPUTER_ID')
        or os.getenv('MY_COMPUTER_ID')
    )
    if explicit:
        return normalize_computer_id(explicit)

    host = os.getenv('COMPUTERNAME') or os.getenv('HOSTNAME')
    return normalize_computer_id(host or '')


def resolve_ads_config():
    computer_id = detect_computer_id()
    prefixes = []

    if computer_id:
        prefixes.append(computer_id.upper())
        # Permite mapear torreon_1/torreon_2 -> TORREON_* del .env
        region_prefix = re.sub(r'_\d+$', '', computer_id.upper())
        if region_prefix and region_prefix not in prefixes:
            prefixes.append(region_prefix)

    api_url = ''
    api_key = ''

    for prefix in prefixes:
        api_url = api_url or os.getenv(f"{prefix}_ADSPOWER_API_URL", "")
        api_key = api_key or os.getenv(f"{prefix}_API_KEY", "")

    api_url = api_url or os.getenv("ADSPOWER_API_URL", "http://local.adspower.com:50325")
    api_key = api_key or os.getenv("API_KEY", "")

    return computer_id or 'local', api_url, api_key


ACTIVE_COMPUTER_ID, ADSPOWER_API_URL, API_KEY = resolve_ads_config()

if not API_KEY:
    print(
        f"ERROR CRITICO: No se encuentra API_KEY para '{ACTIVE_COMPUTER_ID}'. "
        f"Directorio actual: {os.getcwd()}"
    )
else:
    print(f"Configuracion activa: {ACTIVE_COMPUTER_ID}")
    print(f"API URL: {ADSPOWER_API_URL}")
    print(f"API Key cargada: {API_KEY[:5]}...")

# =========================================


def human_sleep(a=2, b=5):
    time.sleep(random.uniform(a, b))


def random_scroll(driver):
    """Realiza scroll aleatorio para simular comportamiento humano"""
    try:
        scroll_amount = random.randint(300, 700)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        human_sleep(1, 2)
        
        # A veces regresa un poco
        if random.random() > 0.7:
             driver.execute_script(f"window.scrollBy(0, -{random.randint(100, 300)});")
             human_sleep(0.5, 1)
             
    except Exception as e:
        print(f"⚠️ Error en random_scroll: {e}")


# ---------- ADSPOWER ----------
def start_browser(user_id):
    # Flags de optimización para ChromeDriver dentro de AdsPower
    launch_args = [
        "--headless=new",  # Modo headless (sin ventana visible)
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-breakpad",
        "--disable-client-side-phishing-detection",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-dev-shm-usage",
        "--disable-domain-reliability",
        "--disable-extensions",
        "--disable-features=InterestFeedContentSuggestions",
        "--mute-audio" # Mute a nivel browser por defecto
    ]

    url = f"{ADSPOWER_API_URL}/api/v1/browser/start"
    params = {
        "user_id": user_id,
        "launch_args": json.dumps(launch_args)
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "api-key": API_KEY
    }

    try:
        resp = requests.get(url, params=params, headers=headers)
    except Exception as e:
        log_to_web(f"❌ Error de conexión al iniciar browser: {e}", "error")
        return None

    if resp.status_code != 200:
        log_to_web(f"❌ AdsPower no respondió (HTTP {resp.status_code})", "error")
        return None

    data = resp.json()

    if data["code"] == 0:
        log_to_web(f"🟢 Perfil {user_id} iniciado con éxito", "success")
        return data["data"]
    else:
        log_to_web(f"❌ Error AdsPower ({user_id}): {data['msg']}", "error")
        return None


def close_browser(user_id):
    url = f"{ADSPOWER_API_URL}/api/v1/browser/stop?user_id={user_id}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "api-key": API_KEY
    }
    requests.get(url, headers=headers)


# ---------- API HELPERS ----------
def get_ads_groups():
    """Obtiene la lista de todos los grupos de AdsPower y los ordena con manejo de rate limit"""
    groups = []
    page = 1
    while True:
        url = f"{ADSPOWER_API_URL}/api/v1/group/list?page={page}&page_size=100"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "api-key": API_KEY
        }
        try:
            resp = requests.get(url, headers=headers)
            data = resp.json()
            if data.get("code") == 0:
                group_list = data.get("data", {}).get("list", [])
                if not group_list:
                    break
                for g in group_list:
                    groups.append({
                        "group_id": g.get("group_id"),
                        "group_name": g.get("group_name"),
                        "count": g.get("number_of_accounts", 0)
                    })
                page += 1
                # Pausa para no saturar la API en paginación
                time.sleep(1.0)
            elif "Too many request" in data.get("msg", ""):
                log_to_web(f"⚠️ Rate limit en AdsPower. Esperando 2s...", "warning")
                time.sleep(2)
                continue
            else:
                log_to_web(f"❌ Error API AdsPower (Grupos): {data.get('msg')}", "error")
                break
        except Exception as e:
            log_to_web(f"❌ Excepción obteniendo grupos: {str(e)}", "error")
            break
    
    # Filtrar grupos del 1 al 16 (son de otra red social, sin Facebook)
    filtered_groups = []
    import re
    for g in groups:
        name = g.get('group_name', '')
        # Buscar el número en el nombre "Grupo 1", "Grupo 10", etc.
        match = re.search(r'Grupo\s+(\d+)', name, re.IGNORECASE)
        if match:
            group_num = int(match.group(1))
            if 1 <= group_num <= 16:
                continue # Saltar grupos del 1 al 16
        filtered_groups.append(g)
    
    # Ordenar por nombre (Natural order: Grupo 1, Grupo 2... Grupo 10)
    try:
        def natural_sort_key(s):
            name = s.get('group_name', '')
            return [int(text) if text.isdigit() else text.lower()
                    for text in re.split('([0-9]+)', name)]
        filtered_groups.sort(key=natural_sort_key)
    except:
        filtered_groups.sort(key=lambda x: x.get('group_name', '').lower())
        
    return filtered_groups


def get_ads_profiles(group_id):
    """Obtiene todos los perfiles de un grupo específico con manejo de rate limit"""
    ids = []
    page = 1
    while True:
        url = f"{ADSPOWER_API_URL}/api/v1/user/list?group_id={group_id}&page={page}&page_size=100"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "api-key": API_KEY
        }
        
        try:
            resp = requests.get(url, headers=headers)
            data = resp.json()
            if data.get("code") == 0:
                user_list = data["data"]["list"]
                if not user_list:
                    break
                for profile in user_list:
                    ids.append(profile["user_id"])
                
                page += 1
                time.sleep(1.0)
                if len(user_list) < 100: 
                     break
            elif "Too many request" in data.get("msg", ""):
                log_to_web(f"⚠️ Rate limit en perfiles (grupo {group_id}). Esperando 2s...", "warning")
                time.sleep(2)
                continue
            else:
                log_to_web(f"❌ Error AdsPower Perfiles (Grupo {group_id}): {data.get('msg')}", "error")
                break
        except Exception as e:
            log_to_web(f"❌ Excepción obteniendo perfiles: {str(e)}", "error")
            break
            
    return ids


# ---------- FACEBOOK ----------
def get_driver(driver_path, debugger_address):
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", debugger_address)

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    wait = WebDriverWait(driver, 25)
    return driver, wait, ActionChains(driver)





def watch_live_video(driver_path, debugger_address, url, duration_seconds=60):
    """
    Simula visualización de un video en vivo.
    Entra al link, da play si es necesario y se queda simulando actividad.
    """
    log_to_web(f"🕵️ Conectando driver para automatización...", "info")
    driver, wait, actions = get_driver(driver_path, debugger_address)
    
    # 1. Limpieza de pestañas (Dejar solo una)
    try:
        handles = driver.window_handles
        if len(handles) > 1:
            log_to_web(f"🧹 Limpiando {len(handles)-1} pestañas extra...", "info")
            main_handle = handles[0]
            for handle in handles[1:]:
                driver.switch_to.window(handle)
                driver.close()
            driver.switch_to.window(main_handle)
    except Exception as e:
        log_to_web(f"⚠️ Error limpiando pestañas: {e}", "warning")

    # 2. Navegación
    if url and not url.startswith('http'):
        url = 'https://' + url
        
    log_to_web(f"🌐 Navegando a: {url}", "info")
    try:
        driver.get(url)
    except Exception as e:
        log_to_web(f"❌ Error en driver.get: {e}", "error")
        return False

    print(f"Viendo video por {duration_seconds} segundos...")
    human_sleep(5, 8)
    
    # 1. Intentar dar Play y desbloquear (Incluso dentro de IFrames)
    log_to_web("🔍 Iniciando secuencia de desbloqueo profunda...", "info")
    
    # Función de ayuda para clickar el botón de play
    def try_click_play(ctx):
        # 1. Intentar Play vía JavaScript directo en todos los videos (Lo más efectivo)
        try:
            videos = ctx.find_elements(By.TAG_NAME, "video")
            for v in videos:
                if v.is_displayed():
                    driver.execute_script("arguments[0].play();", v)
                    log_to_web("⚡ Intento de play vía JS en elemento <video>", "info")
        except: pass

        # 2. Selectores específicos de Play (Ordenados por prioridad)
        selectors = [
            "//button[contains(@aria-label, 'Reproducir')]", # Español
            "//button[contains(@aria-label, 'Play')]",      # Inglés
            "//div[contains(@aria-label, 'Reproducir')]", 
            "//div[contains(@aria-label, 'Play')]",
            "//*[contains(@class, 'play') and not(contains(@class, 'player'))]", # Evitar la clase del contenedor
            "//div[contains(text(), 'permitir')]",
            "//div[contains(text(), 'Haga clic')]"
        ]
        
        for s in selectors:
            try:
                elements = ctx.find_elements(By.XPATH, s)
                for el in elements:
                    if el.is_displayed():
                        # Evitar clics en botones de "Menú" o "Más opciones" si se colaron
                        label = el.get_attribute("aria-label") or el.text or ""
                        if any(x in label.lower() for x in ["menú", "opciones", "settings", "configuración"]):
                            continue
                            
                        try:
                            actions = ActionChains(driver)
                            actions.move_to_element(el).click().perform()
                            log_to_web(f"🎯 Click (Action) en selector específico: {s[:20]}", "success")
                            return True
                        except:
                            driver.execute_script("arguments[0].click();", el)
                            log_to_web(f"🎯 Click (JS) en selector específico: {s[:20]}", "success")
                            return True
            except: continue
        
        # 3. Si hay video pero no botón, click en el centro del video
        try:
            videos = ctx.find_elements(By.TAG_NAME, "video")
            for v in videos:
                if v.is_displayed():
                    actions = ActionChains(driver)
                    actions.move_to_element(v).click().perform()
                    log_to_web("🎯 Click en el centro del elemento <video>", "success")
                    return True
        except: pass

        return False

    # Primero buscamos en el documento principal
    found = try_click_play(driver)
    
    # Si no lo encontramos, buscamos en todos los iframes
    if not found:
        log_to_web("📂 Buscando botón en iframes internos...", "info")
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for i, frame in enumerate(iframes):
            try:
                driver.switch_to.frame(frame)
                if try_click_play(driver):
                    log_to_web(f"✅ Desbloqueado dentro de IFrame #{i+1}", "success")
                    found = True
                    # NO salimos del frame si el video está dentro
                    break
                driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
                continue
    
    if not found:
        log_to_web("⚠️ No se detectó botón obvio, intentando click central forzado...", "warning")
        try:
            # Click en el centro de la pantalla como último recurso
            size = driver.get_window_size()
            actions = ActionChains(driver)
            actions.move_by_offset(size['width']//2, size['height']//2).click().perform()
        except: pass

    human_sleep(3, 5)
    log_to_web("🎬 Iniciando simulación de visualización...", "info")

    # Intentar desmutear (Opcional pero recomendado para views)
    try:
        mute_selectors = ["//button[contains(@aria-label, 'unmute')]", "//button[contains(@aria-label, 'activar sonido')]"]
        for s in mute_selectors:
            m_btn = driver.find_elements(By.XPATH, s)
            if m_btn and m_btn[0].is_displayed():
                driver.execute_script("arguments[0].click();", m_btn[0])
                log_to_web("🔊 Video desmuiteado para validez de view.", "success")
                break
    except: pass

    # 2. Loop de actividad
    start_time = time.time()
    while (time.time() - start_time) < duration_seconds:
        try:
            # Simular movimiento aleatorio cada 10-20 segundos
            human_sleep(10, 20)
            
            # Probabilidad de scroll corto
            if random.random() > 0.7:
                scroll = random.randint(100, 300)
                driver.execute_script(f"window.scrollBy(0, {scroll});")
                time.sleep(1)
                driver.execute_script(f"window.scrollBy(0, -{scroll});")
                print("Movimiento de actividad simulado.")
            else:
                actions = ActionChains(driver)
                actions.move_by_offset(random.randint(-5, 5), random.randint(-5, 5)).perform()
        except:
            break
            
    print("Tiempo de visualizacion completado.")
    return True



