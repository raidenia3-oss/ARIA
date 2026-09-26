import queue
import threading
import time
import logging
from typing import Optional, Callable

import numpy as np
import sounddevice as sd
from AURA_Core.voice.vad_wrapper import VADWrapper

logger = logging.getLogger("AURA_Voice")


class AudioStreamer:
    def __init__(
        self,
        on_speech_detected: Optional[Callable[[bytes], None]] = None,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        vad_aggressiveness: int = 2,
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.on_speech_detected = on_speech_detected
        self._running = False
        self._stream_lock = threading.Lock()
        self._audio_queue = queue.Queue(maxsize=1024)
        self._vad = VADWrapper(
            sample_rate=sample_rate,
            frame_duration_ms=frame_duration_ms,
            aggressiveness=vad_aggressiveness,
        )

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.debug(f"Audio callback status: {status}")
        try:
            self._audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            logger.warning("Cola de audio llena; se descarta un frame.")

    def start(self):
        with self._stream_lock:
            if self._running:
                return
            self._running = True
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.frame_size,
                dtype="int16",
                channels=1,
                callback=self._callback,
            )
            self._stream.start()
            threading.Thread(target=self._process_loop, daemon=True).start()
            logger.info("AudioStreamer iniciado (RawInputStream).")

    def stop(self):
        with self._stream_lock:
            self._running = False
            if hasattr(self, "_stream") and self._stream:
                self._stream.stop()
                self._stream.close()
            logger.info("AudioStreamer detenido.")

    def _process_loop(self):
        speech_buffer = bytearray()
        in_speech = False
        while self._running:
            try:
                raw = self._audio_queue.get(timeout=1.0)
            except queue.Empty:
                if in_speech:
                    speech = bytes(speech_buffer)
                    speech_buffer.clear()
                    in_speech = False
                    if self.on_speech_detected:
                        self.on_speech_detected(speech)
                continue

            is_speech = self._vad.is_speech(raw)
            if is_speech:
                if not in_speech:
                    in_speech = True
                    speech_buffer.clear()
                speech_buffer.extend(raw)
            else:
                if in_speech:
                    speech = bytes(speech_buffer)
                    speech_buffer.clear()
                    in_speech = False
                    if self.on_speech_detected:
                        self.on_speech_detected(speech)
