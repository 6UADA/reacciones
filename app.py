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
    thread = threading.Thread(target=run_batch, args=(assignments, url))
    thread.start()
    
    return jsonify({"status": "started", "message": f"Campaña iniciada con {total_needed} perfiles (orden aleatorio)."})

def run_batch(assignments, url):
    print(f"🚀 Iniciando campaña batch para {url}")
    
    summary = {} # Contador de éxitos
    
    for task in assignments:
        pid = task['profile_id']
        reaction = task['reaction']
        print(f"Processing Profile {pid} -> {reaction}")
        
        # Iniciar navegador
        data = automation.start_browser(pid)
        if not data:
            print(f"Failed to start {pid}")
            continue
            
        # Reaccionar
        is_success = False
        try:
            is_success = automation.react_to_post(
                data["webdriver"],
                data["ws"]["selenium"],
                url,
                target_reaction=reaction
            )
        except Exception as e:
            print(f"Error in automation: {e}")
            
        # Actualizar resumen si fue exitoso
        if is_success:
            summary[reaction] = summary.get(reaction, 0) + 1
            
        # Cerrar
        automation.close_browser(pid)
        time.sleep(random.uniform(2, 5)) # Pausa entre perfiles
        
    # --- REPORTE FINAL ---
    print("\n" + "="*30)
    print("📢 REPORTE FINAL DE CAMPAÑA")
    print(f"🔗 URL: {url}")
    print("Resultados:")
    if not summary:
        print("❌ Ninguna reacción exitosa.")
    else:
        # Formato: "Me encanta: 5, Me asombra: 2"
        parts = [f"{k}: {v}" for k, v in summary.items()]
        print(", ".join(parts))
    print("="*30 + "\n")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
