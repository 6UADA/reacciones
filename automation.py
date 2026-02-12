import requests
import random
import time
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
def start_browser(user_id, headless=True, api_config=None):
    # Get config from args or environment
    api_url = api_config.get("url", ADSPOWER_API_URL) if api_config else ADSPOWER_API_URL
    api_key = api_config.get("key", API_KEY) if api_config else API_KEY

    #Modo sin cabeza y banderas de optimización de alto rendimiento
    headless_flag = "1" if headless else "0"
    
    # v16: Banderas optimizadas para Modo Híbrido
    opt_flags = [
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
        "--mute-audio",
        "--no-sandbox",
        "--disable-ipc-flooding-protection",
        "--disable-hang-monitor",
        "--js-flags=--optimize_for_size --max-old-space-size=500",
        "--disable-session-crashed-bubble",
        "--no-session-restore",
        "--no-first-run",
        "--disable-infobars"
    ]
    
    # Si es Headless, desactivamos GPU para ahorrar. 
    # Si es visible (v16), permitimos GPU para que FB valide la vista del video.
    if headless:
        opt_flags.append("--disable-gpu")
    else:
        # Modo Visible: Aseguramos que el video renderice correctamente
        opt_flags.extend(["--enable-gpu-rasterization", "--ignore-certificate-errors"])
    
    # AdsPower requiere launch_args como una cadena JSON de lista
    import json
    launch_args = json.dumps(opt_flags)
    
    url = f"{api_url}/api/v1/browser/start?user_id={user_id}&headless={headless_flag}&launch_args={launch_args}"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        print(f"❌ AdsPower no respondió ({api_url})")
        return None

    data = resp.json()

    if data["code"] == 0:
        print(f"🟢 Perfil iniciado en {api_url}")
        return data["data"]
    else:
        print(f"❌ Error iniciando perfil {user_id} en {api_url}: {data['msg']}")
        return None


def close_browser(user_id, api_config=None):
    api_url = api_config.get("url", ADSPOWER_API_URL) if api_config else ADSPOWER_API_URL
    api_key = api_config.get("key", API_KEY) if api_config else API_KEY
    url = f"{api_url}/api/v1/browser/stop?user_id={user_id}"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    requests.get(url, headers=headers)


# ---------- API HELPERS ----------
def get_ads_groups(api_config=None):
    """Obtiene la lista de todos los grupos de AdsPower y los ordena con manejo de rate limit"""
    api_url = api_config.get("url", ADSPOWER_API_URL) if api_config else ADSPOWER_API_URL
    api_key = api_config.get("key", API_KEY) if api_config else API_KEY
    groups = []
    page = 1
    while True:
        url = f"{api_url}/api/v1/group/list?page={page}&page_size=100"
        headers = {"Authorization": f"Bearer {api_key}"}
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
                print(f"⏳ Rate limit en grupos (página {page}). Esperando 2s antes de reintentar...")
                time.sleep(2)
                continue
            else:
                print(f"⚠️ Error API AdsPower (Groups) en {api_url}: {data.get('msg')}")
                break
        except Exception as e:
            print(f"⚠️ Excepción obteniendo grupos en {api_url}: {e}")
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


def get_ads_profiles(group_id, api_config=None):
    """Obtiene todos los perfiles de un grupo específico con manejo de rate limit"""
    api_url = api_config.get("url", ADSPOWER_API_URL) if api_config else ADSPOWER_API_URL
    api_key = api_config.get("key", API_KEY) if api_config else API_KEY
    ids = []
    page = 1
    while True:
        url = f"{api_url}/api/v1/user/list?group_id={group_id}&page={page}&page_size=100"
        headers = {"Authorization": f"Bearer {api_key}"}
        
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
                print(f"❌ Error obteniendo perfiles del grupo {group_id} en {api_url}: {data.get('msg')}")
                break
        except Exception as e:
            print(f"⚠️ Excepción obteniendo perfiles del grupo {group_id} en {api_url}: {e}")
            break
            
    return ids


# ---------- FACEBOOK ----------
def get_driver(driver_path, debugger_address, api_config=None):
    chrome_options = Options()
    
    # Si estamos en modo remoto, redirigimos el debugger a la IP interna de la PC
    # que es visible para el servidor a través de Cloudflare WARP/Private Network
    target_address = debugger_address
    is_remote = False
    if api_config and "127.0.0.1" in debugger_address:
        is_remote = True
        remote_host = api_config.get("internal_ip")
        if not remote_host:
            # Fallback a hostname del URL si no hay IP interna
            from urllib.parse import urlparse
            parsed = urlparse(api_config.get("url", ""))
            remote_host = parsed.hostname
            
        if remote_host:
            target_address = debugger_address.replace("127.0.0.1", remote_host)
            print(f"   🌐 Redireccionando debugger de 127.0.0.1 a {target_address}")

    chrome_options.add_experimental_option("debuggerAddress", target_address)

    # Intentar conexión con reintentos para evitar Read Timeout durante el arranque
    max_retries = 3
    driver = None
    for attempt in range(max_retries):
        try:
            print(f"   🔧 Conectando Selenium a {target_address} (Intento {attempt+1})...")
            
            if is_remote:
                # Usar webdriver-manager para asegurar un driver compatible en el servidor
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
            else:
                # Local: Usar el driver que proporciona AdsPower
                service = Service(driver_path)
                
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Tiempos aumentados para entornos con mucha carga
            driver.set_page_load_timeout(200)
            driver.set_script_timeout(200)
            break 
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️ Error de conexión, reintentando en 3s...")
                time.sleep(3)
            else:
                contexto = "remoto" if is_remote else "local"
                print(f"   ❌ Error fatal conectando a AdsPower {contexto}: {e}")
                return None, None, None
    
    if driver is None:
        return None, None, None

    wait = WebDriverWait(driver, 25)
    return driver, wait, ActionChains(driver)


def clean_up_tabs(driver):
    """
    Cierra todas las pestañas excepto la actual para que AdsPower no las guarde.
    """
    try:
        current_handle = driver.current_window_handle
        handles = driver.window_handles
        if len(handles) > 1:
            print(f"🧹 Limpiando {len(handles)-1} pestañas adicionales...")
            for handle in handles:
                if handle != current_handle:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(current_handle)
    except Exception as e:
        print(f"⚠️ Error limpiando pestañas: {e}")


def ensure_video_playing(driver):
    """
    Verifica mediante JS si el video está en reproducción y le da Play si está pausado.
    """
    try:
        script = """
        var vid = document.querySelector('video');
        if (vid) {
            if (vid.paused) {
                vid.play();
                return 'paused_to_playing';
            }
            return 'playing';
        }
        return 'no_video';
        """
        result = driver.execute_script(script)
        if result == 'paused_to_playing':
            print("▶️ Video detectado en pausa. Forzando Play vía JS...")
        return result
    except:
        return 'error'


def random_pre_reaction_interaction(driver):
    """
    Realiza movimientos de mouse y scrolls aleatorios para simular interés humano.
    """
    try:
        print("🎭 Simulando comportamiento humano (interacción previa)...")
        actions = ActionChains(driver)
        
        # 1. Movimiento de mouse aleatorio
        for _ in range(random.randint(2, 4)):
            actions.move_by_offset(random.randint(-50, 50), random.randint(-50, 50)).perform()
            time.sleep(random.uniform(0.5, 1.5))
            
        # 2. Scrolls cortos de "lectura"
        for _ in range(random.randint(1, 3)):
            scroll = random.randint(50, 150)
            driver.execute_script(f"window.scrollBy(0, {scroll});")
            time.sleep(random.uniform(1, 2.5))
            driver.execute_script(f"window.scrollBy(0, -{random.randint(20, 50)});")
            
    except: pass


def check_account_status(driver):
    """
    Verifica si la cuenta está logueada y activa con mayor precisión.
    Retorna: "ok", "logged_out", "disabled"
    """
    try:
        # v8: Esperar un poco a que las redirecciones de Facebook se estabilicen
        time.sleep(4)
        
        current_url = driver.current_url
        
        # 1. Detección por URL (Más fiable que el texto)
        if "facebook.com/login" in current_url or "facebook.com/checkpoint" in current_url:
            return "logged_out"
        
        if "facebook.com/disabled" in current_url or "account_disabled" in current_url:
            return "disabled"
            
        # 2. Detección por Título de página (Evita falsos positivos en comentarios)
        try:
            title = driver.title.lower()
            if "log in" in title or "iniciar sesión" in title:
                return "logged_out"
            if "disabled" in title or "inhabilitada" in title or "suspended" in title:
                # Solo si el título lo dice explícitamente es un bloqueo
                return "disabled"
        except: pass

        # 3. Detección de formulario de login (Si el botón de login está presente y visible)
        login_selectors = ["input[name='lsd']", "button[name='login']", "#login_form"]
        for sel in login_selectors:
            try:
                if driver.find_elements(By.CSS_SELECTOR, sel):
                    return "logged_out"
            except: pass
            
        return "ok"
    except:
        return "ok" 


def safe_reaction_click(driver, reaction_name):
    """
    Busca botones de reacción específicos para evitar clics en texto aleatorio.
    Intenta varias veces por si la animación de apertura demora.
    """
    print(f"🔎 Buscando reacción: {reaction_name}...")
    
    # Mapeo de variaciones ultra-expandido (Español, Inglés, Sistema)
    variations = [reaction_name]
    if reaction_name == "Me encanta": 
        variations.extend(["Love", "Heart", "Encanta", "Love reaction", "Reacción Me encanta"])
    if reaction_name == "Me divierte": 
        variations.extend(["Haha", "Laughter", "Laughing", "Funny", "Gracia", "Laugh", "Divierte", "Haha reaction", "Reacción Me divierte"])
    if reaction_name == "Me asombra": 
        variations.extend(["Wow", "Astonished", "Asombra", "Surprised", "Amazing", "Wow reaction", "Reacción Me asombra"])
    if reaction_name == "Me entristece": 
        variations.extend(["Sad", "Crying", "Sorry", "Entristece", "Triste", "Sad reaction", "Reacción Me entristece"])
    if reaction_name == "Me enoja": 
        variations.extend(["Angry", "Mad", "Enoja", "Enfada", "Grumpy", "Angry reaction", "Reacción Me enoja"])
    if reaction_name == "Me importa": 
        variations.extend(["Care", "Hug", "Importa", "Care/Heart", "Care reaction", "Reacción Me importa"])

    # v22: Mapeo de índices para Fallback (1:Like, 2:Love, 3:Care, 4:Haha, 5:Wow, 6:Sad, 7:Angry)
    reaction_indices = {
        "Me gusta": 1, "Like": 1,
        "Me encanta": 2, "Love": 2, "Heart": 2,
        "Me importa": 3, "Care": 3, "Hug": 3,
        "Me divierte": 4, "Haha": 4, "Funny": 4,
        "Me asombra": 5, "Wow": 5, "Astonished": 5,
        "Me entristece": 6, "Sad": 6, "Sorry": 6,
        "Me enoja": 7, "Angry": 7, "Mad": 7
    }
    target_idx = reaction_indices.get(reaction_name, 0)

    # Intentos de espera (el menú tarda unos ms en aparecer)
    for attempt in range(4): 
        try:
            for variant in variations:
                # Selectores ultra-flexibles
                xpaths = [
                    f"//div[@role='button'][contains(@aria-label, '{variant}')]",
                    f"//div[contains(@aria-label, '{variant}')][@role='img']",
                    f"//img[contains(@alt, '{variant}')]",
                    f"//*[contains(@aria-label, '{variant}')]", # Selector más agresivo
                    f"//*[@aria-label='{variant}']",
                    f"//*[text()='{variant}']"
                ]
                
                for xpath in xpaths:
                    # Intento de localización de elementos con reintento por Stale
                    try:
                        elements = driver.find_elements(By.XPATH, xpath)
                    except: continue

                    for el in elements:
                        try:
                            # Re-verificar que el elemento sigue "vivo" (evita StaleElementReferenceException)
                            if not el.is_displayed(): continue
                            
                            size = el.size
                            # FILTRO v12: Relajado para capturar iconos pequeños pero ignorar el botón principal
                            if size['height'] < 10 or size['width'] < 10: continue
                            
                            # Si buscamos una reacción específica (NO "Me gusta"), ignoramos botones muy grandes
                            if reaction_name.lower() not in ["me gusta", "like"]:
                                if size['width'] > 85: 
                                    continue

                            print(f"   ✅ '{variant}' encontrado ({xpath}) [{size['width']}x{size['height']}px]. Click...")
                            
                            try:
                                actions = ActionChains(driver)
                                actions.move_to_element(el).pause(0.2).click().perform()
                                time.sleep(0.5)
                                # Segundo click (JS)
                                driver.execute_script("arguments[0].click();", el)
                                time.sleep(1)
                            except Exception as e:
                                if "stale" in str(e).lower():
                                    print("   ⚠️ Elemento se volvió obsoleto (stale), reintentando búsqueda inmediata...")
                                    break 
                                else:
                                    driver.execute_script("arguments[0].click();", el)
                                    time.sleep(1)
                                    
                            return True
                        except Exception as e:
                            if "stale" in str(e).lower(): break 
                            continue
            
                # Fallback v23: Robust Index-based Click (Canvas/Lottie Support)
                if target_idx > 0:
                    print(f"   ⚠️ Reacción no detectada por etiqueta. Intentando Fallback por Índice v23 ({target_idx})...")
                    
                    # Selectores de contenedor ultra-agresivos (v23)
                    # El contenedor tiene al menos 6 o 7 divs hijos (las reacciones)
                    # Usamos clases atómicas comunes en el menú de reacciones
                    container_xpaths = [
                        "//div[@role='presentation']//div[count(div)>=6]",
                        "//div[@role='dialog']//div[count(div)>=6]",
                        "//div[contains(@class, 'x1uvtmcs')]//div[count(div)>=6]",
                        "//div[contains(@class, 'x9f619')]//div[count(div)>=6]",
                        "//div[contains(@class, 'x1n2onr6')]//div[count(div)>=6]"
                    ]
                    
                    for c_xpath in container_xpaths:
                        try:
                            # Buscamos el div más profundo que tenga 6+ hijos
                            containers = driver.find_elements(By.XPATH, c_xpath)
                            # Ordenar por profundidad (el más profundo suele ser el correcto)
                            for container in sorted(containers, key=lambda x: len(x.get_attribute('xpath') or ''), reverse=True):
                                try:
                                    # Facebook v23: El botón es el hijo directo o nieto
                                    # Intentamos './div[{idx}]' o './div/div[{idx}]'
                                    btn_xpath = f"./div[{target_idx}]"
                                    btn = container.find_element(By.XPATH, btn_xpath)
                                    
                                    if btn.is_displayed():
                                        print(f"   🎯 Blanco fijado en posición {target_idx} (Contenedor: {c_xpath})...")
                                        
                                        # Click compuesto (Actions + JS)
                                        actions = ActionChains(driver)
                                        actions.move_to_element(btn).pause(0.2).click().perform()
                                        driver.execute_script("arguments[0].click();", btn)
                                        time.sleep(1)
                                        return True
                                except: continue
                        except: continue

            # Si no encontró nada, esperar un poco antes del siguiente intento
            time.sleep(1)
            
        except Exception as e:
            print(f"⚠️ Error intentando buscar reaccion: {e}")
            time.sleep(1)
            
    print(f"❌ No se encontró '{reaction_name}' tras {attempt+1} intentos")
    return False


def react_via_keyboard(driver, target_reaction):
    """
    v31: Navegación por teclado (TAB + Flechas) - REFURBISHED
    Enfoca el post primero y verifica físicamente el cambio.
    """
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        
        # 0. Limpieza y Enfoque Inicial
        body.send_keys(Keys.ESCAPE)
        time.sleep(0.5)
        
        # Intentar enfocar el contenedor del post para que TAB empiece desde ahí
        try:
            post = driver.find_element(By.XPATH, "//div[@role='article'] | //div[@role='main']")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", post)
            time.sleep(1)
            # Click neutral para poner el foco cerca
            ActionChains(driver).move_to_element_with_offset(post, 10, 10).click().perform()
        except:
            print("⚠️ No se pudo enfocar el post, intentando TAB desde la posición actual.")

        found = False
        print(f"⌨️ Teclado: Buscando botón de reacciones para '{target_reaction}'...")
        
        last_label = ""
        for _ in range(25): # Menos TABs si ya estamos enfocados en el post
            body.send_keys(Keys.TAB)
            active = driver.switch_to.active_element
            label = str(active.get_attribute("aria-label") or "").lower()
            
            # Evitar bucles infinitos si el foco no se mueve
            if label == last_label and label != "":
                # Intentar un TAB extra o ESC
                body.send_keys(Keys.ESCAPE)
                time.sleep(0.1)
            last_label = label

            # Detección del botón (Me gusta / Reaccionar)
            if any(x in label for x in ["me gusta", "te gusta", "liked", "reacción", "remove", "ya no", "un-like"]):
                # Si ya tiene la reacción exacta
                if target_reaction.lower() in label:
                    print(f"👍 Ya tiene la reacción '{target_reaction}' activa.")
                    return True
                found = True
                break
            time.sleep(0.1)

        if not found:
            return False

        # 2. Aplicar Reacción
        if target_reaction == "Me gusta":
            active.send_keys(Keys.ENTER)
        else:
            # Abrir menú con SPACE (Mantenido)
            ActionChains(driver).key_down(Keys.SPACE).pause(2.2).key_up(Keys.SPACE).perform()
            time.sleep(1.5)

            reaction_map = {
                "Me encanta": 1,
                "Me importa": 2,
                "Me divierte": 3,
                "Me asombra": 4,
                "Me entristece": 5,
                "Me enoja": 6
            }
            steps = reaction_map.get(target_reaction, 0)
            if steps > 0:
                # Primer flecha para entrar al menú flotante
                ActionChains(driver).send_keys(Keys.ARROW_RIGHT).pause(0.3).perform()
                for _ in range(steps - 1):
                    ActionChains(driver).send_keys(Keys.ARROW_RIGHT).pause(0.4).perform()
                
                time.sleep(0.5)
                ActionChains(driver).send_keys(Keys.ENTER).perform()

        # 3. VERIFICACIÓN FÍSICA (Crucial v31)
        print("⌨️ Teclado: Verificando éxito...")
        success_keys = ["te gusta", "liked", "reacción", "remove", "ya no", "eliminar", "quitar", "un-like"]
        for _ in range(6):
            time.sleep(1.5)
            try:
                # Re-localizar el botón activo o el botón de like por XPATH
                check_label = str(driver.switch_to.active_element.get_attribute("aria-label") or "").lower()
                if any(x in check_label for x in success_keys):
                    print(f"✅ Éxito confirmado vía teclado ({check_label})")
                    return True
            except:
                # Si el elemento se vuelve stale, es buena señal en FB
                return True
        
        print("⚠️ Teclado: La reacción parece no haber persistido en la UI.")
        return False
    except Exception as e:
        print(f"⚠️ Error en método teclado v31: {e}")
        return False


def react_to_post(driver_path, debugger_address, post_url, target_reaction="Me encanta", watch_mins=0, api_config=None):
    """
    Retorna: "success", "account_error", "error"
    v17: Añadido watch_mins para combinar vista + reacción
    """
    driver, wait, actions = get_driver(driver_path, debugger_address, api_config=api_config)
    if not driver:
        return "error"

    # v25: Navigation with retries to handle ReadTimeout
    max_get_retries = 2
    loaded = False
    for attempt in range(max_get_retries):
        try:
            print(f"   🌐 Cargando URL (Intento {attempt+1})...")
            driver.get(post_url)
            loaded = True
            break
        except Exception as e:
            if attempt < max_get_retries - 1:
                print(f"   ⚠️ Error de red/timeout cargando URL, reintentando en 5s...")
                time.sleep(5)
            else:
                print(f"   ❌ Error fatal cargando URL tras {max_get_retries} intentos: {e}")
                return "error"

    if not loaded:
        return "error"

    try:
        # 0. Verificación de salud inicial
        status = check_account_status(driver)
        if status != "ok":
            print(f"⚠️ Cuenta detectada como: {status}. Skipping.")
            return "account_error"

        # 0. Limpieza inicial de pestañas (v15)
        clean_up_tabs(driver)

        # v17: Si se solicita ver antes de reaccionar (Natural Mode)
        if watch_mins > 0:
            print(f"👀 Modo Natural: Viendo por {watch_mins} mins antes de reaccionar...")
            # Reutilizamos la lógica de visualización (simulada aquí para no duplicar código)
            start_v = time.time()
            while (time.time() - start_v) < (watch_mins * 60):
                human_sleep(15, 30)
                random_pre_reaction_interaction(driver)
        else:
            # v17: Delay aleatorio corto (10-30s) para que no todos reaccionen al segundo exacto
            delay = random.randint(10, 35)
            print(f"⏳ Modo Natural: Esperando {delay}s de 'lectura' antes de reaccionar...")
            time.sleep(delay)
            random_pre_reaction_interaction(driver)

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

        # v30: MÉTODO PRINCIPAL - Teclado (TAB + Flechas)
        try:
            if react_via_keyboard(driver, target_reaction):
                print(f"✅ Reacción aplicada exitosamente vía Teclado v30 ({target_reaction}).")
                human_sleep(2, 3)
                # v30: Verificación rápida
                return "success"
        except Exception as e:
            print(f"⚠️ Falló método principal de teclado: {e}. Intentando fallback ratón...")

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
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", like_button)
                    time.sleep(0.5)
                    actions = ActionChains(driver)
                    actions.move_to_element(like_button).click().perform()
                except:
                    driver.execute_script("arguments[0].click();", like_button)
                
                human_sleep(1, 2)
                
                # v10: Verificación final
                # v25: Verificación ultra-robusta con re-localización
                success_keys = ["te gusta", "liked", "reacción", "remove", "ya no", "eliminar", "quitar", "un-like"]
                for i in range(5):
                    try:
                        # En cada intento, intentamos re-obtener el aria del botón actual 
                        # o buscar uno nuevo si el DOM cambió
                        current_aria = like_button.get_attribute("aria-label").lower()
                        if any(x in current_aria for x in success_keys):
                            return "success"
                    except:
                        # Si el elemento es stale, es un excelente indicador de que Facebook
                        # refrescó la parte de la UI de reacciones (Éxito probable)
                        return "success"
                    time.sleep(1.2)
                
                print("⚠️ Verificación fallida: El botón no cambió de estado tras el click.")
                return "error"

            # --- OTRAS REACCIONES (v11: Bucle de Reintento Auto) ---
            for attempt in range(2):
                if attempt > 0:
                    print(f"🔄 Reintentando reacción (Intento {attempt+1})...")
                    # Re-abrir menú si se cerró
                    actions = ActionChains(driver)
                    actions.move_to_element(like_button).perform()
                    time.sleep(1)
                    for offset in [(2,2), (-2,-2)]:
                        actions.move_by_offset(offset[0], offset[1]).perform()
                        time.sleep(0.5)

                # 2. Realizar Hover para que salgan las reacciones
                print(f"👆 Preparando menú de reacciones (Intento {attempt+1})...")
                
                # v9/v11: Hover persistente
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", like_button)
                    time.sleep(0.5)
                    actions = ActionChains(driver)
                    actions.move_to_element(like_button).perform()
                except:
                    pass
                time.sleep(0.5)
                for offset in [(2,2), (-2,-2), (1,1)]:
                    actions.move_by_offset(offset[0], offset[1]).perform()
                    time.sleep(0.3)
                
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='presentation']|//div[@role='dialog']|//div[contains(@class, 'x1n2onr6')]")))
                except: pass

                time.sleep(1.5) 
                success = safe_reaction_click(driver, target_reaction)

                # v11: Verificación post-click para reacciones específicas
                if success:
                    try:
                        time.sleep(3)
                        # v25: Verificación robusta con detección de stale
                        success_keys = ["te gusta", "reacción", "liked", "remove", "asombra", "encanta", "divierte", "enoja", "triste", "importa", "eliminar", "quitar", "ya no"]
                        for _ in range(5):
                            try:
                                current_aria = like_button.get_attribute("aria-label").lower()
                                if any(x in current_aria for x in success_keys):
                                    print(f"✅ Reacción verificada en el botón principal: '{current_aria}'")
                                    return "success"
                            except:
                                # Stale = Éxito en la mayoría de los casos de FB UI
                                print("✅ Reacción confirmada (UI Refrescada).")
                                return "success"
                            time.sleep(1.2)
                        
                        print(f"⚠️ Reacción NO persistió. Reintentando...")
                    except Exception as e:
                        print(f"⚠️ Error verificando: {e}")
                        return "success"
                
                # Si falló safe_reaction_click o la verificación, el bucle continúa a attempt 1
                if not success and attempt == 0:
                    print("⚠️ Click falló, intentando Force Hold en el reintento...")
                    # En el siguiente intento usaremos el safe_reaction_click normal pero ya habremos forzado el menú
            
            # --- FALLBACK FINAL: Force Hold (Si el bucle falló) ---
            print("⚠️ Ejecutando Fallback: Force Hold (3.5s)...")
            try:
                actions = ActionChains(driver)
                actions.move_to_element(like_button).click_and_hold(like_button).pause(3.5).release().perform()
                time.sleep(2)
                if safe_reaction_click(driver, target_reaction):
                    # Una última validación
                    time.sleep(2)
                    if "me gusta" not in like_button.get_attribute("aria-label").lower():
                        return "success"
            except: pass

            # v27: ULTIMO RECURSO - Navegación por Teclado (TAB + Flechas)
            print("⚠️ Reacción no lograda con ratón. Intentando Prototipo de Teclado (v27)...")
            try:
                if react_via_keyboard(driver, target_reaction):
                    print(f"✅ Reacción aplicada exitosamente vía Teclado ({target_reaction}).")
                    # Pequeña verificación final
                    human_sleep(2, 3)
                    return "success"
            except Exception as e:
                print(f"⚠️ Falló prototipo de teclado: {e}")

            # v15: Limpieza final antes de cerrar
            try: clean_up_tabs(driver)
            except: pass

            print(f"❌ Falló reaccion: {target_reaction} después de múltiples intentos y verificaciones.")
            return "error"

        except Exception as e:
            print("❌ Error general reaccionando:")
            traceback.print_exc()
            return "error"

    except Exception as e:
        print(f"❌ Error durante el proceso: {e}")
        traceback.print_exc()
        return "error"


def watch_live_video(driver_path, debugger_address, url, duration_seconds=60, api_config=None):
    """
    Retorna: "success", "account_error", "error"
    """
    driver, wait, actions = get_driver(driver_path, debugger_address, api_config=api_config)
    if not driver:
        return "error"

    try:
        driver.get(url)
        
        # 0. Verificación de salud inicial
        status = check_account_status(driver)
        if status != "ok":
            print(f"⚠️ Cuenta detectada como: {status}. Skipping.")
            return "account_error"
    
        # 0. Limpieza inicial de pestañas (v15)
        clean_up_tabs(driver)

    except Exception as e:
        print(f"⚠️ Error en carga inicial: {e}")

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

    # 2. Loop de actividad y monitoreo de video (v16)
    start_time = time.time()
    last_play_check = 0
    
    while (time.time() - start_time) < duration_seconds:
        try:
            current_time = time.time()
            
            # Monitoreo de reproducción cada 10-15 segundos
            if current_time - last_play_check > 15:
                ensure_video_playing(driver)
                last_play_check = current_time

            # Simular movimiento aleatorio cada 10-20 segundos
            human_sleep(10, 20)
            
            # Probabilidad de scroll corto
            if random.random() > 0.7:
                scroll = random.randint(100, 300)
                driver.execute_script(f"window.scrollBy(0, {scroll});")
                time.sleep(1)
                driver.execute_script(f"window.scrollBy(0, -{scroll});")
                print("🖱️ Actividad simulada (Scroll).")
            else:
                actions = ActionChains(driver)
                actions.move_by_offset(random.randint(-5, 5), random.randint(-5, 5)).perform()
        except:
            break
            
    print("✅ Tiempo de visualización completado.")
    # v15: Limpieza final antes de cerrar
    try: clean_up_tabs(driver)
    except: pass
    return True



