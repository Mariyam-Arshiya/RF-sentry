import numpy as np
from collections import deque
import config


class DetectionEngine:
    def __init__(self):
        self.rssi_buf      = deque(maxlen=config.WINDOW_SIZE)
        self.ping_buf      = deque(maxlen=config.WINDOW_SIZE)
        self.baseline_mean = None
        self.baseline_std  = None
        self.calibrated    = False

    def calibrate(self, samples):
        arr                = np.array(samples)
        self.baseline_mean = float(np.mean(arr))
        self.baseline_std  = float(np.std(arr))
        self.calibrated    = True
        return self.baseline_mean, self.baseline_std

    def push(self, rssi, ping):
        self.rssi_buf.append(rssi)
        self.ping_buf.append(ping)

    def analyze(self):
        if len(self.rssi_buf) < 10:
            return 'CALIBRATING', 0, {}

        rssi_arr    = np.array(self.rssi_buf)
        ping_arr    = np.array(self.ping_buf)
        recent_rssi = rssi_arr[-20:]
        recent_ping = ping_arr[-20:]

        rssi_std    = float(np.std(recent_rssi))
        rssi_mean   = float(np.mean(recent_rssi))
        rssi_range  = float(np.ptp(rssi_arr[-10:]))
        ping_std    = float(np.std(recent_ping))

        drift = 0.0
        if self.calibrated and self.baseline_mean is not None:
            drift = abs(rssi_mean - self.baseline_mean)

        score = (
            rssi_std   * 0.50 +
            rssi_range * 0.20 +
            ping_std   * 0.10 +
            drift      * 0.20
        )

        confidence = int(min(100, (score / config.THRESHOLD_HIGH) * 100))

        if score < config.THRESHOLD_LOW:
            level = 'SECURE'
        elif score < config.THRESHOLD_HIGH:
            level = 'MINOR_MOVEMENT'
        else:
            level = 'INTRUSION'

        stats = {
            'rssi_std'  : round(rssi_std, 4),
            'rssi_mean' : round(rssi_mean, 2),
            'rssi_range': round(rssi_range, 2),
            'ping_std'  : round(ping_std, 2),
            'drift'     : round(drift, 2),
            'score'     : round(score, 4),
        }

        return level, confidence, stats
