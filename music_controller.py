import discord
import re
import asyncio
import sys
import time
import random
import logging
import audioop
import speech_recognition as sr
from itertools import chain
from typing import Optional, Tuple
from discord.ext import voice_recv
from discord.ext.voice_recv.extras import speechrecognition as vr_sr
from management.banned_users import BannedUsers
from management.word_counter import WordCounter
from management.bot_keywords import BotKeywords
from scripts.ytDLP import VideoSearcher, getSongExpiration
from embed_views.music_buttons import MusicButtons
from scripts.spotify import SpotifyController


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

EMBED_COLOR = 0xA600FF

# Máximo de canciones recordadas por lista de historial (evita crecer sin límite en sesiones 24/7).
MAX_SESSION_HISTORY = 50

# Segundos de margen antes de considerar caducado un enlace de audio.
LINK_EXPIRY_MARGIN = 60

# ~0.3 s a 48 kHz mono 16-bit. Audios más cortos se ignoran.
MIN_AUDIO_BYTES = 28800

# Poner en True solo para depurar el reconocimiento de voz (escribe un .wav por cada audio).
DEBUG_SAVE_AUDIO = False

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -filter:a volume=0.7",
}

VOTE_EMOJIS = ("✅", "❌")

# Comando interno -> método que lo atiende.
VOICE_COMMANDS = {
    "play": "handle_play_keyword",
    "pause": "handle_pause_keyword",
    "skip": "handle_skip_keyword",
    "next": "handle_skip_keyword",
    "loop": "handle_loop_keyword",
    "stop": "handle_stop_keyword",
    "recommend": "handle_recommend_keyword",
}

# Sinónimos en español -> comando interno.
VOICE_ALIASES = {
    "reproduce": "play", "toca": "play", "pon": "play", "pone": "play",
    "pausa": "pause", "pausar": "pause",
    "siguiente": "skip", "salta": "skip", "saltar": "skip",
    "repite": "loop", "repetir": "loop",
    "para": "stop", "detener": "stop", "detén": "stop", "reset": "stop", "reinicia": "stop",
    "recomienda": "recommend","recomendar": "recommend","recomendaciones": "recommend",
}

# Patrones para detectar el origen de una canción (compilados una sola vez).
YOUTUBE_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/")
YOUTUBE_PLAYLIST_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/playlist\?list=[\w-]+")
SPOTIFY_RE = re.compile(r"(https?://)?(open\.)?spotify\.com/")
SPOTIFY_PLAYLIST_RE = re.compile(r"(https?://)?(open\.)?spotify\.com/(playlist|album)/[a-zA-Z0-9]+")
SOUNDCLOUD_RE = re.compile(r"(https?://)?(www\.)?soundcloud\.com/")
SOUNDCLOUD_PLAYLIST_RE = re.compile(r"^(https?://)?(www\.)?soundcloud\.com/[^/]+/sets/[^/]+/?")

# Algoritmo para modificar como se lee el audio que se recibe de un canal de voz.
def _patched_read(self, size: int) -> bytes:
    need = size * self.SAMPLE_WIDTH * self.CHANNELS
    for _ in range(10):
        if len(self.buffer) < need:
            time.sleep(0.1)
        else:
            break
    else:
        if len(self.buffer) == 0:
            return b''

    chunk = self.buffer[:need].tobytes()
    chunk = chunk[: len(chunk) - (len(chunk) % 4)]
    del self.buffer[: len(chunk)]
    return audioop.tomono(chunk, 2, 0.5, 0.5)

vr_sr.DiscordSRAudioSource.read = _patched_read

# Definición de clases con sus atributos, MusicController además tiene funciones propias.

class Song:
    def __init__(
        self,
        title: str,
        url: str,
        link: str,
        thumbnail: str,
        duration: int,
        user: discord.User,
        isFile: bool,
        artist: str | None = None,
    ):
        self.title = title
        self.url = url
        self.link = link
        self.thumbnail = thumbnail
        self.duration = duration
        self.user = user
        self.isFile = isFile
        self.artist = artist


class MusicController:
    # Constructor
    def __init__(self, client: discord.Client, guild: discord.Guild):
        logging.info(f"Created Music Controller for: {guild}")
        self.client = client
        self.guild = guild
        self.spotify = SpotifyController()
        self.voiceChannel = None
        self.textChannel = None
        self.transcriptionChannel = None
        self.songQueue = []
        # Cola de recomendación cuando no quedan canciones en la cola principal.
        self.recommendationQueue = []
        self.currentSong = None
        self.currentSongIsRecommendation = False
        # Historial temporal de la sesión musical
        self.sessionRequestedSongs = []
        self.sessionRecommendedSongs = []
        self.sessionRecentSongs = []
        self.isLooping = False
        self.isMajorityVote = False
        # Temporizador de la canción actual
        self.start_time = None
        self.pause_start = None
        self.pause_duration = 0
        self.player_message = None
        # Estado interno
        self._presence_title = None
        self._background_tasks = set()

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------
    def _getNextQueuedSong(self) -> Optional[Song]:
        """Prioriza solicitudes explícitas sobre recomendaciones."""
        if self.songQueue:
            return self.songQueue[0]

        if self.recommendationQueue:
            return self.recommendationQueue[0]

        return None
    
    def _getVoiceClient(self):
        """Devuelve el cliente de voz si está conectado; si no, None."""
        voice_client = self.guild.voice_client
        if voice_client is not None and voice_client.is_connected():
            return voice_client
        return None

    def _resetTimer(self):
        self.start_time = None
        self.pause_start = None
        self.pause_duration = 0

    def _applyResume(self):
        """Suma el tiempo que estuvo pausada la canción."""
        if self.pause_start is not None:
            self.pause_duration += int(time.time()) - self.pause_start
            self.pause_start = None

    def getElapsedSeconds(self) -> int:
        """Segundos reproducidos de la canción actual, sin contar las pausas."""
        if self.start_time is None:
            return 0

        reference = self.pause_start if self.pause_start is not None else time.time()
        return max(0, int(reference - self.start_time - self.pause_duration))

    def _formatDuration(self, seconds) -> str:
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)

        if hours:
            return f"{hours:02}:{minutes:02}:{secs:02}"

        return f"{minutes:02}:{secs:02}"

    def _spawn(self, coro):
        """Lanza una tarea en segundo plano sin bloquear el flujo actual."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._onBackgroundDone)
        return task

    def _onBackgroundDone(self, task):
        self._background_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logging.error("Error en tarea en segundo plano: %r", task.exception())

    @staticmethod
    def _logFutureError(future):
        try:
            future.result()
        except Exception:
            logging.exception("Error gestionando el fin de la reproducción.")

    async def _setPresence(self, title: Optional[str]):
        """Actualiza la presencia del bot solo si cambió."""
        if title == self._presence_title:
            return

        self._presence_title = title
        activity = None

        if title:
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name=title
            )

        try:
            await self.client.change_presence(activity=activity)
        except Exception:
            logging.exception("No se pudo actualizar la presencia del bot.")

    @staticmethod
    def _songFromResult(
        result: dict,
        user,
        fallback_url: Optional[str] = None
    ) -> Song:
        """Crea un Song a partir de un resultado de VideoSearcher."""
        return Song(
            title=result.get("title") or "Sin título",
            url=result.get("url") or fallback_url,
            link=result.get("link"),
            thumbnail=result.get("thumbnail"),
            duration=int(result.get("duration") or 0),
            user=user,
            isFile=False,
            artist=result.get("artist"),
        )


    def _resetSession(self):
        self.songQueue.clear()
        self.resetSongHistory()
        self.isLooping = False
        self._resetTimer()
        self.markPlayerFinished()

    # ------------------------------------------------------------------
    # Reproductor: texto de duración y mensaje
    # ------------------------------------------------------------------

    def buildDurationValue(self, song: Song) -> str:
        """Texto del campo 'Duración'. Usa timestamps de Discord (sin ediciones periódicas)."""
        is_paused = self.pause_start is not None

        if song.duration == 0:
            if is_paused:
                return "⏸️ Pausado"
            return "📁 Archivo adjunto" if song.isFile else "🔴 En directo"

        total = self._formatDuration(song.duration)
        elapsed = min(self.getElapsedSeconds(), song.duration)

        # En pausa el tiempo está congelado: no hay cuenta regresiva.
        if is_paused:
            return f"⏸️ Pausado en `{self._formatDuration(elapsed)}` / `{total}`"

        end_ts = int(time.time()) + (song.duration - elapsed)

        return (
            f"▶️ Termina <t:{end_ts}:R> (a las <t:{end_ts}:T>)\n"
            f"⏱️ Duración total: `{total}`"
        )

    def _buildPlayerEmbed(self, song: Song) -> discord.Embed:
        embed = discord.Embed(
            title="🎵 Reproduciendo ahora",
            description=f"**[{song.title}]({song.url})**",
            color=EMBED_COLOR,
        )

        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)

        embed.add_field(
            name="Duración",
            value=self.buildDurationValue(song),
            inline=False,
        )

        embed.add_field(
            name="Solicitada por",
            value=song.user.mention,
            inline=False,
        )

        embed.set_footer(text="Reproductor musical • Usa los botones para controlar la música")
        return embed

    async def updatePlayerTimestamp(self, paused: bool = False):
        """Reescribe el campo 'Duración' (se usa al pausar y al reanudar).

        El parámetro `paused` se conserva por compatibilidad: el estado
        real se toma de pause_start.
        """
        if not self.songQueue or self.start_time is None:
            return

        message = self.player_message

        if message is None or not message.embeds:
            return

        embed = message.embeds[0].copy()
        value = self.buildDurationValue(self.songQueue[0])

        for index, field in enumerate(embed.fields):
            if field.name == "Duración":
                embed.set_field_at(
                    index,
                    name="Duración",
                    value=value,
                    inline=field.inline
                )
                break
        else:
            return

        try:
            edited = await message.edit(embed=embed)
        except discord.NotFound:
            logging.warning("El mensaje del reproductor fue eliminado.")
            return
        except discord.HTTPException:
            logging.exception("No se pudo actualizar el reproductor.")
            return

        # Solo reemplazar si no apareció un mensaje nuevo mientras se editaba.
        if self.player_message is message:
            self.player_message = edited

    def markPlayerFinished(self):
        """Marca el mensaje del reproductor como finalizado (en segundo plano)."""
        message = self.player_message
        self.player_message = None

        if message is None or not message.embeds:
            return

        self._spawn(self._finishPlayerMessage(message))

    async def _finishPlayerMessage(self, message: discord.Message):
        embed = message.embeds[0].copy()

        for index, field in enumerate(embed.fields):
            if field.name == "Duración":
                embed.set_field_at(
                    index,
                    name="Duración",
                    value="✅ Finalizada",
                    inline=field.inline
                )
                break

        try:
            await message.edit(embed=embed, view=None)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            logging.exception("No se pudo marcar el reproductor como finalizado.")

    # ------------------------------------------------------------------
    # Historial y recomendaciones
    # ------------------------------------------------------------------

    def resetSongHistory(self):
        self.sessionRequestedSongs.clear()
        self.sessionRecommendedSongs.clear()
        self.sessionRecentSongs.clear()

        logging.info("Historial de canciones de la sesión reiniciado.")

   
    async def discardFailedSong(self, song: Song, reason: str):
        logging.error(
            "Descartando canción: %s. Motivo: %s",
            song.title,
            reason
        )

        if song in self.songQueue:
            self.songQueue.remove(song)
        elif song in self.recommendationQueue:
            self.recommendationQueue.remove(song)

        self._resetTimer()

        try:
            await self.textChannel.send(
                f"No se pudo reproducir **{song.title}**. "
                "Se intentará continuar con la siguiente canción."
            )
        except discord.HTTPException:
            logging.exception(
                "No se pudo avisar de la canción descartada."
            )

    def buildRecommendationQuery(self):
        context = self.getSessionMusicContext()
        last_requested = context["last_requested"]

        if last_requested is None:
            return None

        artist = self.getSongArtist(last_requested)
        logging.info(
            "Contexto de recomendación: canción='%s', artista='%s'",
            last_requested.title,
            artist
        )
        if not artist:
            logging.warning(
                "No se pudo identificar el artista de: %s",
                last_requested.title
            )
            return None

        return f"{artist} songs"

    async def getRecommendedSong(self):
        context = self.getSessionMusicContext()
        queries = []

        # 1. Priorizar la banda de la última solicitud manual.
        main_query = self.buildRecommendationQuery()
        if main_query:
            queries.append(main_query)

        # 2. Evitar repetir consultas idénticas.
        queries = list(dict.fromkeys(queries))

        for query in queries:
            candidate = await self.searchRecommendedSong(
                query,
                self.client.user,
                max_results=10
            )

            if candidate is not None:
                logging.info(
                    "Recomendación seleccionada con la búsqueda '%s': %s",
                    query,
                    candidate.title
                )
                return candidate

            logging.info(
                "La búsqueda no produjo una recomendación válida: %s",
                query
            )

        logging.warning(
            "No se encontraron recomendaciones válidas tras probar %s búsquedas.",
            len(queries)
        )
        return None


    def getSongArtist(self, song: Song) -> str | None:
        """Obtiene el artista de una canción usando sus metadatos o título."""
        artist = getattr(song, "artist", None)

        if artist and artist.strip():
            return artist.strip()

        title = song.title.strip()

        if " - " in title:
            artist = title.split(" - ", 1)[0].strip()

            if artist:
                return artist

        return None


    def _allKnownSongs(self):
        return chain(
            self.sessionRequestedSongs,
            self.sessionRecommendedSongs,
            self.sessionRecentSongs,
            self.songQueue,
        )

    def getExcludedIds(self) -> set:
        """Identificadores de todas las canciones que no deben recomendarse."""
        return {
            song_id
            for song_id in map(self.getSongIdentifier, self._allKnownSongs())
            if song_id
        }

    def getExcludedSongs(self):
        # Eliminar duplicados por URL, conservando el orden.
        unique_songs = []
        seen_ids = set()

        for song in self._allKnownSongs():
            song_id = self.getSongIdentifier(song)

            if song_id and song_id not in seen_ids:
                seen_ids.add(song_id)
                unique_songs.append(song)

        return unique_songs

    async def searchRecommendedSong(self, query, user, max_results=5):
        searcher = VideoSearcher()

        try:
            results = await searcher.getVideoInfoFromQuery(
                query,
                max_results=max_results
            )
        except Exception:
            logging.exception("Error buscando canciones recomendadas.")
            return None

        if not results:
            return None

        excluded_ids = self.getExcludedIds()

        for result in results:
            candidate = self._songFromResult(result, user)
            candidate_id = self.getSongIdentifier(candidate)

            if candidate_id and candidate_id not in excluded_ids:
                logging.info(
                    "Recomendación seleccionada: %s",
                    candidate.title
                )
                return candidate

            logging.debug(
                "Candidato repetido o sin identificador: %s",
                candidate.title
            )

        return None

    def filterExcludedSongs(self, candidates: list[Song]):
        excluded_ids = self.getExcludedIds()

        return [
            song for song in candidates
            if self.getSongIdentifier(song) not in excluded_ids
        ]

    def getSongIdentifier(self, song: Song):
        # Usar el enlace como identificador de la canción.
        return song.url or song.link

    def getSessionMusicContext(self):
        requested_songs = self.sessionRequestedSongs.copy()
        recommended_songs = self.sessionRecommendedSongs.copy()

        # La última canción solicitada manualmente será la referencia principal.
        last_requested = requested_songs[-1] if requested_songs else None

        # Dar más importancia a las solicitudes manuales que a las recomendaciones.
        return {
            "last_requested": last_requested,
            "requested_songs": requested_songs,
            "recommended_songs": recommended_songs,
            "recent_songs": self.sessionRecentSongs.copy(),
        }

    # ------------------------------------------------------------------
    # Getters y ajustes simples
    # ------------------------------------------------------------------

    # function to check if the bot is currently connected to a voice channel
    def isConnectedToVC(self) -> bool:
        return self._getVoiceClient() is not None

    # function to get the voice and text channel
    def getVideoAndTextChannel(self) -> Tuple[discord.VoiceChannel, discord.TextChannel]:
        return self.voiceChannel, self.textChannel

    # function to get the song queue
    def getSongQueue(self) -> list:
        return self.songQueue

    # function to get isMajorityVote
    def getIsMajorityVote(self) -> bool:
        return self.isMajorityVote

    async def getCurrentDuration(self) -> str:
        if not self.songQueue:
            return "No hay ninguna canción reproduciéndose actualmente."

        song = self.songQueue[0]
        elapsed = self.getElapsedSeconds()

        if song.duration == 0:
            return f"*{self._formatDuration(elapsed)}* transcurridos desde el inicio de la transmisión."

        elapsed = min(elapsed, song.duration)
        return (
            f"*{self._formatDuration(elapsed)}* **/** "
            f"*{self._formatDuration(song.duration)}*"
        )

    # function to set the transcription channel
    async def setTranscriptionChannel(self, transcriptionChannel: discord.TextChannel) -> discord.TextChannel:
        logging.debug("Starting /transcribe function")
        self.transcriptionChannel = transcriptionChannel
        return self.transcriptionChannel

    # function to set looping
    async def setLooping(self) -> bool:
        logging.debug("Starting /loop function")
        self.isLooping = not self.isLooping
        return self.isLooping

    # function to set majority vote
    async def setMajorityVote(self) -> bool:
        logging.debug("Starting /majorvote function")
        self.isMajorityVote = not self.isMajorityVote
        return self.isMajorityVote

    # function to shuffle the queue (the current song stays first)
    async def shuffleQueue(self):
        logging.debug("Starting /shuffle function")

        if not self.isConnectedToVC() or len(self.songQueue) <= 1:
            return

        rest = self.songQueue[1:]
        random.shuffle(rest)
        self.songQueue[1:] = rest

    async def searchSongs(self, query: str):
        logging.debug("Starting /search function")

        try:
            result = await VideoSearcher().getSearchResults(query)
        except Exception as e:
            logging.exception("Search error: %s", query)
            await self.textChannel.send(f"No se pudieron buscar canciones: {e}")
            return None

        if not result:
            await self.textChannel.send(f"No se pudieron buscar canciones: no hay resultados para '{query}'.")
            return None

        return result

    # ------------------------------------------------------------------
    # Votaciones, saltar, pausar, detener
    # ------------------------------------------------------------------

    async def _runVote(self, voice_client, prompt: str, required_fn, timeout: int, message: discord.Message = None) -> str:
        """Ejecuta una votación por reacciones.

        Devuelve: 'approved', 'rejected', 'no_majority' o 'timeout'.
        `required_fn` recibe la cantidad de votantes elegibles y devuelve los votos necesarios.
        """
        if message is None:
            message = await self.textChannel.send(prompt)

        for emoji in VOTE_EMOJIS:
            await message.add_reaction(emoji)

        def check(reaction, user):
            return (
                reaction.message.id == message.id
                and str(reaction.emoji) in VOTE_EMOJIS
                and not user.bot
                and user in voice_client.channel.members
            )

        eligible_users = [m for m in voice_client.channel.members if not m.bot]
        required_votes = required_fn(len(eligible_users))
        logging.debug(f"required votes: {required_votes}")

        vote_counts = {"✅": 0, "❌": 0}
        voters = set()
        loop = self.client.loop
        deadline = loop.time() + timeout

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return "timeout"

            try:
                reaction, user = await self.client.wait_for(
                    "reaction_add",
                    timeout=remaining,
                    check=check
                )
            except asyncio.TimeoutError:
                return "timeout"

            if user.id in voters:
                continue

            voters.add(user.id)
            vote_counts[str(reaction.emoji)] += 1

            if vote_counts["✅"] >= required_votes:
                return "approved"
            if vote_counts["❌"] >= required_votes:
                return "rejected"
            if len(voters) >= len(eligible_users):
                return "no_majority"

    # function to skip current song

    async def skipSong(self, message: discord.Message = None):
        logging.debug("Starting /skip function")

        voice_client = self._getVoiceClient()

        if voice_client is None:
            return

        if not voice_client.is_playing() and not voice_client.is_paused():
            await self.textChannel.send("No hay ninguna canción reproduciéndose.")
            return

        if not self.isMajorityVote:
            # El callback de finalización avanzará la cola.
            voice_client.stop_playing()
            return

        result = await self._runVote(
            voice_client,
            "Saltar canción?",
            required_fn=lambda n: (n // 2) + 1,
            timeout=30,
            message=message,
        )

        if result == "approved":
            await self.textChannel.send(
                "Mayoría alcanzada. Saltando la canción."
            )
            # No vaciar las colas; el callback se encargará del avance.
            voice_client.stop_playing()

        elif result == "rejected":
            await self.textChannel.send(
                "Mayoría alcanzada. La canción continuará."
            )

        elif result == "no_majority":
            await self.textChannel.send(
                "No hubo mayoría. La canción continuará."
            )

        else:
            await self.textChannel.send(
                "Votación agotada por tiempo. La canción continuará."
            )


    # Pausar o reanudar la canción actual
    async def pauseSong(self):
        logging.debug("Starting /pause function")

        voice_client = self._getVoiceClient()
        if voice_client is None:
            return

        if voice_client.is_paused():
            voice_client.resume()
            self._applyResume()
            await self.updatePlayerTimestamp()
            return False

        if voice_client.is_playing():
            voice_client.pause()
            self.pause_start = int(time.time())
            await self.updatePlayerTimestamp()
            return True

        # No hay nada sonando.
        return

    # Reanudar la canción actual
    async def resumeSong(self):
        logging.debug("Starting /resume function")

        voice_client = self._getVoiceClient()
        if voice_client is None or not voice_client.is_paused():
            return

        voice_client.resume()
        self._applyResume()
        await self.updatePlayerTimestamp()

    
    async def _stopEverything(self, voice_client):
        # Limpiar ambas colas.
        self.songQueue.clear()
        self.recommendationQueue.clear()

        # Reiniciar los estados de reproducción.
        self.isLooping = False
        self.currentSong = None
        self.currentSongIsRecommendation = False

        self.resetSongHistory()
        self._resetTimer()
        self.markPlayerFinished()

        # Detener el audio después de limpiar el estado para que
        # el callback de finalización no avance una cola vacía.
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop_playing()

        await self._setPresence(None)

        logging.info("Playback stopped and both queues cleared.")


    # function to stop all songs
    async def stopAllSongs(self, message: discord.Message = None):
        logging.debug("Starting /stop function")

        voice_client = self._getVoiceClient()
        if voice_client is None:
            return

        if not self.isMajorityVote:
            await self._stopEverything(voice_client)
            return

        result = await self._runVote(
            voice_client,
            "Stop current song and clear the queue? ***Needs all votes***",
            required_fn=lambda n: n,
            timeout=45,
            message=message,
        )

        if result == "approved":
            await self.textChannel.send("Se alcanzó la mayoría de votos. Deteniendo la canción y vaciando la cola.")
            await self._stopEverything(voice_client)
        elif result == "rejected":
            await self.textChannel.send("Se alcanzó la mayoría de votos en contra. La canción continuará reproduciéndose.")
        elif result == "no_majority":
            await self.textChannel.send("No se alcanzó una mayoría de votos. La canción continuará reproduciéndose.")
        else:
            await self.textChannel.send("Se agotó el tiempo de votación. La canción continuará reproduciéndose.")

    # ------------------------------------------------------------------
    # Conexión a voz
    # ------------------------------------------------------------------

    async def _disconnect(self, force: bool):
        voice_client = self._getVoiceClient()
        if voice_client is None:
            return

        self._resetSession()
        await voice_client.disconnect(force=force)

    # function to soft disconnect the bot. This is used when a bot is the only one left in a voice channel and should leave, being able to reconnect later
    async def softDisconnect(self):
        await self._disconnect(force=False)
        logging.debug(f"{self.guild.name} Music Controller has been soft disconnected.")

    # function to hard disconnect the bot.
    async def hardDisconnect(self):
        await self._disconnect(force=True)
        logging.debug(f"{self.guild.name} Music Controller has been hard disconnected.")

    # function to join the channel and start listening
    async def two_four_seven(self, voiceChannel: discord.VoiceChannel, textChannel: discord.TextChannel) -> discord.VoiceClient:
        logging.debug("Starting /247 function")

        voice_client = self._getVoiceClient()

        if voice_client is None:
            logging.debug("Bot is not in channel, connecting...")
            await voiceChannel.connect(cls=voice_recv.VoiceRecvClient)
            logging.info(f"Bot succesfully connected to {voiceChannel.name}")
            self.voiceChannel = voiceChannel
            self.textChannel = textChannel
            await self.startVoiceRecording()
            return None

        logging.debug(f"Bot is already in channel: {voice_client.channel.name}")
        await self.startVoiceRecording()
        return voice_client

    # ------------------------------------------------------------------
    # Reconocimiento de voz
    # ------------------------------------------------------------------

    # function to start the voice listening
    async def startVoiceRecording(self):
        logging.debug("in voice recording")

        voice_client = self._getVoiceClient()
        if voice_client is None:
            return

        # Evitar registrar un segundo sink si ya está escuchando.
        is_listening = getattr(voice_client, "is_listening", None)
        if callable(is_listening) and is_listening():
            return

        # override the speech recognition to use google
        def process_wit(recognizer: sr.Recognizer, audio: sr.AudioData, user) -> Optional[str]:
            if len(audio.frame_data) < MIN_AUDIO_BYTES:
                return None

            if DEBUG_SAVE_AUDIO:
                with open("debug_venus.wav", "wb") as f:
                    f.write(audio.get_wav_data())

            try:
                text = recognizer.recognize_google(audio, language="es-CL")

                logging.info(f"Escuchado ({user}): {text}")
                asyncio.run_coroutine_threadsafe(
                    self.handleTranscribedAudio(user, text),
                    self.client.loop
                )
                return text
            except sr.UnknownValueError:
                logging.debug("No se pudo entender el audio.")
            except Exception:
                logging.exception("Error al transcribir.")
            return None

        try:
            voice_client.listen(
                vr_sr.SpeechRecognitionSink(
                    process_cb=process_wit,
                    default_recognizer="google"
                )
            )
        except Exception:
            logging.exception("No se pudo iniciar la escucha de voz.")

    # function to handle the transcribed audio for actual commands
    async def handleTranscribedAudio(self, user, text):
        text = (text or "").strip()
        if not text:
            logging.debug("text is empty. Doing nothing")
            return

        logging.info(f"{user.display_name}: {text}")

        # Enviar la transcripción sin retrasar el procesamiento del comando.
        if self.transcriptionChannel:
            self._spawn(
                self.transcriptionChannel.send(f"**{user.display_name}**: {text}")
            )

        text_lower = text.lower()

        counters = (await WordCounter().loadWordCounters())[0]
        if any(word in text_lower for word in counters):
            await self.handle_word_counter_keyword(user, text_lower, counters)

        bot_keywords = await BotKeywords().loadBotKeywords()
        if not bot_keywords:
            return

        alternatives = "|".join(re.escape(k) for k in bot_keywords)
        match = re.search(rf"(?:{alternatives})\s+(\w+)", text, re.IGNORECASE)
        if not match:
            logging.debug("No command keyword found after bot name")
            return

        keyword = match.group(1).lower()
        keyword = VOICE_ALIASES.get(keyword, keyword)
        if keyword not in VOICE_COMMANDS:
            logging.debug(f"'{keyword}' is not a valid command keyword")
            return

        banned_users = await BannedUsers().loadBannedUserIDs()
        if user.id in banned_users:
            await self.textChannel.send(f"El usuario **{user.display_name}** ha sido baneado por el Mambo.")
            return

        handler = getattr(self, VOICE_COMMANDS[keyword], None)
        if handler:
            await handler(user, text)

    async def handle_word_counter_keyword(self, user, text, mapping=None):
        logging.debug("in handle_word_counter_keyword")
        wordCounterClass = WordCounter()

        if mapping is None:
            mapping = (await wordCounterClass.loadWordCounters())[0]

        text = text.lower()
        avatar_url = self.client.user.display_avatar.url
        counter_hits = {}

        for keyword, counter_name in mapping.items():
            count = text.count(keyword)
            if count > 0:
                counter_hits[counter_name] = counter_hits.get(counter_name, 0) + count
                for _ in range(count):
                    await wordCounterClass.incrementCounterForKeyword(keyword)
                    new_count = await wordCounterClass.getCount(counter_name)
                    embed = discord.Embed(
                        title=f"{counter_name.capitalize()} Counter:",
                        description=f"{new_count} - {user.display_name}",
                        color=EMBED_COLOR,
                    )
                    embed.set_thumbnail(url=avatar_url)
                    await self.textChannel.send(embed=embed)

        logging.info(f"{user.display_name} triggered updates for: {counter_hits}")

    async def handle_recommend_keyword(self, user, text):
        logging.debug("In handle_recommend_keyword")

        if not self.isConnectedToVC():
            await self.textChannel.send(
                "Necesito estar conectado a un canal de voz para recomendar música."
            )
            return

        recommended_song = await self.getRecommendedSong()

        if recommended_song is None:
            await self.textChannel.send(
                "No encontré una recomendación disponible. "
                "Prueba después de escuchar o solicitar otra canción."
            )
            return

        await self.queueSong(
            recommended_song,
            is_recommendation=True
        )


    async def handle_play_keyword(self, user, text):
        logging.debug("In handle_play_keyword")
        bot_keywords = await BotKeywords().loadBotKeywords()

        match = None
        if bot_keywords:
            alternatives = "|".join(re.escape(k) for k in bot_keywords)
            match = re.search(
                rf"(?:{alternatives})\s+(?:play|reproduce|pon|toca)\s+(.*)",
                text,
                re.IGNORECASE
            )

        if not match:
            logging.debug("No query found after 'keyword play', assume user wants to resume")
            await self.textChannel.send("Comando de voz - Continuando reproducción")
            await self.resumeSong()
            return

        query = match.group(1).strip()
        await self.textChannel.send(f"Comando de voz - Buscando: {query}")
        await self.handleYoutubeSearch(user, query)

    async def handle_pause_keyword(self, user, text):
        logging.debug("In handle_pause_keyword")
        voice_client = self._getVoiceClient()
        if voice_client is None:
            return

        if not voice_client.is_paused():
            await self.textChannel.send("Comando de voz - Detener canción")
        else:
            await self.textChannel.send("Comando de voz - Seguir escuchando")
        await self.pauseSong()

    async def handle_skip_keyword(self, user, text):
        logging.debug("In handle_skip_keyword")
        if self.isConnectedToVC():
            if not self.isMajorityVote:
                await self.textChannel.send("Comando de voz - Saltar canción")
            await self.skipSong()

    async def handle_stop_keyword(self, user, text):
        logging.debug("In handle_stop_keyword")
        if self.isConnectedToVC():
            if not self.isMajorityVote:
                await self.textChannel.send("Comando de voz - Deteniendo música y reiniciando cola")
            await self.stopAllSongs()

    async def handle_loop_keyword(self, user, text):
        logging.debug("In handle_loop_keyword")
        if self.isConnectedToVC():
            if await self.setLooping():
                await self.textChannel.send("Comando de voz - Repetir")
            else:
                await self.textChannel.send("Comando de voz - No repetir")

    # ------------------------------------------------------------------
    # Origen de las canciones
    # ------------------------------------------------------------------

    async def handleFile(self, user: discord.User, file: discord.Attachment):
        logging.debug("In handleFile")
        fileSong = Song(
            file.filename,
            file.url,
            file.url,
            self.client.user.display_avatar.url,
            0,
            user,
            isFile=True
        )
        await self.queueSong(fileSong)

    async def determineSongSource(self, user: discord.User, query: str):
        logging.debug("In Determine Song Source")
        query_lower = query.lower()

        if YOUTUBE_RE.search(query_lower):
            logging.debug("Detected YouTube link")
            if YOUTUBE_PLAYLIST_RE.search(query_lower):
                logging.debug("Detected YouTube playlist")
                return await self.handleYoutubePlaylist(user, query)
            return await self.handleYoutubeLink(user, query)

        if SPOTIFY_RE.search(query_lower):
            logging.debug("Detected Spotify link")
            if SPOTIFY_PLAYLIST_RE.search(query_lower):
                logging.debug("Detected spotify playlist/album")
                return await self.handleSpotifyPlaylist(user, query)
            return await self.handleSpotifyLink(user, query)

        if SOUNDCLOUD_RE.search(query_lower):
            logging.debug("Detected SoundCloud link")
            if SOUNDCLOUD_PLAYLIST_RE.search(query_lower):
                logging.debug("Detected SoundCloud playlist")
                return await self.handleSoundCloudPlaylist(user, query)
            return await self.handleSoundCloudLink(user, query)

        logging.debug("Detected search query - assuming YouTube search")
        return await self.handleYoutubeSearch(user, query)

    async def _handleSingleUrl(self, user, url):
        """Canción individual de YouTube o SoundCloud a partir de su URL."""
        try:
            result = await VideoSearcher().getVideoInfoFromURL(url)
        except Exception as e:
            logging.exception("Error obteniendo la canción: %s", url)
            await self.textChannel.send(f"No se pudo añadir la canción: {e}")
            return

        if not result:
            await self.textChannel.send("No se encontró la canción.")
            return

        await self.queueSong(self._songFromResult(result, user, fallback_url=url))

    async def _announcePlaylist(self, thumbnail: str, name, count):
        embed = discord.Embed(
            title="Añadiendo lista de reproducción:",
            color=EMBED_COLOR,
        )
        embed.set_thumbnail(url=thumbnail)
        embed.add_field(name="Nombre de la lista", value=name, inline=False)
        embed.add_field(name="# Cantidad de canciones", value=count, inline=False)
        await self.textChannel.send(embed=embed)

    async def _handleUrlPlaylist(self, user, url):
        """Playlist de YouTube o SoundCloud a partir de su URL."""
        searcher = VideoSearcher()

        try:
            result = await searcher.getPlaylistInfo(url)
        except Exception as e:
            logging.exception("Error obteniendo la playlist: %s", url)
            await self.textChannel.send(f"No se encontró la lista de reproducción: {e}")
            return

        if not result:
            await self.textChannel.send("No se encontró la lista de reproducción.")
            return

        metadata = result.pop(0)
        thumbnail = metadata.get('thumbnail') or self.client.user.display_avatar.url
        await self._announcePlaylist(
            thumbnail,
            metadata['playlist_name'],
            metadata['song_count']
        )

        for entry in result:
            logging.debug(f"Searching for {entry['url']}")
            try:
                info = await searcher.getVideoInfoFromURL(entry['url'])
            except Exception as e:
                logging.error(e)
                await self.textChannel.send(f"No se pudo añadir la canción: {e}")
                continue

            if not info:
                await self.textChannel.send("No se encontró la canción.")
                continue

            await self.queueSong(
                self._songFromResult(info, user, fallback_url=entry['url']),
                announce=False
            )

    async def handleYoutubeLink(self, user, url):
        logging.debug("In handleYoutubeLink")
        await self._handleSingleUrl(user, url)

    async def handleYoutubePlaylist(self, user, url):
        logging.debug("In handleYoutubePlaylist")
        await self._handleUrlPlaylist(user, url)

    async def handleSoundCloudLink(self, user, url):
        logging.debug("In handleSoundCloudLink")
        await self._handleSingleUrl(user, url)

    async def handleSoundCloudPlaylist(self, user, url):
        logging.debug("In handleSoundCloudPlaylist")
        await self._handleUrlPlaylist(user, url)

    async def _findSongByQuery(self, user, query: str) -> Optional[Song]:
        """Busca en YouTube y devuelve el primer resultado como Song."""
        try:
            results = await VideoSearcher().getVideoInfoFromQuery(query)
        except Exception as e:
            logging.exception("Error buscando: %s", query)
            await self.textChannel.send(f"No se pudo añadir la canción: {e}")
            return None

        if not results:
            await self.textChannel.send("No se encontró la canción.")
            return None

        # Para las búsquedas manuales, usar el primer resultado.
        return self._songFromResult(results[0], user)

    async def handleYoutubeSearch(self, user, query):
        logging.debug("In handleYoutubeSearch")

        song = await self._findSongByQuery(user, query)
        if song is not None:
            await self.queueSong(song)

    async def handleSpotifyLink(self, user, url):
        logging.debug("In handleSpotifyLink")

        try:
            info = await self.spotify.getSpotifySongInfo(url)
        except Exception as e:
            logging.exception("Error obteniendo la canción de Spotify: %s", url)
            await self.textChannel.send(f"No se pudo añadir la canción: {e}")
            return

        if not info:
            await self.textChannel.send("No se encontró la canción.")
            return

        song = await self._findSongByQuery(user, f"{info['title']} by {info['artist']}")
        if song is not None:
            await self.queueSong(song)

    async def handleSpotifyPlaylist(self, user, playlist):
        logging.debug("In handleSpotifyPlaylist")

        try:
            result = await self.spotify.getSpotifyPlaylistInfo(playlist)
        except Exception as e:
            logging.exception("Error obteniendo la playlist de Spotify: %s", playlist)
            await self.textChannel.send(f"No se pudo obtener la lista de Spotify o el álbum: {e}")
            return

        if not result:
            await self.textChannel.send("No se pudo obtener la lista de Spotify o el álbum.")
            return

        playlist_info = result.pop(0)
        thumbnail = playlist_info.get('thumbnail') or self.client.user.display_avatar.url
        await self._announcePlaylist(thumbnail, playlist_info['title'], len(result))

        searcher = VideoSearcher()

        for track in result:
            query = f"{track['title']} by {track['artist']}"

            logging.debug("Searching for %s", query)

            try:
                search_results = await searcher.getVideoInfoFromQuery(query)
            except Exception:
                logging.exception("Error buscando canción de Spotify: %s", query)
                await self.textChannel.send(f"No se pudo añadir la canción: {track['title']}")
                continue

            if not search_results:
                await self.textChannel.send(f"No se encontró la canción: {track['title']}")
                continue

            await self.queueSong(
                self._songFromResult(search_results[0], user),
                announce=False
            )

    # ------------------------------------------------------------------
    # Cola de reproducción
    # ------------------------------------------------------------------

    
    async def _playFirstAvailable(self) -> bool:
        """Reproduce la siguiente canción disponible según su prioridad."""

        while True:
            song = self._getNextQueuedSong()

            if song is None:
                return False

            voice_client = self._getVoiceClient()

            if voice_client is None:
                logging.error("El bot no está conectado al canal de voz.")
                await self.textChannel.send(
                    "No estoy conectado a un canal de voz."
                )
                return False

            if voice_client.is_playing() or voice_client.is_paused():
                logging.warning(
                    "Ya hay una reproducción activa; se conserva la cola."
                )
                return True

            if await self.playSong(song):
                return True

            # Si falla, retirar únicamente la canción que se intentó reproducir.
            if song in self.songQueue:
                self.songQueue.remove(song)
            elif song in self.recommendationQueue:
                self.recommendationQueue.remove(song)

            logging.warning(
                "Se retiró de la cola la canción fallida: %s",
                song.title
            )

            try:
                await self.textChannel.send(
                    f"No se pudo reproducir **{song.title}**."
                )
            except discord.HTTPException:
                logging.exception(
                    "No se pudo avisar de la canción fallida."
                )


    
    async def queueSong(
        self,
        song: Song,
        is_recommendation: bool = False,
        announce: bool = True
    ):
        logging.debug("Añadiendo canción a la cola.")

        # Elegir la cola correspondiente.
        target_queue = (
            self.recommendationQueue
            if is_recommendation
            else self.songQueue
        )

        # Evitar duplicados en ambas colas y en el historial reciente.
        all_queued_songs = self.songQueue + self.recommendationQueue

        def normalize_title(title: str) -> str:
            return re.sub(r"\s+", " ", title).strip().casefold()

        title = normalize_title(song.title)

        if any(
            normalize_title(queued_song.title) == title
            for queued_song in all_queued_songs
        ):
            logging.info("Canción ya en cola; se ignora: %s", song.title)
            return

        if is_recommendation and any(
            normalize_title(recent_song.title) == title
            for recent_song in self.sessionRecentSongs
        ):
            logging.info(
                "Recomendación reproducida recientemente; se ignora: %s",
                song.title
            )
            return

        target_queue.append(song)

        # Registrar la solicitud o recomendación en su historial.
        history = (
            self.sessionRecommendedSongs
            if is_recommendation
            else self.sessionRequestedSongs
        )
        history.append(song)
        del history[:-MAX_SESSION_HISTORY]

        logging.info(
            "Canción añadida a %s: %s",
            "recommendationQueue" if is_recommendation else "songQueue",
            song.title
        )

        voice_client = self._getVoiceClient()
        is_playing = (
            voice_client is not None
            and (voice_client.is_playing() or voice_client.is_paused())
        )

        # Iniciar reproducción solo si no hay una canción sonando.
        if not is_playing and self.currentSong is None:
            await self._playFirstAvailable()
            return

        if not announce:
            return

        embed = discord.Embed(
            title=(
                "Recomendación añadida:"
                if is_recommendation
                else "Añadida a la cola:"
            ),
            description=song.title,
            color=EMBED_COLOR
        )

        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)

        await self.textChannel.send(embed=embed)


    
    async def queuePlaylist(self, playlist: list):
        logging.debug("In queuePlaylist")

        if not playlist:
            logging.warning("La playlist está vacía.")
            return

        # El primer elemento contiene la miniatura de la playlist.
        thumbnail = playlist.pop(0)

        # Las canciones de la playlist son solicitudes explícitas.
        for song in playlist:
            await self.queueSong(
                song,
                is_recommendation=False,
                announce=False
            )

        # Mostrar un único mensaje para toda la playlist.
        embed = discord.Embed(
            title="Playlist añadida a la cola:",
            color=EMBED_COLOR
        )

        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        added_songs = playlist[:25]

        if added_songs:
            for i, song in enumerate(added_songs, start=1):
                embed.add_field(
                    name=str(i),
                    value=song.title,
                    inline=False
                )
        else:
            embed.description = "No se añadieron canciones nuevas."

        if len(playlist) > 25:
            embed.set_footer(text=f"...y {len(playlist) - 25} más")

        await self.textChannel.send(embed=embed)

        # Iniciar reproducción si ninguna canción está sonando.
        voice_client = self._getVoiceClient()
        is_playing = (
            voice_client is not None
            and (voice_client.is_playing() or voice_client.is_paused())
        )

        if self.currentSong is None and not is_playing:
            await self._playFirstAvailable()


    
    async def play_next_song(
        self,
        pop_current: bool = True,
        finished: Optional[Song] = None
    ):
        logging.debug("Avanzando a la siguiente canción.")

        # Guardar la canción que terminó antes de limpiar el estado actual.
        current_song = finished or self.currentSong

        self.markPlayerFinished()

        # Si repetir está activo, volver a reproducir la misma canción.
        if self.isLooping and current_song is not None:
            self._resetTimer()

            if await self.playSong(current_song):
                return

            logging.warning(
                "No se pudo repetir %s; se desactivará el modo repetir.",
                current_song.title
            )
            self.isLooping = False

        # Retirar únicamente la canción que terminó o falló.
        if pop_current and current_song is not None:
            if current_song in self.songQueue:
                self.songQueue.remove(current_song)
            elif current_song in self.recommendationQueue:
                self.recommendationQueue.remove(current_song)

            logging.info(
                "Canción retirada de la cola: %s",
                current_song.title
            )

        # Limpiar el estado de la canción anterior.
        self.currentSong = None
        self.currentSongIsRecommendation = False
        self._resetTimer()

        # Primero solicitudes explícitas; después recomendaciones pendientes.
        if await self._playFirstAvailable():
            return

        # Si no queda nada, generar una recomendación.
        recommended_song = await self.getRecommendedSong()

        if recommended_song is not None:
            await self.queueSong(
                recommended_song,
                is_recommendation=True
            )

            # Verificar si se agregó y pudo iniciar la reproducción.
            if self.currentSong is not None:
                return

            if await self._playFirstAvailable():
                return

        await self._setPresence(None)
        logging.info("No hay más canciones disponibles para reproducir.")

    
    async def handlePlaybackFinished(self, song: Song, error):
        # Ignorar callbacks antiguos, por ejemplo después de detener la música.
        if self.currentSong is not song:
            logging.info(
                "Aviso de fin ignorado: la canción ya no es la actual (%s).",
                song.title
            )
            return

        if error:
            await self.discardFailedSong(
                song,
                f"Error durante la reproducción: {error}"
            )
            await self.play_next_song(pop_current=False)
            return

        await self.play_next_song(finished=song)


    async def _refreshLinkIfNeeded(self, song: Song) -> bool:
        """Renueva el enlace de audio si falta o está por caducar."""
        if song.isFile:
            return True

        expiration = getSongExpiration(song.link) if song.link else None

        if song.link and (
            expiration is None
            or expiration > int(time.time()) + LINK_EXPIRY_MARGIN
        ):
            return True

        try:
            result = await VideoSearcher().getVideoInfoFromURL(song.url)
        except Exception:
            logging.exception(
                "No se pudo renovar el enlace de audio: %s",
                song.title
            )
            return False

        if not result or not result.get("link"):
            logging.error("No se obtuvo un enlace nuevo para %s", song.title)
            return False

        song.link = result["link"]
        return True

    
    async def playSong(self, song: Optional[Song] = None):
        logging.debug("Reproduciendo.")

        # Si no se especifica una canción, elegir la siguiente por prioridad.
        if song is None:
            song = self._getNextQueuedSong()

        if song is None:
            self.currentSong = None
            self.currentSongIsRecommendation = False
            self._resetTimer()
            return False

        voice_client = self._getVoiceClient()

        if voice_client is None:
            logging.error("El bot no está conectado al canal de voz.")
            await self.textChannel.send("No estoy conectado a un canal de voz.")
            return False

        if voice_client.is_playing() or voice_client.is_paused():
            logging.warning("Ya hay una reproducción activa.")
            return False

        if not await self._refreshLinkIfNeeded(song):
            return False

        try:
            player = discord.FFmpegOpusAudio(
                song.link,
                **FFMPEG_OPTIONS,
                stderr=sys.stderr
            )
        except Exception:
            logging.exception(
                "No se pudo crear la fuente de audio para %s",
                song.title
            )
            return False

        def after_playing(error):
            if error:
                logging.error(
                    "Error durante la reproducción de %s: %r",
                    song.title,
                    error
                )
            else:
                logging.info(
                    "Discord terminó la reproducción: %s",
                    song.title
                )

            if not voice_client.is_connected():
                return

            future = asyncio.run_coroutine_threadsafe(
                self.handlePlaybackFinished(song, error),
                self.client.loop
            )
            future.add_done_callback(self._logFutureError)

        try:
            voice_client.play(player, after=after_playing)
        except Exception:
            logging.exception(
                "No se pudo iniciar la reproducción de %s",
                song.title
            )
            player.cleanup()
            return False

        # Registrar qué canción está sonando y de qué cola procede.
        self.currentSong = song
        self.currentSongIsRecommendation = song in self.recommendationQueue

        self.start_time = int(time.time())
        self.pause_start = None
        self.pause_duration = 0

        if not self.sessionRecentSongs or self.sessionRecentSongs[-1] is not song:
            self.sessionRecentSongs.append(song)
            del self.sessionRecentSongs[:-2]

        try:
            self.player_message = await self.textChannel.send(
                embed=self._buildPlayerEmbed(song),
                view=MusicButtons(client=self.client)
            )
        except discord.HTTPException:
            logging.exception("No se pudo enviar el mensaje del reproductor.")
            self.player_message = None

        await self._setPresence(song.title)
        return True
