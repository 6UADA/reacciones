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

POST_URL = "https://www.facebook.com/share/r/1XAkkQ5Kc9/"
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
    Busca todos los elementos que contengan el reaction_name en su aria-label,
    y da clic al primero que sea VISIBLE.
    """
    print(f"🔎 Buscando reacción visible: {reaction_name}...")
    try:
        # Buscar TODOS los candidatos (aria-label O texto visible)
        xpath = f"//*[contains(@aria-label, '{reaction_name}') or contains(text(), '{reaction_name}')]"
        elements = driver.find_elements(By.XPATH, xpath)
        
        print(f"   -> Encontrados {len(elements)} candidatos.")

        for i, el in enumerate(elements):
            try:
                if el.is_displayed():
                    print(f"   ✅ Candidato {i+1} es VISIBLE. Intentando click...")
                    
                    # 1. Intentar Click directo con Acción (Mouse real)
                    try:
                        actions = ActionChains(driver)
                        actions.move_to_element(el).click().perform()
                    except:
                        driver.execute_script("arguments[0].click();", el)

                    human_sleep(0.5, 1)

                    # 2. Intentar Click en el PADRE (por si el texto no es clickeable)
                    try:
                        parent = el.find_element(By.XPATH, "..")
                        driver.execute_script("arguments[0].click();", parent)
                    except:
                        pass
                    
                    return True
            except:
                pass
        
        print(f"❌ Ningún candidato visible encontrado para {reaction_name}")
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

    try:
        # Botón principal de reacción
        like_button = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@role='button' and contains(@aria-label,'Me gusta')]")
            )
        )

        # ¿Ya reaccionó?
        # if like_button.get_attribute("aria-pressed") == "true":
        #    print("⚠️ Ya tenía reacción, se omite")
        #    return

        # Hover para mostrar reacciones
        actions.move_to_element(like_button).perform()
        human_sleep(2, 4)

        # Diccionario solo para validar nombre vs texto, aunque safe_reaction_click usa el texto directo para buscar
        # Entonces solo pasamos el target_reaction directo.
        
        print(f"🎯 Intentando aplicar reacción: {target_reaction}")
        
        # Intentar click seguro
        success = safe_reaction_click(driver, target_reaction)

        human_sleep(1, 2)
        
        if success:
            print(f"✅ Reacción enviada: {target_reaction}")
        else:
            print(f"❌ No se pudo enviar reacción: {target_reaction}")
        human_sleep(2, 4)

    except Exception as e:
        print("❌ Error reaccionando:")
        traceback.print_exc()



