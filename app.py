from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import os
import sys
import json
import threading
import time
import re
from functools import wraps
from dotenv import load_dotenv

# --- CARGA DE CONFIGURACIÓN INICIAL (DEBE SER ANTES DE OTROS IMPORTS) ---
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    load_dotenv(os.path.join(exe_dir, '.env'))
else:
    load_dotenv()

import automation  # Ahora automation cargará las variables correctas del .env
from logger_shared import log_to_web, get_logs

app = Flask(__name__)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    template_folder = os.path.join(application_path, 'templates')
    static_folder = os.path.join(application_path, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key-123')

AUTH_USERNAME = os.getenv('APP_USERNAME') or os.getenv('LOGIN_USER') or 'Maxtres'
AUTH_PASSWORD = os.getenv('APP_PASSWORD') or os.getenv('LOGIN_PASSWORD') or 'M4xTr3s2025'


def normalize_computer_id(value):
    if not value:
        return ''
    return re.sub(r'[^a-z0-9_]', '', value.strip().lower().replace('-', '_').replace(' ', '_'))


def detect_computer_id():
    explicit = (
        os.getenv('CURRENT_COMPUTER')
        or os.getenv('CURRENT_COMPUTER_ID')
        or os.getenv('MY_COMPUTER_ID')
    )
    if explicit:
        return normalize_computer_id(explicit)

    host = os.getenv('COMPUTERNAME') or os.getenv('HOSTNAME') or 'local'
    return normalize_computer_id(host)


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if session.get('logged_in'):
            return view_func(*args, **kwargs)

        if request.path.startswith('/api/') or request.path == '/start_campaign':
            return jsonify({"status": "error", "message": "No autorizado. Inicia sesión."}), 401

        return redirect(url_for('login'))

    return wrapped_view


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''

        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))

        return render_template('login.html', error='Usuario o contraseña incorrectos.')

    if session.get('logged_in'):
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/debug_logs')
@login_required
def get_debug_logs():
    return jsonify(get_logs())

COMPUTER_NAME = detect_computer_id() or 'local'

@app.route('/')
@login_required
def index():
    return render_template('index.html', computer_name=COMPUTER_NAME)

@app.route('/api/groups')
@login_required
def get_groups():
    """Lee los grupos directamente de AdsPower local"""
    try:
        log_to_web("📡 Cargando grupos de AdsPower local...", "info")
        groups = automation.get_ads_groups()
        log_to_web(f"✅ {len(groups)} grupos cargados", "success")
        return jsonify(groups)
    except Exception as e:
        log_to_web(f"❌ Error cargando grupos: {str(e)}", "error")
        return jsonify({"error": str(e)}), 500

@app.route('/start_campaign', methods=['POST'])
@login_required
def start_campaign():
    """Inicia la campaña localmente en esta máquina"""
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
             return jsonify({"status": "error", "message": f"El grupo ID {group_id} no existe en AdsPower."}), 400
             
        profiles = automation.get_ads_profiles(group_id)
        if not profiles:
             return jsonify({"status": "error", "message": f"El grupo '{target_group.get('group_name')}' está vacío en AdsPower."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error conectando con AdsPower: {str(e)}"}), 500

    log_to_web(f"🚀 Iniciando campaña local con {len(profiles)} perfiles", "info")
    assignments = []
    thread = threading.Thread(target=run_batch, args=(assignments, url, duration_mins, group_id, end_group_id))
    thread.start()
    
    return jsonify({"status": "started", "message": f"Campaña iniciada. Procesando {len(profiles)} perfiles..."})

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
