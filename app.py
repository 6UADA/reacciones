from flask import Flask, render_template, request, jsonify
import json
import threading
import time
import automation
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Cargar perfiles
def load_profiles():
    with open('profiles.json', 'r') as f:
        return json.load(f)

@app.route('/')
def index():
    profiles = load_profiles()
    return render_template('index.html', profiles=profiles)

import random

@app.route('/start_campaign', methods=['POST'])
def start_campaign():
    data = request.json
    url = data.get('url')
    # counts espera estructura: {"Me encanta": 5, "Me asombra": 2}
    counts = data.get('counts', {}) 
    
    profiles = load_profiles()
    active_profiles = [p['id'] for p in profiles if p['status'] == 'active']
    
    total_needed = sum(int(c) for c in counts.values())
    
    if total_needed > len(active_profiles):
        return jsonify({"status": "error", "message": f"No hay suficientes perfiles. Necesitas {total_needed}, tienes {len(active_profiles)}"}), 400

    # 1. Seleccionar perfiles al azar
    selected_ids = random.sample(active_profiles, total_needed)
    
    # 2. Asignar reacciones a cada ID
    assignments = []
    current_idx = 0
    for reaction, count in counts.items():
        count = int(count)
        for _ in range(count):
            assignments.append({
                "profile_id": selected_ids[current_idx],
                "reaction": reaction
            })
            current_idx += 1
            
            
    # 2.5 Mezclar el orden de ejecución para mayor naturalidad
    random.shuffle(assignments)

    # 3. Lanzar hilo en background
    duration_mins = float(data.get('duration_mins', 1))
    thread = threading.Thread(target=run_batch, args=(assignments, url, duration_mins))
    thread.start()
    
    return jsonify({"status": "started", "message": f"Campaña iniciada con {total_needed} perfiles."})

from concurrent.futures import ThreadPoolExecutor

def run_batch(assignments, url, duration_mins=1):
    print(f"🚀 Iniciando campaña simultánea para {url} (Vistas: {duration_mins} min)")
    
    summary = {} # Contador compartido
    summary_lock = threading.Lock() # Bloqueo para hilos
    
    def process_profile(task, index):
        pid = task['profile_id']
        reaction = task['reaction']
        
        # v6: Arranque escalonado (cada perfil espera un poco más que el anterior)
        # Esto evita abrir 20 Chromes al mismo segundo
        wait_time = index * 4 # 4 segundos entre arranques
        print(f"⏳ Perfil {pid} esperando {wait_time}s para arrancar...")
        time.sleep(wait_time)
        
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

    # Lanzar hilos (máximo 10 perfiles a la vez por seguridad)
    max_workers = 10
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
