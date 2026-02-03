# Proyecto de Reacciones Facebook

Este proyecto automatiza reacciones en Facebook utilizando perfiles de AdsPower.

## Instalación

1.  Clona el repositorio o descarga la carpeta.
2.  Crea un entorno virtual (opcional pero recomendado):
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```
3.  Instala las dependencias:
    ```bash
    pip install -r requirements.txt
    ```
4.  Configura tus variables de entorno:
    - Crea un archivo `.env` basado en el ejemplo (o usa el que se generó).
    - Asegúrate de tener `ADSPOWER_API_URL` y `API_KEY`.

## Uso

1.  Ejecuta la aplicación:
    ```bash
    python app.py
    ```
2.  Abre tu navegador en `http://localhost:5000`.
3.  Ingresa la URL del post y la cantidad de reacciones deseadas.

## Estructura

- `app.py`: Servidor web Flask.
- `automation.py`: Lógica de automatización con Selenium y AdsPower.
- `profiles.json`: Base de datos local de perfiles.
