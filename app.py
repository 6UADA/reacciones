from flask import Flask, render_template, request, jsonify, session
import os
import json
import threading
import time
import automation
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key-123')

# Configuración de computadoras disponibles
AVAILABLE_COMPUTERS = {
    "chihuahua_2": {
        "name": "Chihuahua 2",
        "url": "https://chihuahua2.maxtres.org"
    },
    "chihuahua_1": {
        "name": "Chihuahua",
        "url": "https://chihuahua1.maxtres.org"
    },
    "torreon": {
        "name": "Torreón",
        "url": "https://torreon1.maxtres.org"
    },
    "sinaloa": {
        "name": "Sinaloa",
        "url": "https://sinaloa1.maxtres.org"
    },
    "quintanaroo": {
        "name": "Quintana Roo",
        "url": "https://quintanaroo1.maxtres.org"
    }
}

# v38: Identidad de esta PC (debe coincidir con una key de AVAILABLE_COMPUTERS para ser "local")
# Si no está definido en .env, asumimos que estamos en chihuahua_2 (Master por defecto)
MY_COMPUTER_ID = os.getenv('CURRENT_COMPUTER_ID', 'chihuahua_2')

# Ya no usamos profiles.json, todo se maneja dinámicamente con AdsPower

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/groups')
def get_groups():
    selected_id = session.get('selected_computer', 'chihuahua_2')
    
    # 1. Si es LOCAL, usamos automation.py directo
    if selected_id == MY_COMPUTER_ID:
        try:
            groups = automation.get_ads_groups()
            return jsonify(groups)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # 2. Si es REMOTO, pedimos los grupos a esa PC
    target_pc = AVAILABLE_COMPUTERS.get(selected_id)
    if not target_pc:
        return jsonify({"error": "Computadora no encontrada"}), 404
        
    try:
        # Hacemos request a la API de la otra PC
        # Nota: La otra PC ejecutará su propia versión de 'get_groups' (que caerá en el caso LOCAL)
        import requests
        resp = requests.get(f"{target_pc['url']}/api/groups", timeout=5)
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            return jsonify({"error": f"Error remoto: {resp.status_code}"}), 502
    except Exception as e:
        return jsonify({"error": f"Error conexión: {str(e)}"}), 502

@app.route('/api/computers')
def get_computers():
    return jsonify({
        "available": AVAILABLE_COMPUTERS,
        "selected": session.get('selected_computer', 'chihuahua_2')
    })

@app.route('/api/set_computer', methods=['POST'])
def set_computer():
    data = request.json
    comp_id = data.get('computer_id')
    if comp_id in AVAILABLE_COMPUTERS:
        session['selected_computer'] = comp_id
        return jsonify({"status": "success", "message": f"Computadora cambiada a {AVAILABLE_COMPUTERS[comp_id]['name']}"})
    return jsonify({"status": "error", "message": "Computadora no válida"}), 400

@app.route('/api/relay_task', methods=['POST'])
def relay_task():
    """
    Endpoint para recibir una tarea de otro servidor y ejecutarla LOCALMENTE.
    Llama a automation.py directamente (que es local-only).
    """
    data = request.json
    pid = data.get('profile_id')
    reaction = data.get('reaction')
    url = data.get('url')
    duration_mins = float(data.get('duration_mins', 1))
    
    print(f"📡 Recibido relevo: {pid} -> {reaction}")
    
    # IMPORTANTE: automation.py es local, así que llamamos directo sin configs
    browser_data = automation.start_browser(pid)
    if not browser_data:
         return jsonify({"status": "error", "message": "No se pudo iniciar navegador localmente"}), 500
         
    status = "error"
    try:
        if reaction == "Solo Views":
             success = automation.watch_live_video(
                 browser_data["webdriver"],
                 browser_data["ws"]["selenium"],
                 url,
                 duration_seconds=int(duration_mins * 60)
             )
        else:
             success = automation.react_to_post(
                 browser_data["webdriver"], 
                 browser_data["ws"]["selenium"],
                 url,
                 target_reaction=reaction
             )
        status = "success" if success else "error"
    except Exception as e:
        print(f"❌ Error en relevo: {e}")
        status = "error"
        
    automation.close_browser(pid)
    return jsonify({"status": status})

import random

@app.route('/start_campaign', methods=['POST'])
def start_campaign():
    data = request.json
    url = data.get('url')
    # counts espera estructura: {"Me encanta": 5, "Me asombra": 2}
    counts = data.get('counts', {}) 
    group_id = data.get('group_id')
    end_group_id = data.get('end_group_id')
    
    active_profiles = []
    total_needed = sum(int(c) for c in counts.values())

    if not group_id:
        return jsonify({"status": "error", "message": "Debes seleccionar un grupo de AdsPower o un rango."}), 400

    assignments = [] # Se llenará en el hilo run_batch

    # Asignar a hilo de ejecución de forma segura
    duration_mins = float(data.get('duration_mins', 1))
    target_computer_id = session.get('selected_computer', 'chihuahua_2')
    
    # Nuevo: Pasamos la configuración del rango al hilo si existe
    thread = threading.Thread(target=run_batch, args=(assignments, url, duration_mins, counts, group_id, end_group_id, target_computer_id))
    thread.start()
    
    msg = f"Campaña iniciada para {total_needed} perfiles."
    if group_id:
        msg = f"Iniciando extracción y campaña para el rango de grupos..."
        

    msg = f"Iniciando extracción y campaña para el rango de grupos..."

    return jsonify({"status": "started", "message": msg})

from concurrent.futures import ThreadPoolExecutor

def run_batch(assignments, url, duration_mins=1, counts=None, group_id=None, end_group_id=None, target_computer_id='chihuahua_2'):
    print(f"🚀 Iniciando campaña simultánea para {url} (Vistas: {duration_mins} min)")
    print(f"💻 Computadora objetivo: {target_computer_id}")


    # Si tenemos rango de grupos, cargamos los perfiles AQUÍ en el hilo
    if group_id and counts:
        print("📥 Cargando perfiles de los grupos seleccionados...")
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
            if not end_group_id: break # Si solo es un grupo

        print(f"✅ Extracción completada. {len(range_profiles)} perfiles encontrados.")

        # Re-armar los assignments con los perfiles reales
        new_assignments = []
        current_idx = 0
        total_needed = sum(int(c) for c in counts.values())

        # Limitamos a los perfiles que encontramos
        selected_ids = range_profiles[:total_needed]

        for reaction, count in counts.items():
            count = int(count)
            for _ in range(count):
                if current_idx < len(selected_ids):
                    new_assignments.append({
                        "profile_id": selected_ids[current_idx],
                        "reaction": reaction
                    })
                    current_idx += 1

        random.shuffle(new_assignments)
        assignments = new_assignments

    if not assignments:
        print("❌ No hay perfiles asignados. Abortando campaña.")
        return

    summary = {} # Contador compartido
    summary_lock = threading.Lock() # Bloqueo para hilos
    
    def process_profile(task, index):
        pid = task['profile_id']
        reaction = task['reaction']
        
    # v6: Arranque escalonado (cada perfil espera un poco más que el anterior)
        # Ejecución escalonada para no saturar el PC
        delay = index * 8 # 8 segundos entre cada arranque
        print(f"⏳ Perfil {pid} esperando {delay}s para arrancar...")
        time.sleep(delay)
        
        # --- LÓGICA DE RELAY ---
        is_remote = (target_computer_id != MY_COMPUTER_ID)
        
        if is_remote:
            # ENVIAR TAREA A OTRA PC
            target_pc = AVAILABLE_COMPUTERS.get(target_computer_id)
            if target_pc:
                print(f"📡 Relevando tarea {pid} a {target_pc['name']} ({target_pc['url']})...")
                try:
                    import requests
                    relay_url = f"{target_pc['url']}/api/relay_task"
                    resp = requests.post(relay_url, json={
                        "profile_id": pid,
                        "reaction": reaction,
                        "url": url,
                        "duration_mins": duration_mins
                    }, timeout=300)
                    
                    if resp.status_code == 200:
                        remote_status = resp.json().get("status", "error")
                        if remote_status == "success":
                            with summary_lock:
                                summary[reaction] = summary.get(reaction, 0) + 1
                    else:
                        print(f"❌ Error relay {resp.status_code}")
                except Exception as e:
                    print(f"❌ Error conexión relay: {e}")
            else:
                print(f"❌ PC destino no encontrada: {selected_id}")
            # Terminamos aquí para este perfil (ya fue procesado remotamente)
            return

        # --- EJECUCIÓN LOCAL (Si soy la PC destino) ---
        print(f"🟢 Perfil {pid} iniciando...")
        
        # Iniciar navegador
        data = automation.start_browser(pid)
        if not data:
            print(f"❌ Error iniciando {pid}")
            return
            
        is_success = False
        try:
            if reaction == "Solo Views":
                is_success = automation.watch_live_video(
                    data["webdriver"],
                    data["ws"]["selenium"],
                    url,
                    duration_seconds=int(duration_mins * 60)
                )
            else:
                is_success = automation.react_to_post(
                    data["webdriver"],
                    data["ws"]["selenium"],
                    url,
                    target_reaction=reaction
                )
        except Exception as e:
            print(f"❌ Error en automatización ({pid}): {e}")
            
        if is_success:
            with summary_lock:
                summary[reaction] = summary.get(reaction, 0) + 1
            
        automation.close_browser(pid)

    # Lanzar hilos (Aumentado a 90 por solicitud del usuario)
    max_workers = 90
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i, task in enumerate(assignments):
            executor.submit(process_profile, task, i)
            
    # --- REPORTE FINAL ---
    print("\n" + "="*30)
    print("📢 REPORTE FINAL DE CAMPAÑA SIMULTÁNEA")
    print(f"🔗 URL: {url}")
    print("Resultados:")
    if not summary:
        print("❌ Ninguna acción exitosa.")
    else:
        parts = [f"{k}: {v}" for k, v in summary.items()]
        print(", ".join(parts))
    print("="*30 + "\n")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
