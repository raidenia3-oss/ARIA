import collections
import numpy as np


class VADWrapper:
    def __init__(
        self, sample_rate: int = 16000, frame_duration_ms: int = 30, aggressiveness: int = 2
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.aggressiveness = aggressiveness
        self._ring = collections.deque(maxlen=32)

    def is_speech(self, frame: bytes) -> bool:
        samples = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(samples**2)))
        self._ring.append(rms)
        floor = float(np.percentile(self._ring, 10)) if self._ring else 0.0
        if rms < max(floor * 1.4, 120.0):
            return False
        zcr = float(np.mean(np.abs(np.diff(np.sign(samples))))) if samples.size > 1 else 0.0
        return zcr > 0.02
