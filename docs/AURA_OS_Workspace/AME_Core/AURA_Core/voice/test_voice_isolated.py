import time
import logging
from AURA_Core.voice.audio_streamer import AudioStreamer
from AURA_Core.voice.vad_wrapper import VADWrapper

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    streamer = AudioStreamer(
        on_speech_detected=lambda audio: print(f"Speech segment: {len(audio)} bytes"),
        sample_rate=16000,
        frame_duration_ms=30,
        vad_aggressiveness=2,
    )
    streamer.start()
    logging.info("Voice test running (10s)...")
    time.sleep(10)
    streamer.stop()
    logging.info("Voice test finished.")


if __name__ == "__main__":
    main()
