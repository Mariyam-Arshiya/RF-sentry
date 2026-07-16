import csv
import os
import config

HEADERS = [
    'timestamp', 'rssi_dbm', 'signal_pct',
    'ping_ms', 'rssi_std', 'score',
    'detection', 'confidence_pct'
]


class DataLogger:
    def __init__(self):
        self.path = config.LOG_FILE
        self._init_file()

    def _init_file(self):
        if not os.path.exists(self.path):
            with open(self.path, 'w', newline='') as f:
                csv.writer(f).writerow(HEADERS)

    def write(self, ts, rssi, pct, ping, std, score, level, conf):
        with open(self.path, 'a', newline='') as f:
            csv.writer(f).writerow([
                ts.strftime('%Y-%m-%d %H:%M:%S'),
                round(rssi, 2),
                pct,
                round(ping, 1),
                round(std, 4),
                round(score, 4),
                level,
                conf
            ])

    def open_file(self):
        os.startfile(self.path)
