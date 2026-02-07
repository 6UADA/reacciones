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

load_dotenv()

# ================= CONFIG =================
# NOTA: La API Key se carga desde el archivo .env
ADSPOWER_API_URL = os.getenv("ADSPOWER_API_URL", "http://local.adspower.com:50325")
API_KEY = os.getenv("API_KEY", "")

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
        "Authorization": f"Bearer {API_KEY}"
    }

    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        print("❌ AdsPower no respondió")
        return None

    data = resp.json()

    if data["code"] == 0:
        print("🟢 Perfil iniciado")
        return data["data"]
    else:
        print(f"❌ Error iniciando perfil {user_id}: {data['msg']}")
        return None


def close_browser(user_id):
    url = f"{ADSPOWER_API_URL}/api/v1/browser/stop?user_id={user_id}"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    requests.get(url, headers=headers)


# ---------- API HELPERS ----------
def get_ads_groups():
    """Obtiene la lista de todos los grupos de AdsPower y los ordena con manejo de rate limit"""
    groups = []
    page = 1
    while True:
        url = f"{ADSPOWER_API_URL}/api/v1/group/list?page={page}&page_size=100"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        try:
            resp = requests.get(url, headers=headers)
            data = resp.json()
            if data.get("code") == 0:
                batch = data["data"]["list"]
                if not batch: 
                    break
                groups.extend(batch)
                page += 1
                # Pausa para no saturar la API en paginación
                time.sleep(1.0)
            elif "Too many request" in data.get("msg", ""):
                print(f"⏳ Rate limit en grupos (página {page}). Esperando 2s antes de reintentar...")
                time.sleep(2)
                continue
            else:
                print(f"⚠️ Error API AdsPower (Groups): {data.get('msg')}")
                break
        except Exception as e:
            print(f"⚠️ Excepción obteniendo grupos: {e}")
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
    
    print(f"📊 Total grupos cargados (filtrando 1-16): {len(filtered_groups)}")
    
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
        headers = {"Authorization": f"Bearer {API_KEY}"}
        
        try:
            resp = requests.get(url, headers=headers)
            data = resp.json()
            if data.get("code") == 0:
                user_list = data["data"]["list"]
                if not user_list:
                    break
                for profile in user_list:
                    ids.append(profile["user_id"])
                
                # Continuar solo si recibimos una lista llena, 
                # pero mejor basarse en si hay más páginas o si recibimos algo
                page += 1
                time.sleep(1.0)
                # Si recibimos menos de 100, es muy probable que sea la última página
                # pero para ser ultra-seguros en APIs inconsistentes, solo paramos si not batch
                if len(user_list) < 10: # Si tiene 10 perfiles por grupo, esto frenará bien
                     break
                if len(user_list) == 0:
                     break
            elif "Too many request" in data.get("msg", ""):
                print(f"⏳ Rate limit en perfiles (grupo {group_id}). Esperando 2s...")
                time.sleep(2)
                continue
            else:
                print(f"❌ Error obteniendo perfiles del grupo {group_id}: {data.get('msg')}")
                break
        except Exception as e:
            print(f"⚠️ Excepción obteniendo perfiles del grupo {group_id}: {e}")
            break
            
    return ids


# ---------- FACEBOOK ----------
def get_driver(driver_path, debugger_address):
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", debugger_address)

    # Extract port from debugger_address (e.g., "127.0.0.1:50000")
    webdriver_port = debugger_address.split(':')[-1]

    # Intentar conexión con reintentos para evitar Read Timeout durante el arranque
    max_retries = 3
    driver = None
    for attempt in range(max_retries):
        try:
            print(f"   🔧 Conectando Selenium a puerto {webdriver_port} (Intento {attempt+1})...")
            # Revertido v7: Usar webdriver.Chrome directo sobre el puerto de depuración
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            driver.set_page_load_timeout(150)
            driver.set_script_timeout(150)
            break 
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️ Error de conexión, reintentando en 3s...")
                time.sleep(3)
            else:
                print(f"   ❌ Error fatal conectando a AdsPower local: {e}")
                return None, None, None
    
    if driver is None:
        return None, None, None

    wait = WebDriverWait(driver, 25)
    return driver, wait, ActionChains(driver)


def check_account_status(driver):
    """
    Verifica si la cuenta está logueada y activa.
    Retorna: "ok", "logged_out", "disabled"
    """
    try:
        current_url = driver.current_url
        if "login" in current_url or "checkpoint" in current_url:
            return "logged_out"
            
        # Buscar elementos típicos de 'cuenta suspendida' o 'inhabilitada'
        page_text = driver.page_source.lower()
        if "cuenta inhabilitada" in page_text or "account disabled" in page_text or "suspended" in page_text:
            return "disabled"
            
        return "ok"
    except:
        return "ok" # Si falla la revisión, asumimos ok para no bloquear


def safe_reaction_click(driver, reaction_name):
    """
    Busca botones de reacción específicos para evitar clics en texto aleatorio.
    Intenta varias veces por si la animación de apertura demora.
    """
    print(f"🔎 Buscando reacción: {reaction_name}...")
    
    # Mapeo de variaciones comunes o errores de typo
    variations = [reaction_name]
    if reaction_name == "Me encanta": variations.extend(["Love", "Heart", "Encanta"])
    if reaction_name == "Me divierte": variations.extend(["Haha", "Laughter", "Laughing", "Funny", "Gracia", "Laugh", "Divierte"])
    if reaction_name == "Me asombra": variations.extend(["Wow", "Astonished", "Asombra", "Surprised", "Amazing"])
    if reaction_name == "Me entristece": variations.extend(["Sad", "Crying", "Sorry", "Entristece", "Triste"])
    if reaction_name == "Me enoja": variations.extend(["Angry", "Mad", "Enoja", "Enfada", "Grumpy"])
    if reaction_name == "Me importa": variations.extend(["Care", "Hug", "Importa", "Care/Heart"])

    # Intentos de espera (el menú tarda unos ms en aparecer)
    for attempt in range(4): 
        try:
            for variant in variations:
                # Selectores ultra-flexibles
                xpaths = [
                    f"//div[@role='button'][contains(@aria-label, '{variant}')]",
                    f"//div[contains(@aria-label, '{variant}')][@role='img']",
                    f"//img[contains(@alt, '{variant}')]",
                    f"//*[@aria-label='{variant}']",
                    f"//*[text()='{variant}']"
                ]
                
                for xpath in xpaths:
                    elements = driver.find_elements(By.XPATH, xpath)
                    for el in elements:
                        try:
                            if el.is_displayed():
                                size = el.size
                                # FILTRO v5: Ajustado para capturar iconos en diferentes zooms
                                if size['height'] < 25 or size['width'] < 25:
                                    continue
                                
                                if size['height'] > 120 or size['width'] > 130:
                                    continue 
                                
                                print(f"   ✅ '{variant}' encontrado ({xpath}) [{size['width']}x{size['height']}px]. Click...")
                                
                                # Move to element de forma segura
                                try:
                                    actions = ActionChains(driver)
                                    # Moverse, esperar a que el hover del icono se active y click
                                    actions.move_to_element(el).pause(0.5).click().perform()
                                except:
                                    driver.execute_script("arguments[0].click();", el)
                                    
                                return True
                        except:
                            continue
            
            # Si no encontró nada, esperar un poco antes del siguiente intento
            time.sleep(1)
            
        except Exception as e:
            print(f"⚠️ Error intentando buscar reaccion: {e}")
            time.sleep(1)
            
    print(f"❌ No se encontró '{reaction_name}' tras {attempt+1} intentos")
    return False


def react_to_post(driver_path, debugger_address, post_url, target_reaction="Me encanta"):
    """
    Retorna: "success", "account_error", "error"
    """
    driver, wait, actions = get_driver(driver_path, debugger_address)
    if not driver:
        return "error"

    try:
        driver.get(post_url)
        
        # 0. Verificación de salud inicial
        status = check_account_status(driver)
        if status != "ok":
            print(f"⚠️ Cuenta detectada como: {status}. Skipping.")
            return "account_error"

        # Clean up tabs...
        try:
            current_handle = driver.current_window_handle
            handles = driver.window_handles
            if len(handles) > 1:
                for handle in handles:
                    if handle != current_handle:
                        driver.switch_to.window(handle)
                        driver.close()
                driver.switch_to.window(current_handle)
        except Exception as e:
            print(f"⚠️ Advertencia limpiando pestañas: {e}")

        human_sleep(5, 8)
        
        # Re-check status después de cargar el post (a veces el login sale después del .get)
        if "login" in driver.current_url:
            return "account_error"

        # 0. Esperar a que la página se estabilice un poco más (revisar si hay contenido)
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='main'] | //div[@role='article']")))
        except:
            print("⚠️ Advertencia: Tiempo de carga excedido, intentando continuar...")

        # Comportamiento humano antes de interactuar
        random_scroll(driver)

        try:
            # 1. Buscar el botón "Me gusta" principal 
            # Selectores expandidos: Español, Inglés, Estructurales y Vecindad v6
            like_btn_selectors = [
                "//div[@role='button'][@aria-label='Me gusta']",
                "//div[@role='button'][@aria-label='Like']",
                "//div[@role='button'][contains(@aria-label, 'Me gusta')]",
                "//div[@role='button'][contains(@aria-label, 'Te gusta')]", # "A ti te gusta esto"
                "//div[@role='button'][contains(@aria-label, 'Liked')]", # Inglés reaccionado
                "//div[@role='button'][@aria-label='Reaccionar']",
                "//div[@role='button'][@aria-label='Reaction']",
                "//div[@role='button'][contains(@aria-label, 'reacción')]",
                # Selector estructural
                "//div[@role='button']//span[text()='Me gusta']/ancestor::div[@role='button']",
                "//div[@role='button']//span[text()='Like']/ancestor::div[@role='button']",
                "//div[contains(@class, 'x1i10hfl')]//span[text()='Me gusta']/../../..",
                # v6: Sibling logic (El botón antes de Comentar/Comment o Compartir)
                "//div[@role='button'][contains(@aria-label, 'Comentar') or contains(@aria-label, 'Comment')]/preceding-sibling::div[@role='button']",
                "//div[@role='button'][contains(@aria-label, 'Compartir') or contains(@aria-label, 'Share')]/preceding-sibling::div[@role='button'][1]",
                "//span[contains(text(), 'Comentar') or contains(text(), 'Comment')]/ancestor::div[@role='button']/preceding-sibling::div[@role='button']"
            ]
            
            like_button = None
            current_aria = ""
            
            # v5: Proceso en dos pasadas. Primero buscamos botones con ARIA-LABEL no vacío.
            candidates = []
            for selector in like_btn_selectors:
                try:
                    elements = driver.find_elements(By.XPATH, selector)
                    for el in elements:
                        if el.is_displayed():
                            size = el.size
                            if size['width'] > 40 and size['width'] < 360:
                                candidates.append(el)
                except:
                    continue
            
            # Seleccionar el mejor candidato (el que tenga aria-label o texto)
            for cand in candidates:
                aria = cand.get_attribute("aria-label") or ""
                text = cand.text or ""
                if aria or text:
                    like_button = cand
                    current_aria = aria
                    break
            
            # Fallback al primero disponible v6 (con o sin texto)
            if not like_button and candidates:
                like_button = candidates[0]
                current_aria = like_button.get_attribute("aria-label") or ""

            if not like_button:
                print("❌ No se encontró el botón principal de 'Me gusta' (Probamos 14 selectores)")
                return "success" # Retornar success para no marcar error fatal si ya estaba liked pero no lo vimos
                
            print(f"✅ Botón encontrado (Aria: '{current_aria}')")

            # --- CASO ESPECIAL: "Me gusta" ---
            target_norm = target_reaction.lower()
            if target_norm == "me gusta" or target_norm == "like":
                # Detectar si ya está activo
                already_active = any(x in current_aria.lower() for x in ["te gusta", "reacción", "liked", "remove", "ya no", "un-like"])
                
                if already_active:
                     print("👍 Ya tiene un 'Me gusta' o reacción activa. No hacemos nada.")
                     return "success"

                print("👍 Reacción es 'Me gusta'. Click directo.")
                try:
                    actions = ActionChains(driver)
                    actions.move_to_element(like_button).click().perform()
                except:
                    driver.execute_script("arguments[0].click();", like_button)
                
                human_sleep(1, 2)
                return "success"

            # --- OTRAS REACCIONES (Requieren Hover) ---
            # 2. Realizar Hover para que salgan las reacciones
            print("👆 Realizando Hover 'Sticky' (v5)...")
            
            # v5/v6: Hover sostenido y deliberado
            actions = ActionChains(driver)
            actions.move_to_element(like_button).perform()
            time.sleep(1) 
            
            # Micro movimiento para trigger v6
            actions.move_by_offset(2, 2).perform()
            
            try:
                # Esperar a que salga la capa de reacciones
                wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='presentation']|//div[@role='dialog']")))
                print("✨ Capa de reacciones detectada.")
            except:
                pass

            time.sleep(1.5) 
            
            print(f"🎯 Buscando reacción: {target_reaction}")
            
            # 3. Click en la reacción específica
            success = safe_reaction_click(driver, target_reaction)

            human_sleep(1, 2)
            
            # v6 Force Hold: Si falló, intentar Presión larga (3 segundos)
            if not success:
                print("⚠️ Intento v6 Force Hold: Click and hold (3s) sobre botón Me gusta...")
                try:
                    actions = ActionChains(driver)
                    actions.move_to_element(like_button).click_and_hold(like_button).pause(3.5).release().perform()
                    human_sleep(2, 4)
                    if safe_reaction_click(driver, target_reaction):
                        return "success"
                    else:
                        print(f"❌ No se encontró la reacción '{target_reaction}' en el menú")
                        return "error"
                except Exception as e:
                    print(f"❌ Error en Force Hold: {e}")
                    return "error" # Added return here
            
            if success:
                print(f"✅ Reacción enviada: {target_reaction}")
                return "success"
            else:
                print(f"❌ Falló clic en: {target_reaction}")
                return "error"

        except Exception as e:
            print("❌ Error general reaccionando:")
            traceback.print_exc()
            return "error"

    except Exception as e:
        print(f"❌ Error durante el proceso: {e}")
        traceback.print_exc()
        return "error"


def watch_live_video(driver_path, debugger_address, url, duration_seconds=60):
    """
    Retorna: "success", "account_error", "error"
    """
    driver, wait, actions = get_driver(driver_path, debugger_address)
    if not driver:
        return "error"

    try:
        driver.get(url)
        
        # 0. Verificación de salud inicial
        status = check_account_status(driver)
        if status != "ok":
            print(f"⚠️ Cuenta detectada como: {status}. Skipping.")
            return "account_error"
    
    # Limpieza de pestañas...
            for handle in handles:
                if handle != current_handle:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(current_handle)
    except: pass

    print(f"👀 Viendo video por {duration_seconds} segundos...")
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
                print("▶️ Play clicado.")
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
                print("🖱️ Movimiento de actividad simulado.")
            else:
                actions = ActionChains(driver)
                actions.move_by_offset(random.randint(-5, 5), random.randint(-5, 5)).perform()
        except:
            break
            
    print("✅ Tiempo de visualización completado.")
    return True



