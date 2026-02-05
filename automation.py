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


# ---------- FACEBOOK ----------
def get_driver(driver_path, debugger_address):
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", debugger_address)

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    wait = WebDriverWait(driver, 25)
    return driver, wait, ActionChains(driver)


def safe_reaction_click(driver, reaction_name):
    """
    Busca botones de reacción específicos para evitar clics en texto aleatorio.
    """
    print(f"🔎 Buscando reacción: {reaction_name}...")
    try:
        # Intentamos selectores más precisos primero (aria-label exacto en botones)
        # Facebook a veces usa "reaction_profile_..." o simplemente el nombre en aria-label
        xpaths = [
            f"//div[@aria-label='{reaction_name}' and @role='button']",
            f"//div[@aria-label='{reaction_name}']",
            f"//*[text()='{reaction_name}']" # Fallback ultimo recurso
        ]
        
        for xpath in xpaths:
            elements = driver.find_elements(By.XPATH, xpath)
            for el in elements:
                try:
                    if el.is_displayed():
                        # Verificar que no sea un texto gigante o comentario
                        size = el.size
                        if size['height'] > 100 or size['width'] > 200:
                            continue # Probablemente no sea el icono de reacción
                            
                        print(f"   ✅ Elemento encontrado con {xpath}. Click...")
                        
                        # Scroll y Click
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                        human_sleep(0.5, 1)
                        
                        try:
                            actions = ActionChains(driver)
                            actions.move_to_element(el).click().perform()
                        except:
                            driver.execute_script("arguments[0].click();", el)
                            
                        return True
                except:
                    continue
        
        print(f"❌ No se encontró botón visible para {reaction_name}")
        return False

    except Exception as e:
        print(f"❌ Error buscando elementos: {e}")
        return False


def react_to_post(driver_path, debugger_address, post_url, target_reaction="Me encanta"):
    driver, wait, actions = get_driver(driver_path, debugger_address)

    driver.get(post_url)

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

    human_sleep(4, 7)
    
    # Comportamiento humano antes de interactuar
    random_scroll(driver)

    try:
        # 1. Buscar el botón "Me gusta" principal (sin reaccionar aun)
        # Buscamos por aria-label "Me gusta" que sea un div role=button o similar
        like_btn_selectors = [
            "//div[@role='button' and @aria-label='Me gusta']",
            "//div[@aria-label='Me gusta' and contains(@class, 'x1i10hfl')]", # Clases comunes de FB
            "//span[text()='Me gusta']/ancestor::div[@role='button']"
        ]
        
        like_button = None
        for selector in like_btn_selectors:
            try:
                like_button = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                if like_button: break
            except:
                continue
                
        if not like_button:
            print("❌ No se encontró el botón principal de 'Me gusta'")
            return False
            
        # --- CASO ESPECIAL: "Me gusta" ---
        # Si la reacción es "Me gusta", no necesitamos el menú. Click directo.
        if target_reaction.lower() == "me gusta":
            print("👍 Reacción es 'Me gusta'. Click directo al botón principal.")
            try:
                actions.move_to_element(like_button).click().perform()
            except:
                driver.execute_script("arguments[0].click();", like_button)
            
            human_sleep(1, 2)
            print("✅ Click enviado a botón principal (Me gusta)")
            return True

        # --- OTRAS REACCIONES (Requieren Hover) ---
        # 2. Realizar Hover para que salgan las reacciones
        print("👆 Realizando Hover Robusto...")
        
        # A) Moverse al centro
        actions.move_to_element(like_button).perform()
        human_sleep(0.5, 1)
        
        # B) "Wiggle" (Pequeño movimiento dentro del elemento para despertar el JS)
        actions.move_by_offset(3, 3).perform() 
        human_sleep(0.5, 1)
        actions.move_by_offset(-2, -2).perform()
        human_sleep(1.5, 3)

        print(f"🎯 Buscando reacción: {target_reaction}")
        
        # 3. Click en la reacción específica
        success = safe_reaction_click(driver, target_reaction)

        human_sleep(1, 2)
        
        # Si falló, intentar un último recurso: Click largo (Long Press) si no apareció
        if not success:
            print("⚠️ Intento Fallback: Click largo sobre botón Me gusta...")
            actions.click_and_hold(like_button).pause(1.5).release().perform()
            human_sleep(2, 3)
            success = safe_reaction_click(driver, target_reaction)
        
        if success:
            print(f"✅ Reacción enviada: {target_reaction}")
            return True
        else:
            print(f"❌ Falló clic en: {target_reaction}")
            return False

    except Exception as e:
        print("❌ Error general reaccionando:")
        traceback.print_exc()
        return False



