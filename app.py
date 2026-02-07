from flask import Flask, render_template, request, jsonify
import json
import threading
import time
import automation
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Ya no usamos profiles.json, todo se maneja dinámicamente con AdsPower

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/groups')
def get_groups():
    groups = automation.get_ads_groups()
    return jsonify(groups)

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
    
    # Nuevo: Pasamos la configuración del rango al hilo si existe
    thread = threading.Thread(target=run_batch, args=(assignments, url, duration_mins, counts, group_id, end_group_id))
    thread.start()
    
    msg = f"Campaña iniciada para {total_needed} perfiles."
    if group_id:
        msg = f"Iniciando extracción y campaña para el rango de grupos..."
        

    msg = f"Iniciando extracción y campaña para el rango de grupos..."

    return jsonify({"status": "started", "message": msg})

from concurrent.futures import ThreadPoolExecutor

def run_batch(assignments, url, duration_mins=1, counts=None, group_id=None, end_group_id=None):
    print(f"🚀 Iniciando campaña simultánea para {url} (Vistas: {duration_mins} min)")

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

        # Perfiles usados para la campaña inicial
        selected_ids = range_profiles[:total_needed]
        # Perfiles de reserva para sustitución
        reserve_pool = range_profiles[total_needed:]
        reserve_lock = threading.Lock()

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
        
        # v6: Arranque escalonado
        delay = index * 8 
        print(f"⏳ Perfil {pid} esperando {delay}s para arrancar...")
        time.sleep(delay)
        
        while pid: # Loop para permitir sustitución
            print(f"🟢 Perfil {pid} iniciando...")
            
            # Iniciar navegador
            data = automation.start_browser(pid)
            if not data:
                print(f"❌ Error iniciando {pid}")
                # Intentar sustituir si el inicio falla por AdsPower
                pid = None
                with reserve_lock:
                    if reserve_pool:
                        pid = reserve_pool.pop(0)
                        print(f"♻️ Sustituyendo por error de inicio. Nuevo perfil: {pid}")
                        continue
                return
                
            status = "error"
            try:
                if reaction == "Solo Views":
                    status = automation.watch_live_video(
                        data["webdriver"],
                        data["ws"]["selenium"],
                        url,
                        duration_seconds=int(duration_mins * 60)
                    )
                else:
                    status = automation.react_to_post(
                        data["webdriver"],
                        data["ws"]["selenium"],
                        url,
                        target_reaction=reaction
                    )
            except Exception as e:
                print(f"❌ Error en automatización ({pid}): {e}")
                status = "error"
                
            automation.close_browser(pid)

            if status == "success":
                with summary_lock:
                    summary[reaction] = summary.get(reaction, 0) + 1
                break # Éxito, salir del loop de sustitución
            
            elif status == "account_error":
                print(f"🔴 Perfil {pid} inhabilitado o deslogueado.")
                pid = None
                with reserve_lock:
                    if reserve_pool:
                        pid = reserve_pool.pop(0)
                        print(f"♻️ Sustituyendo perfil... Nuevo perfil: {pid}")
                        # No hay delay extra aquí para no retrasar la campaña, 
                        # pero ya pasó el delay inicial del hilo
                        continue
                break # Si no hay más reserva, terminar
            else:
                # Error general (no de cuenta), mejor no reintentar para no gastar reserva en errores de red/selectores
                break

    # Lanzar hilos
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
    # v7: Desactivamos debug y reloader para evitar WinError 10038 al manejar muchos hilos y procesos
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)
