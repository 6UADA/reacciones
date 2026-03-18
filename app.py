from flask import Flask, render_template, request, jsonify, session
import os
import sys
import json
import threading
import time
from dotenv import load_dotenv

# --- CARGA DE CONFIGURACIÓN INICIAL (DEBE SER ANTES DE OTROS IMPORTS) ---
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    load_dotenv(os.path.join(exe_dir, '.env'))
else:
    load_dotenv()

import automation  # Ahora automation cargará las variables correctas del .env
from logger_shared import log_to_web, get_logs

# --- DETERMINAR RUTA BASE PARA RECURSOS ---
if getattr(sys, 'frozen', False):
    # Si es un ejecutable (PyInstaller), los recursos están en _MEIPASS
    base_path = sys._MEIPASS
else:
    # Si es un script normal, los recursos están en el directorio actual
    base_path = os.path.abspath(".")

template_dir = os.path.join(base_path, 'templates')
static_dir = os.path.join(base_path, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key-123')

app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key-123')

@app.route('/api/debug_logs')
def get_debug_logs():
    return jsonify(get_logs())

# Configuración de computadoras disponibles
AVAILABLE_COMPUTERS = {
    "chihuahua_1": {"name": "Chihuahua 1", "url": "https://chihuahua1.maxtres.org", "id": "chihuahua_1"},
    "chihuahua_2": {"name": "Chihuahua 2", "url": "https://chihuahua2.maxtres.org", "id": "chihuahua_2"},
    "chihuahua_3": {"name": "Chihuahua 3", "url": "https://chihuahua3.maxtres.org", "id": "chihuahua_3"},
    "sinaloa_1": {"name": "Sinaloa 1", "url": "https://sinaloa1.maxtres.org", "id": "sinaloa_1"},
    "sinaloa_2": {"name": "Sinaloa 2", "url": "https://sinaloa2.maxtres.org", "id": "sinaloa_2"},
    "quintanaroo_1": {"name": "Quintana Roo 1", "url": "https://quintanaroo1.maxtres.org", "id": "quintanaroo_1"},
    "quintanaroo_2": {"name": "Quintana Roo 2", "url": "https://quintanaroo2.maxtres.org", "id": "quintanaroo_2"},
    "torreon_1": {"name": "Torreón 1", "url": "https://torreon1.maxtres.org", "id": "torreon_1"},
    "torreon_2": {"name": "Torreón 2", "url": "https://torreon2.maxtres.org", "id": "torreon_2"},
    "tijuana_1": {"name": "Tijuana 1", "url": "https://tijuana1.maxtres.org", "id": "tijuana_1"},
    "tijuana_1": {"name": "Tijuana 1", "url": "https://tijuana1.maxtres.org", "id": "tijuana_1"},
    "guada": {"name": "Guada", "url": "https://guada.maxtres.org", "id": "guada"}
}

# Identidad de esta instancia (se carga del .env)
MY_ID = os.getenv('MY_COMPUTER_ID', 'guada')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/local_groups')
def local_groups():
    """Ruta interna: Lee los grupos directamente de AdsPower en la máquina física actual"""
    try:
        groups = automation.get_ads_groups()
        return jsonify(groups)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/groups')
def get_groups():
    """Ruta UI: Pide los grupos redirigiendo a la PC seleccionada mediante Cloudflare"""
    selected_id = session.get('selected_computer', MY_ID)
    
    target_pc = AVAILABLE_COMPUTERS.get(selected_id)
    if not target_pc:
        log_to_web(f"❌ Error: Computadora '{selected_id}' no existe en la lista.", "error")
        return jsonify({"error": "Computadora no encontrada"}), 404
        
    log_to_web(f"📡 Solicitando grupos vía Cloudflare a: {target_pc['url']}", "info")
    try:
        import requests
        resp = requests.get(f"{target_pc['url']}/api/local_groups", timeout=10)
        if resp.status_code == 200:
            log_to_web(f"✅ Grupos recibidos desde {target_pc['name']}", "success")
            return jsonify(resp.json())
        else:
            log_to_web(f"❌ Error Cloudflare ({resp.status_code}): {resp.text}", "error")
            return jsonify({"error": f"Error remoto ({resp.status_code}): {resp.text}"}), 502
    except Exception as e:
        log_to_web(f"❌ Fallo total conexión: {str(e)}", "error")
        return jsonify({"error": f"No se pudo contactar {target_pc['url']} a través de Cloudflare: {str(e)}"}), 502

@app.route('/api/computers')
def get_computers():
    filtered_computers = {k: v for k, v in AVAILABLE_COMPUTERS.items() if k != 'guada'}
    return jsonify({
        "available": filtered_computers,
        "selected": session.get('selected_computer', MY_ID),
        "this_machine": MY_ID
    })

@app.route('/api/set_computer', methods=['POST'])
def set_computer():
    data = request.json
    comp_id = data.get('computer_id')
    if comp_id in AVAILABLE_COMPUTERS:
        session['selected_computer'] = comp_id
        return jsonify({"status": "success", "message": f"Computadora seleccionada: {AVAILABLE_COMPUTERS[comp_id]['name']}"})
    return jsonify({"status": "error", "message": "Computadora no válida"}), 400

@app.route('/api/local_start_campaign', methods=['POST'])
def local_start_campaign():
    """Ruta interna: Ejecuta los hilos físicamente en la máquina que recibe esta petición"""
    data = request.json
    url = data.get('url')
    group_id = data.get('group_id')
    end_group_id = data.get('end_group_id')
    duration_mins = float(data.get('duration_mins', 1))

    if not group_id:
        return jsonify({"status": "error", "message": "Debes seleccionar un grupo de AdsPower."}), 400

    # Verificación preliminar de perfiles antes de lanzar el hilo
    try:
        all_groups = automation.get_ads_groups()
        target_group = next((g for g in all_groups if str(g['group_id']) == str(group_id)), None)
        if not target_group:
             return jsonify({"status": "error", "message": f"El grupo ID {group_id} no existe en este AdsPower."}), 400
             
        profiles = automation.get_ads_profiles(group_id)
        if not profiles:
             return jsonify({"status": "error", "message": f"El grupo '{target_group.get('group_name')}' está vacío en AdsPower."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error conectando con AdsPower local: {str(e)}"}), 500

    assignments = []
    thread = threading.Thread(target=run_batch, args=(assignments, url, duration_mins, group_id, end_group_id))
    thread.start()
    
    return jsonify({"status": "started", "message": f"Campaña recibida correctamente. Iniciando {len(profiles)} perfiles..."})

@app.route('/start_campaign', methods=['POST'])
def start_campaign():
    """Ruta UI: Envía el inicio de campaña entero a la computadora objetivo a través de Cloudflare"""
    data = request.json
    selected_id = session.get('selected_computer', MY_ID)
    
    target_pc = AVAILABLE_COMPUTERS.get(selected_id)
    
    if not target_pc:
        log_to_web(f"❌ Error: Destino '{selected_id}' no encontrado para iniciar campaña.", "error")
        return jsonify({"status": "error", "message": "Computadora destino no encontrada"}), 400

    log_to_web(f"🚀 Enviando orden de inicio vía Cloudflare a: {target_pc['name']} ({target_pc['url']})", "info")
    try:
        import requests
        resp = requests.post(f"{target_pc['url']}/api/local_start_campaign", json=data, timeout=15)
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            return jsonify({"status": "error", "message": f"Error en PC destino ({resp.status_code}): {resp.text}"}), 502
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fallo al contactar PC destino via Cloudflare: {e}"}), 502

from concurrent.futures import ThreadPoolExecutor

def run_batch(assignments, url, duration_mins=1, group_id=None, end_group_id=None):
    print(f"🚀 Iniciando procesamiento LOCAL en este servidor para {url} (Vistas: {duration_mins} min)")

    if group_id:
        print("📥 Cargando perfiles de AdsPower a nivel local...")
        all_groups = automation.get_ads_groups()
        range_profiles = []
        in_range = False
        for g in all_groups:
            gid = str(g['group_id'])
            if gid == str(group_id): in_range = True
            if in_range:
                print(f"   📥 Extrayendo perfiles del grupo: {g['group_name']}...")
                range_profiles.extend(automation.get_ads_profiles(gid))
            if end_group_id and gid == str(end_group_id): break
            if not end_group_id: break

        print(f"✅ Extracción completada. {len(range_profiles)} perfiles encontrados en la máquina.")

        for pid in range_profiles:
            assignments.append({"profile_id": pid})

        import random
        random.shuffle(assignments)

    if not assignments:
        print("❌ No hay perfiles asignados. Abortando campaña.")
        return

    summary = {}
    summary_lock = threading.Lock()
    
    def process_profile(task, index):
        pid = task['profile_id']
        
        # Ejecución escalonada
        delay = index * 8 
        print(f"⏳ Perfil {pid} esperando {delay}s para arrancar...")
        time.sleep(delay)
        
        print(f"🟢 Perfil {pid} iniciando en la PC actual...")
        
        data = automation.start_browser(pid)
        if not data:
            print(f"❌ Error iniciando {pid}")
            return
            
        is_success = False
        try:
            is_success = automation.watch_live_video(
                data["webdriver"],
                data["ws"]["selenium"],
                url,
                duration_seconds=int(duration_mins * 60)
            )
        except Exception as e:
            print(f"❌ Error en automatización ({pid}): {e}")
            
        if is_success:
            with summary_lock:
                summary["Views completadas"] = summary.get("Views completadas", 0) + 1
            
        automation.close_browser(pid)

    # Límite de 100 perfiles concurrentes abriéndose localmente
    max_workers = 100
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i, task in enumerate(assignments):
            executor.submit(process_profile, task, i)
            
    print("\n" + "="*30)
    print("📢 REPORTE FINAL DE CAMPAÑA DE VISUALIZACIONES")
    print(f"🔗 URL: {url}")
    if not summary:
        print("❌ Ninguna acción exitosa.")
    else:
        parts = [f"{k}: {v}" for k, v in summary.items()]
        print(", ".join(parts))
    print("="*30 + "\n")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
