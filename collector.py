import re
import subprocess
import datetime
import config
from kalman import KalmanFilter


class WiFiCollector:
    def __init__(self):
        self.kalman    = KalmanFilter()
        self.last_rssi = -60.0
        self.last_ping = 10.0

    def rssi(self):
        try:
            raw = subprocess.check_output(
                'netsh wlan show interfaces',
                shell=True,
                universal_newlines=True,
                timeout=3
            )
            for line in raw.splitlines():
                if 'Signal' in line:
                    m = re.search(r'(\d+)\s*%', line)
                    if m:
                        pct            = int(m.group(1))
                        dbm            = (pct / 2) - 100
                        filtered       = self.kalman.update(dbm)
                        self.last_rssi = filtered
                        return filtered, pct
        except Exception:
            pass
        return self.last_rssi, 0

    def ping(self):
        try:
            raw = subprocess.check_output(
                f'ping -n {config.PING_COUNT} -w {config.PING_TIMEOUT_MS} {config.HOTSPOT_IP}',
                shell=True,
                universal_newlines=True,
                timeout=5
            )
            for pattern in [r'Average = (\d+)ms', r'time[=<](\d+)ms']:
                m = re.search(pattern, raw)
                if m:
                    self.last_ping = float(m.group(1))
                    return self.last_ping
        except Exception:
            pass
        return self.last_ping

    def sample(self):
        rssi_val, pct = self.rssi()
        ping_val      = self.ping()
        return {
            'rssi'   : rssi_val,
            'percent': pct,
            'ping'   : ping_val,
            'ts'     : datetime.datetime.now()
        }
