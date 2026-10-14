# MamboBot

MamboBot es un bot de música para Discord basado en [VenusBot](https://github.com/VenusMods/VenusBot), con modificaciones propias orientadas a la reproducción musical, la gestión de colas, los comandos por voz y las recomendaciones.

## Características

- Reproducción de música en canales de voz de Discord.
- Gestión de la cola de reproducción.
- Controles para pausar, reanudar, saltar y detener canciones.
- Funciones para reiniciar la cola y el historial.
- Modo de repetición y reproducción aleatoria de la cola.
- Integración con Spotify para obtener metadatos de canciones y listas de reproducción.
- Búsqueda y reproducción de audio mediante YouTube.
- Reconocimiento de comandos por voz.
- Sistema de recomendaciones musicales.

## Modificaciones y mejoras

MamboBot parte del código original de VenusBot y evoluciona mediante modificaciones propias.

Las áreas de trabajo incluyen:

- Mejoras en el sistema de recomendaciones musicales.
- Ajustes en la selección de canciones para reducir resultados irrelevantes.
- Mejoras en la gestión de la reproducción y las colas.
- Integración y ajustes de comandos controlados por voz.

Esta sección se actualizará conforme se incorporen y validen nuevas mejoras.

## Tecnologías y dependencias

- **Python:** lenguaje principal del proyecto.
- **discord.py:** integración con la API de Discord.
- **discord-ext-voice_recv:** recepción de audio desde canales de voz.
- **davey:** dependencia relacionada con el protocolo de voz DAVE.
- **SpeechRecognition:** reconocimiento de comandos por voz.
- **FFmpeg:** procesamiento de audio.
- **yt-dlp:** extracción de información y enlaces de audio desde YouTube.
- **Spotify API:** obtención de metadatos de canciones y listas de reproducción.

## Requisitos

- Python 3.12, utilizado en el entorno de desarrollo actual.
- FFmpeg instalado y accesible desde la terminal.
- Una aplicación de bot configurada en el [Discord Developer Portal](https://discord.com/developers/applications).
- Credenciales de Spotify Developer, si son necesarias para las funciones de Spotify.
- Las dependencias Python indicadas en `requirements.txt`, si este archivo está disponible en el repositorio.

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/SotoSebastian/MamboBot.git
cd MamboBot
```

### 2. Crear el entorno virtual

```bash
python -m venv .venv
```

### 3. Instalar las dependencias

En Windows, desde Git Bash:

```bash
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### 4. Configurar las variables de entorno

Crea un archivo `.env` en la raíz del proyecto y añade las variables que utiliza el código.

Ejemplo de formato:

```dotenv
DISCORD_TOKEN=tu_token_de_discord
SPOTIFY_CLIENT_ID=tu_client_id
SPOTIFY_CLIENT_SECRET=tu_client_secret
SPOTIFY_CLIENT_REFRESH_TOKEN=tu_refresh_token
OWNER=tu_id_de_usuario_de_discord
```

Los nombres deben coincidir exactamente con los que lee el código. No compartas valores reales de estas credenciales.

### 5. Ejecutar el bot

```bash
./.venv/Scripts/python.exe venusbot.py
```

## Configuración y seguridad

- No publiques tokens de Discord ni credenciales de Spotify.
- Mantén el archivo `.env` fuera del control de versiones mediante `.gitignore`.
- No publiques archivos de cookies, registros privados ni otros archivos sensibles.
- Instala FFmpeg por separado y verifica que esté disponible desde la terminal.

## Metodología de desarrollo

El desarrollo de MamboBot incorpora un enfoque iterativo, con apoyo de herramientas de inteligencia artificial para tareas de programación, depuración y mejora de funcionalidades.

Los cambios se prueban y ajustan conforme se identifican problemas y necesidades del proyecto.

## Créditos y proyecto base

MamboBot es una versión modificada de [VenusBot](https://github.com/VenusMods/VenusBot).

Se reconoce el proyecto original y a sus autores. Las modificaciones añadidas a esta versión se documentan como parte de la evolución de MamboBot.

## Licencia

Consulta el archivo `LICENSE` del repositorio para conocer las condiciones de uso y distribución del código original y los avisos de copyright aplicables.
