import re
import os
import subprocess
import datetime
import config
from kalman import KalmanFilter


SYSTEM32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
NETSH    = os.path.join(SYSTEM32, "netsh.exe")
PING     = os.path.join(SYSTEM32, "PING.EXE")


class WiFiCollector:
    def __init__(self):
        self.kalman    = KalmanFilter()
        self.last_rssi = -60.0
        self.last_ping = 10.0

    def rssi(self):
        try:
            raw = subprocess.check_output(
                [NETSH, "wlan", "show", "interfaces"],
                universal_newlines=True,
                timeout=3,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in raw.splitlines():
                if "Signal" in line and "%" in line:
                    match = re.search(r"(\d+)\s*%", line)
                    if match:
                        pct            = int(match.group(1))
                        dbm            = (pct / 2.0) - 100.0
                        filtered       = self.kalman.update(dbm)
                        self.last_rssi = filtered
                        return filtered, pct
        except Exception as e:
            print(f"[RSSI ERROR] {e}")
        return self.last_rssi, 0

    def ping(self):
        try:
            raw = subprocess.check_output(
                [PING, "-n", "1", "-w", "500", config.HOTSPOT_IP],
                universal_newlines=True,
                timeout=3,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            patterns = [
                r"time[=<](\d+)ms",
                r"Average = (\d+)ms",
                r"time=(\d+\.?\d*)\s*ms"
            ]
            for pattern in patterns:
                match = re.search(pattern, raw)
                if match:
                    self.last_ping = float(match.group(1))
                    return self.last_ping
        except Exception as e:
            print(f"[PING ERROR] {e}")
        return self.last_ping

    def sample(self):
        rssi_val, pct = self.rssi()
        ping_val      = self.ping()
        return {
            "rssi"   : rssi_val,
            "percent": pct,
            "ping"   : ping_val,
            "ts"     : datetime.datetime.now()
        }
