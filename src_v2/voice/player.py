import discord
import asyncio
import subprocess
from loguru import logger
from src_v2.voice.service import voice_service

class StreamingFFmpegSource(discord.AudioSource):
    def __init__(self, source_stream):
        self.source_stream = source_stream
        self.process = subprocess.Popen(
            ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-ar', '48000', '-ac', '2', 'pipe:1', '-loglevel', 'quiet'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        self._feeding_task = asyncio.create_task(self.feed_ffmpeg())

    async def feed_ffmpeg(self):
        try:
            async for chunk in self.source_stream:
                if self.process.stdin:
                    self.process.stdin.write(chunk)
                    self.process.stdin.flush()
            if self.process.stdin:
                self.process.stdin.close()
        except Exception as e:
            logger.error(f"Error feeding ffmpeg: {e}")

    def read(self):
        ret = self.process.stdout.read(3840)
        if len(ret) != 3840:
            return b""
        return ret

    def cleanup(self):
        if self.process:
            self.process.kill()
        if self._feeding_task:
            self._feeding_task.cancel()

async def play_text(voice_client: discord.VoiceClient, text: str, voice_id: str = None):
    """
    Generates audio for the text and plays it in the voice channel using streaming.
    """
    if not voice_client or not voice_client.is_connected():
        logger.warning("Voice client not connected.")
        return

    logger.info(f"play_text called with {len(text)} chars. Voice client: {voice_client.channel}")

    try:
        # Stop any current playback
        if voice_client.is_playing():
            logger.info("Stopping current playback to start new one.")
            voice_client.stop()

        # Create the streaming source
        stream = voice_service.generate_audio_stream(text, voice_id=voice_id)
        source = StreamingFFmpegSource(stream)
        
        voice_client.play(source, after=lambda e: logger.info(f"Playback finished. Error: {e}") if e else logger.info("Playback finished."))
        logger.info("Streaming playback started.")

    except Exception as e:
        logger.exception(f"Error in play_text: {e}")
