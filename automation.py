import requests
import random
import time
import traceback

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
# NOTA: La API Key se carga desde el archivo .env
ADSPOWER_API_URL = os.getenv("ADSPOWER_API_URL", "http://local.adspower.com:50325")
API_KEY = os.getenv("API_KEY", "")

if not API_KEY:
    print(f"ERROR CRITICO: No se encuentra API_KEY. Directorio actual: {os.getcwd()}")
else:
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
    url = f"{ADSPOWER_API_URL}/api/v1/browser/start?user_id={user_id}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "api-key": API_KEY  # Soporte doble para asegurar compatibilidad
    }

    resp = requests.get(url, headers=headers)

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
    driver, wait, actions = get_driver(driver_path, debugger_address)
    driver.get(url)
    
    # Limpieza de pestañas...
    try:
        current_handle = driver.current_window_handle
        handles = driver.window_handles
        if len(handles) > 1:
            for handle in handles:
                if handle != current_handle:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(current_handle)
    except: pass

    print(f"Viendo video por {duration_seconds} segundos...")
    human_sleep(5, 8)
    
    # 1. Intentar dar Play si no arrancó solo
    play_selectors = [
        "//div[@role='button'][@aria-label='Reproducir']",
        "//div[@role='button'][@aria-label='Play']",
        "//div[@role='button'][@aria-label='Continuar']",
        "//video/ancestor::div[1]"
    ]
    
    for selector in play_selectors:
        try:
            btn = driver.find_element(By.XPATH, selector)
            if btn.is_displayed():
                actions = ActionChains(driver)
                actions.move_to_element(btn).click().perform()
                print("Play clicado.")
                break
        except: continue

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



