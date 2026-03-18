import os
import shutil
import subprocess

# Lista de computadoras a generar
COMPUTERS = [
    {"id": "chihuahua_1", "name": "Chihuahua_1"},
    {"id": "chihuahua_2", "name": "Chihuahua_2"},
    {"id": "chihuahua_3", "name": "Chihuahua_3"},
    {"id": "sinaloa_1", "name": "Sinaloa_1"},
    {"id": "sinaloa_2", "name": "Sinaloa_2"},
    {"id": "quintanaroo_1", "name": "Quintana_Roo_1"},
    {"id": "quintanaroo_2", "name": "Quintana_Roo_2"},
    {"id": "torreon_1", "name": "Torreon_1"},
    {"id": "torreon_2", "name": "Torreon_2"},
    {"id": "tijuana_1", "name": "Tijuana_1"},
]

BASE_DIR = os.getcwd()
DIST_DIR = os.path.join(BASE_DIR, "dist")
MASTER_BUILD = os.path.join(DIST_DIR, "VIEWS")
OUTPUT_DIR = os.path.join(DIST_DIR, "BUILD_VERSIONS")

def main():
    # 1. Asegurarse de que el build maestro existe
    if not os.path.exists(MASTER_BUILD):
        print("🚀 Generando build maestro 'VIEWS'...")
        subprocess.run([r"..\.venv\Scripts\python.exe", "-m", "PyInstaller", "--noconfirm", "ReaccionesManager.spec"], check=True)
    
    # 2. Crear carpeta de salida
    if os.path.exists(OUTPUT_DIR):
        print(f"🧹 Limpiando carpeta de salida {OUTPUT_DIR}...")
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    # 3. Generar versiones para cada PC
    for comp in COMPUTERS:
        target_path = os.path.join(OUTPUT_DIR, comp["name"])
        print(f"📦 Generando versión para: {comp['name']}...")
        
        # Copiar build maestro
        shutil.copytree(MASTER_BUILD, target_path)
        
        # Modificar .env (PyInstaller lo pone en _internal)
        env_path = os.path.join(target_path, "_internal", ".env")
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            with open(env_path, 'w', encoding='utf-8') as f:
                found = False
                for line in lines:
                    if line.startswith("MY_COMPUTER_ID="):
                        f.write(f"MY_COMPUTER_ID={comp['id']}\n")
                        found = True
                    else:
                        f.write(line)
                if not found:
                    f.write(f"\nMY_COMPUTER_ID={comp['id']}\n")
        
        print(f"✅ {comp['name']} completado.")

    print("\n✨ ¡PROCESO FINALIZADO! Todas las versiones están en: dist/BUILD_VERSIONS")

if __name__ == "__main__":
    main()
