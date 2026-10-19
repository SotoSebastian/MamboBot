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
./.venv/Scripts/python.exe mambobot.py
```

## Configuración y seguridad

- No publiques tokens de Discord ni credenciales de Spotify.
- Mantén el archivo `.env` fuera del control de versiones mediante `.gitignore`.
- No publiques archivos de cookies, registros privados ni otros archivos sensibles.
- Instala FFmpeg por separado y verifica que esté disponible desde la terminal.

## Comandos de MamboBot

MamboBot permite controlar la reproducción musical mediante comandos de Discord y, para algunas funciones, mediante comandos de voz.

### Comandos de música

#### `/247`
Conecta el bot al canal de voz del usuario y activa el modo 24/7, si esta función continúa habilitada en MamboBot.

#### `/dc`
Desconecta el bot del canal de voz y desactiva el modo 24/7, si está disponible.

#### `/play`
Busca y reproduce una canción o lista de reproducción. Puede recibir una búsqueda de texto o un enlace compatible.

**Fuentes compatibles:**
- YouTube: búsqueda, canciones y listas de reproducción.
- Spotify: obtiene los metadatos y busca el audio correspondiente en YouTube.
- SoundCloud: canciones y listas de reproducción.

**Ejemplos:**

```text
/play Never Gonna Give You Up
/play https://www.youtube.com/watch?v=VIDEO_ID
/play https://open.spotify.com/track/TRACK_ID
```

#### `/playfile`
Reproduce un archivo de audio adjunto al mensaje o proporcionado mediante el comando.

#### `/pause`
Pausa la canción actual. Si la reproducción ya está pausada, reanuda la canción.

#### `/resume`
Reanuda la reproducción desde el punto en el que se pausó.

#### `/skip`
Salta la canción actual. Si está activado el sistema de votación por mayoría, el salto depende del resultado de la votación.

#### `/stop`
Detiene la reproducción actual y limpia la cola de canciones. Si está activado el sistema de votación, puede requerir la aprobación de los usuarios del canal.

#### `/loop`
Activa o desactiva la repetición de la canción actual.

#### `/shuffle`
Mezcla las canciones pendientes de la cola sin cambiar la canción que se está reproduciendo.

#### `/time`
Muestra el tiempo transcurrido de la canción actual y, cuando se conoce, su duración total.

#### `/queue`
Muestra la cola de reproducción y permite administrar las canciones mediante los controles disponibles en la interfaz.

#### `/search`
Busca canciones y presenta resultados para ayudar a seleccionar la que se desea reproducir.

### Comandos de voz

MamboBot puede reconocer comandos hablados por los usuarios presentes en un canal de voz. La palabra de activación predeterminada es `mambo`, siempre que no se haya cambiado en la configuración.

**Ejemplos de comandos hablados:**

```text
mambo play [nombre de la canción]
mambo pause
mambo skip
mambo next
mambo loop
mambo stop
mambo reset
mambo recommend
```

También se han añadido alias en español:

- **Reproducción:** `reproduce`, `pon`, `toca`.
- **Pausa:** `pausa`, `pausar`.
- **Siguiente canción:** `siguiente`, `salta`, `saltar`.
- **Repetición:** `repite`, `repetir`.
- **Detener / Reiniciar:** `para`, `detener`, `detén`.
- **Recomendar:** `recomienda`, `recomendar`, `recomendaciones`.

Los comandos hablados requieren que el bot esté conectado al canal de voz y que la transcripción reconozca la frase correctamente.

### Transcripción de voz

#### `/transcribe`
Activa la transcripción de las voces detectadas en un canal de texto seleccionado. Si no se especifica un canal, puede utilizarse para desactivar la transcripción.

### Contadores de palabras

#### `/counters`
Permite consultar y administrar los contadores de palabras y sus palabras clave.

- **Contadores:** estadísticas que registran las menciones detectadas.
- **Palabras clave:** palabras o expresiones que incrementan un contador.
- **Asociaciones:** varias palabras clave pueden contribuir al mismo contador.

#### Contadores activados por voz
Cuando se reconoce una palabra clave en una transcripción, MamboBot incrementa el contador asociado y puede publicar el resultado actualizado en el canal de texto configurado.

### Administración

Los siguientes comandos aparecen en el README original de VenusBot, pero todavía deben verificarse en MamboBot:

- `/ban`: restringe el uso del bot a un usuario.
- `/unban`: elimina la restricción de un usuario.
- `/majorvote`: activa o desactiva la votación por mayoría para saltar o detener canciones.
- `/restart`: reinicia el bot.
- `/addadmin`: otorga permisos administrativos a un usuario.
- `/removeadmin`: retira permisos administrativos a un usuario.



## Metodología de desarrollo

El desarrollo de MamboBot incorpora un enfoque iterativo, con apoyo de herramientas de inteligencia artificial para tareas de programación, depuración y mejora de funcionalidades.

Los cambios se prueban y ajustan conforme se identifican problemas y necesidades del proyecto.

## Créditos y proyecto base

MamboBot es una versión modificada de [VenusBot](https://github.com/VenusMods/VenusBot).

Se reconoce el proyecto original y a sus autores. Las modificaciones añadidas a esta versión se documentan como parte de la evolución de MamboBot.

## Licencia

Consulta el archivo `LICENSE` del repositorio para conocer las condiciones de uso y distribución del código original y los avisos de copyright aplicables.


## Problemas de compatibilidad
Se creó un archivo dentro del repositorio COMPATIBILIDAD_LINUX con información sobre los errores y soluciones que pueden surgir con LINUX
