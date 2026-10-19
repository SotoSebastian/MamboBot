# MamboBot — Informe de compatibilidad con Linux

## 1. Resumen ejecutivo

MamboBot se ejecutó correctamente en Ubuntu 26.04.1 LTS utilizando Python 3.12.10 en un entorno virtual independiente.

Se verificaron los componentes principales de reproducción musical y reconocimiento de comandos de voz. Durante la configuración se identificaron incompatibilidades de Python, problemas de conexión de voz con Discord y dificultades al extraer audio desde YouTube.

Tras aplicar los ajustes descritos en este documento, el bot logró conectarse a un canal de voz, reconocer un comando hablado y continuar el flujo de búsqueda musical.

## 2. Entorno de ejecución

| Componente | Configuración |
|---|---|
| Sistema operativo | Ubuntu 26.04.1 LTS |
| Python del proyecto | 3.12.10 |
| Gestión de versiones | pyenv |
| Entorno virtual | `.venv312/` |
| Biblioteca de Discord | `discord.py` con soporte de voz |
| Recepción de voz | `discord-ext-voice-recv` |
| Reproducción de audio | FFmpeg |
| Búsqueda y extracción de audio | yt-dlp |
| Runtime JavaScript | Deno |
| Reconocimiento de voz | SpeechRecognition |

## 3. Problemas encontrados y soluciones

### 3.1. Incompatibilidad de Python con SpeechRecognition

**Problema:** la versión de Python del sistema era demasiado reciente y la dependencia de reconocimiento de voz intentaba importar `aifc`, un módulo eliminado en Python 3.13.

**Solución:** instalar Python 3.12.10 mediante pyenv y crear el entorno virtual `.venv312/`.

Esta separación permite ejecutar MamboBot con una versión compatible sin reemplazar el Python del sistema operativo.

### 3.2. Errores de conexión y decodificación de voz de Discord

**Problemas observados:**
- Cierre de WebSocket con código `4017`.
- Errores de decodificación de paquetes de voz.
- Errores de Opus relacionados con flujos de audio corruptos.

**Solución aplicada:** instalar una versión experimental de `discord-ext-voice-recv` desde la rama de la solicitud de cambios PR #65, que incorpora soporte de decodificación DAVE.

La versión utilizada fue `0.5.4a182`.

**Advertencia:** esta versión procede de una solicitud de cambios y no debe considerarse una solución estable garantizada. Para reproducir el entorno, conviene fijar el commit exacto utilizado y volver a comprobar la compatibilidad después de actualizar las dependencias.

### 3.3. FFmpeg no encontrado

**Problema:** el bot devolvió un error indicando que no encontraba FFmpeg.

**Solución:** instalar FFmpeg desde los repositorios de Ubuntu y comprobar que el ejecutable esté disponible en el sistema.

La disponibilidad de FFmpeg resuelve la ausencia del ejecutable, pero no garantiza que todas las fuentes de audio puedan descargarse.

### 3.4. Error HTTP 403 al obtener audio de YouTube

**Problema:** yt-dlp encontró dificultades al extraer audio de YouTube, incluyendo avisos sobre la ausencia de un runtime JavaScript y respuestas HTTP `403 Forbidden`.

**Solución aplicada:** instalar Deno, incorporarlo al `PATH` de la sesión y actualizar yt-dlp con sus dependencias opcionales.

Después de estos cambios, el usuario confirmó que la reproducción volvió a funcionar correctamente.

## 4. Comprobaciones de compatibilidad

Durante las pruebas se observaron los siguientes resultados:

- El bot inició y se conectó a Discord.
- El bot pudo entrar a un canal de voz.
- El sistema recibió audio del canal y ejecutó el reconocimiento de voz.
- Se reconoció el comando hablado: «Mambo Reproduce Something About Us de Daft Punk».
- El flujo llegó al manejador de reproducción y a la búsqueda en YouTube.
- Tras los ajustes de yt-dlp y Deno, el usuario confirmó que la reproducción funcionaba correctamente.

Estos resultados corresponden a las pruebas realizadas durante la configuración; no constituyen una garantía de funcionamiento ante futuras actualizaciones de Discord, YouTube o las dependencias.

## 5. Arranque habitual

Desde la terminal, en el directorio del proyecto:

```bash
cd ~/Documentos/botdiscord/MamboBot
source .venv312/bin/activate
export PATH="$HOME/.deno/bin:$PATH"
python mambobot.py
```

Si Deno ya está incluido en el `PATH` de la sesión, la exportación puede no ser necesaria.

## 6. Conclusión

MamboBot consiguió ejecutarse en Ubuntu con un entorno Python separado y con sus funciones de recepción de voz, reconocimiento de comandos y reproducción musical operativas durante las pruebas.

Los puntos más delicados para mantener la compatibilidad son el soporte DAVE de la extensión de voz, la versión de Python requerida por las dependencias y los cambios que YouTube pueda introducir en la extracción de audio.

