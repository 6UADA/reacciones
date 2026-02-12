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

## Acceso Remoto (Cloudflare)

Para usar este panel desde otras PC o dispositivos sin abrir puertos:

1.  **Descarga Cloudflared**: Instala el ejecutable de [Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
2.  **Inicia el Túnel**: En una terminal, ejecuta:
    ```bash
    cloudflared tunnel --url http://localhost:5000
    ```
3.  **Usa la URL**: Copia la URL generada (ej: `https://something-random.trycloudflare.com`) y compártela.

## Seguridad (Login)

El sistema ahora está protegido por una pantalla de inicio de sesión.

- **Usuario**: `Maxtres`
- **Contraseña**: `M4xTr3s2025`

Puedes cambiar estas credenciales en el archivo `.env`.

## Inicio Automático con Windows

Si quieres que el sistema se inicie solo al prender la PC:

1.  Presiona `Win + R`, escribe `shell:startup` y dale a Enter.
2.  Crea un **acceso directo** del archivo `iniciar_sistema.bat` dentro de esa carpeta.
3.  ¡Listo! La próxima vez que inicies Windows, se abrirán las dos ventanas (servidor y túnel) automáticamente.

## Estructura

- `app.py`: Servidor web Flask con protección de rutas.
- `automation.py`: Lógica de automatización con Selenium y AdsPower.
- `templates/login.html`: Pantalla de inicio de sesión.
- `templates/index.html`: Panel principal de control.

