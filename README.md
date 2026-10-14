# MamboBot
Bot de música para Discord basado en [VenusBot](https://github.com/VenusMods/VenusBot), con modificaciones y mejoras propias enfocadas en la reproducción musical, la gestión de colas, los comandos por voz y las recomendaciones.

## Características

- Reproducción de música en canales de voz de Discord mediante comandos de voz.
- Gestión de la cola de reproducción.
- Controles para pausar, reanudar, saltar, detener canciones y reiniciar cola/historial.
- Modo de repetición y reproducción aleatoria de la cola.
- Integración con Spotify para obtener información de canciones para posteriormente reproducirlas en youtube.
- Uso de YouTube como fuente de audio.
- Sistema de recomendaciones musicales.
  
## Modificaciones y mejoras

MamboBot parte del código original de VenusBot y evoluciona mediante modificaciones propias.

Entre las áreas trabajadas se encuentran:

- Mejoras en el sistema de recomendaciones musicales.
- Ajustes en la selección de canciones para reducir resultados irrelevantes.
- Gestión de la reproducción y las colas de canciones.
- Integración y ajustes de comandos controlados por voz.


Esta sección se actualizará conforme se incorporen y validen nuevas mejoras.
## Tecnologías

- Python
- discord.py
- discord-ext-voice-recv
- SpeechRecognition
- FFmpeg
- yt-dlp
- Spotify API
- 
## Tecnologías y dependencias

- **discord.py:** integración con la API de Discord.
- **discord-ext-voice_recv:** recepción de audio desde canales de voz.
- **davey:** soporte relacionado con el protocolo de voz DAVE.
- **FFmpeg:** procesamiento y reproducción de audio.
- **yt-dlp:** extracción de información y enlaces de audio desde YouTube.
- **SpeechRecognition:** reconocimiento de comandos por voz.
## Requisitos

- Python compatible con las dependencias del proyecto.
- FFmpeg instalado y accesible desde el sistema.
- Un bot de Discord creado en el [Discord Developer Portal](https://discord.com/developers/applications).
- Credenciales de API configuradas cuando corresponda.

## Instalación

1. Clona el repositorio:

   ```bash
   git clone https://github.com/SotoSebastian/MamboBot.git
   cd MamboBot
   ```

2. Crea un entorno virtual:

   ```bash
   python -m venv .venv
   ```

3. Activa el entorno virtual en Windows con Git Bash:

   ```bash
   source .venv/Scripts/activate
   ```

4. Instala las dependencias indicadas por el proyecto:

   ```bash
   python -m pip install -r requirements.txt
   ```

5. Configura las variables de entorno necesarias en un archivo `.env`, siguiendo los nombres que utiliza el código.
  DISCORD_TOKEN='########################' (Token del bot de Discord - Discord Developer)
  SPOTIFY_CLIENT_ID='#########' (usuario)
  SPOTIFY_CLIENT_SECRET='*********' (password)
  SPOTIFY_CLIENT_REFRESH_TOKEN='#################' (Token desde Spotify Developer)
  OWNER= ############ (ID usuario Discord - Discord Developer Mode Activate)

6. Ejecuta el bot:

   ```bash
   python venusbot.py
   ```

## Configuración y seguridad

No publiques tokens de Discord, claves de API, archivos `.env` ni cookies privadas. Configura las credenciales localmente antes de ejecutar el bot.

## Créditos y proyecto base

MamboBot es una versión modificada de [VenusBot](https://github.com/VenusMods/VenusBot).

Este proyecto parte del código original de VenusBot e incorpora modificaciones y funcionalidades desarrolladas durante su evolución, incluyendo mejoras en la reproducción musical, la gestión de colas, el control por voz y las recomendaciones.

Se reconoce a los autores del proyecto original y se mantienen los avisos de licencia correspondientes.

## Licencia

Este proyecto se basa en VenusBot, publicado bajo la licencia MIT. Consulta el archivo `LICENSE` para revisar los términos y los avisos de copyright aplicables.
