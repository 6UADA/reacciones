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
            
    # 3. Lanzar hilo en background
    thread = threading.Thread(target=run_batch, args=(assignments, url))
    thread.start()
    
    return jsonify({"status": "started", "message": f"Campaña iniciada con {total_needed} perfiles."})

def run_batch(assignments, url):
    print(f"🚀 Iniciando campaña batch para {url}")
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
        try:
            automation.react_to_post(
                data["webdriver"],
                data["ws"]["selenium"],
                url,
                target_reaction=reaction
            )
        except Exception as e:
            print(f"Error in automation: {e}")
            
        # Cerrar
        automation.close_browser(pid)
        time.sleep(random.uniform(2, 5)) # Pausa entre perfiles para no saturar

if __name__ == '__main__':
    app.run(debug=True, port=5000)
