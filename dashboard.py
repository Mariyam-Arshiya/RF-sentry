import tkinter as tk
from tkinter import ttk, messagebox
import threading
import datetime
import time

import config
from collector import WiFiCollector
from engine    import DetectionEngine
from logger    import DataLogger
from plots     import PlotPanel


COLORS = {
    'bg'    : '#0a0a0a',
    'panel' : '#111111',
    'green' : '#00FF66',
    'blue'  : '#4488FF',
    'orange': '#FFA500',
    'red'   : '#FF3333',
    'dim'   : '#555555',
    'mid'   : '#888888',
}

STATUS_MAP = {
    'SECURE': {
        'text': 'SECURE\nNo Activity',
        'bg'  : '#001a00',
        'fg'  : '#00FF66'
    },
    'MINOR_MOVEMENT': {
        'text': 'MINOR\nMovement',
        'bg'  : '#1a1400',
        'fg'  : '#FFA500'
    },
    'INTRUSION': {
        'text': 'INTRUSION\nDETECTED',
        'bg'  : '#1a0000',
        'fg'  : '#FF3333'
    },
    'CALIBRATING': {
        'text': 'CALIBRATING\nWait...',
        'bg'  : '#001429',
        'fg'  : '#4488FF'
    },
}


class Dashboard:
    def __init__(self, root):
        self.root          = root
        self.root.title(f"{config.APP_NAME}  {config.VERSION}")
        self.root.geometry('1200x750')
        self.root.configure(bg=COLORS['bg'])

        self.collector     = WiFiCollector()
        self.engine        = DetectionEngine()
        self.logger        = DataLogger()

        self.running       = False
        self.calibrating   = False
        self.calib_buf     = []
        self.alert_count   = 0
        self.sample_count  = 0
        self.session_start = None

        self._build_header()
        self._build_body()
        self._tick_clock()

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build_header(self):
        bar = tk.Frame(self.root, bg='#001a00', height=55)
        bar.pack(fill='x')
        bar.pack_propagate(False)

        tk.Label(
            bar,
            text='RF-SENTRY PRO',
            font=('Courier New', 20, 'bold'),
            bg='#001a00', fg=COLORS['green']
        ).pack(side='left', padx=18, pady=8)

        tk.Label(
            bar,
            text='WiFi-Based Human Presence Detection  |  Statistical Anomaly Engine',
            font=('Arial', 10),
            bg='#001a00', fg=COLORS['dim']
        ).pack(side='left', padx=4)

        self.clock = tk.Label(
            bar, text='',
            font=('Courier New', 11),
            bg='#001a00', fg=COLORS['green']
        )
        self.clock.pack(side='right', padx=18)

    def _build_body(self):
        body = tk.Frame(self.root, bg=COLORS['bg'])
        body.pack(fill='both', expand=True)

        left = tk.Frame(body, bg=COLORS['panel'], width=275)
        left.pack(side='left', fill='y', padx=(8, 4), pady=8)
        left.pack_propagate(False)

        right = tk.Frame(body, bg=COLORS['bg'])
        right.pack(side='right', fill='both', expand=True, padx=(4, 8), pady=8)

        self._build_controls(left)
        self._build_metrics(left)
        self.plots = PlotPanel(right)

    def _build_controls(self, p):
        self._section(p, 'CONTROLS')

        self._lbl(p, 'Hotspot Gateway IP')
        self.ip_var = tk.StringVar(value=config.HOTSPOT_IP)
        tk.Entry(
            p, textvariable=self.ip_var,
            font=('Courier New', 11),
            bg='#1a1a1a', fg=COLORS['green'],
            insertbackground=COLORS['green'],
            relief='flat', bd=4
        ).pack(fill='x', padx=12, pady=(2, 8))

        self.calib_btn = self._btn(p, 'CALIBRATE BASELINE', COLORS['orange'], '#000000', self._start_calibration)

        self.calib_bar = ttk.Progressbar(p, orient='horizontal', mode='determinate', maximum=100)
        self.calib_bar.pack(fill='x', padx=12, pady=2)

        self.calib_lbl = tk.Label(
            p, text='Not calibrated',
            font=('Arial', 8),
            bg=COLORS['panel'], fg=COLORS['mid']
        )
        self.calib_lbl.pack(anchor='w', padx=12)

        self._sep(p)

        self.start_btn = self._btn(p, 'START MONITORING', COLORS['green'], '#000000', self._start)
        self.stop_btn  = self._btn(p, 'STOP',             COLORS['red'],   '#ffffff', self._stop, state='disabled')

        self._sep(p)

        self._lbl(p, 'Detection Sensitivity')
        self.sens = tk.DoubleVar(value=config.THRESHOLD_HIGH)
        tk.Scale(
            p,
            from_=1.0, to=8.0, resolution=0.1,
            orient='horizontal', variable=self.sens,
            bg=COLORS['panel'], fg='#ffffff',
            troughcolor='#2a2a2a',
            highlightthickness=0,
            font=('Arial', 8),
            command=lambda v: self.plots.update_threshold(float(v))
        ).pack(fill='x', padx=12, pady=2)

        row = tk.Frame(p, bg=COLORS['panel'])
        row.pack(fill='x', padx=12)
        tk.Label(row, text='Sensitive', font=('Arial', 7), bg=COLORS['panel'], fg=COLORS['red']).pack(side='left')
        tk.Label(row, text='Tolerant',  font=('Arial', 7), bg=COLORS['panel'], fg=COLORS['green']).pack(side='right')

        self._sep(p)

        self.status_box = tk.Label(
            p, text='INACTIVE',
            font=('Courier New', 13, 'bold'),
            bg='#1a1a1a', fg=COLORS['dim'],
            height=3, width=18,
            relief='ridge', bd=2
        )
        self.status_box.pack(pady=8, padx=12)

        self._lbl(p, 'Confidence')
        self.conf_bar = ttk.Progressbar(p, orient='horizontal', mode='determinate', maximum=100)
        self.conf_bar.pack(fill='x', padx=12, pady=2)

        self.conf_lbl = tk.Label(
            p, text='0%',
            font=('Courier New', 10, 'bold'),
            bg=COLORS['panel'], fg=COLORS['green']
        )
        self.conf_lbl.pack()

        self._sep(p)

        self._btn(p, 'Export CSV', '#2a2a2a', '#ffffff', self.logger.open_file)

    def _build_metrics(self, p):
        self._sep(p)
        self._section(p, 'LIVE METRICS')

        frame = tk.Frame(p, bg='#0d1a0d', relief='groove', bd=1)
        frame.pack(fill='x', padx=12, pady=4)

        rows = [
            ('RSSI',       'rssi'),
            ('Signal %',   'pct'),
            ('Ping',       'ping'),
            ('Std Dev s',  'std'),
            ('Score',      'score'),
            ('Drift',      'drift'),
            ('Baseline',   'base'),
            ('Alerts',     'alerts'),
            ('Samples',    'samples'),
            ('Session',    'session'),
        ]

        self.m = {}
        for label, key in rows:
            r = tk.Frame(frame, bg='#0d1a0d')
            r.pack(fill='x', padx=8, pady=1)
            tk.Label(
                r, text=label,
                font=('Courier New', 8),
                bg='#0d1a0d', fg=COLORS['dim'],
                width=10, anchor='w'
            ).pack(side='left')
            lbl = tk.Label(
                r, text='--',
                font=('Courier New', 8, 'bold'),
                bg='#0d1a0d', fg=COLORS['green'],
                anchor='e'
            )
            lbl.pack(side='right')
            self.m[key] = lbl

    def _start_calibration(self):
        if self.running:
            messagebox.showwarning('RF-Sentry', 'Stop monitoring before calibrating.')
            return
        self.calibrating = True
        self.calib_buf   = []
        self.calib_btn.config(state='disabled', text='Calibrating...')
        threading.Thread(target=self._calib_loop, daemon=True).start()

    def _calib_loop(self):
        steps = config.CALIBRATION_SECS * 2
        for i in range(steps):
            rssi, _ = self.collector.rssi()
            self.calib_buf.append(rssi)
            pct = int(((i + 1) / steps) * 100)
            self.calib_bar['value'] = pct
            self.calib_lbl.config(
                text=f'Calibrating {pct}%  keep room still',
                fg=COLORS['orange']
            )
            time.sleep(0.5)

        mean, std = self.engine.calibrate(self.calib_buf)
        self.calibrating = False
        self.calib_btn.config(state='normal', text='RE-CALIBRATE')
        self.calib_lbl.config(
            text=f'Baseline {mean:.1f} dBm  s={std:.3f}',
            fg=COLORS['green']
        )
        self.m['base'].config(text=f'{mean:.1f} dBm')

    def _start(self):
        if not self.engine.calibrated:
            go = messagebox.askyesno(
                'RF-Sentry',
                'Not calibrated. Accuracy will be lower.\nContinue anyway?'
            )
            if not go:
                return

        config.HOTSPOT_IP         = self.ip_var.get()
        self.collector.hotspot_ip = config.HOTSPOT_IP
        self.running              = True
        self.session_start        = datetime.datetime.now()
        self.sample_count         = 0
        self.alert_count          = 0

        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.calib_btn.config(state='disabled')
        self.status_box.config(text='STARTING...', bg='#001429', fg=COLORS['blue'])

        threading.Thread(target=self._loop, daemon=True).start()

    def _stop(self):
        self.running = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.calib_btn.config(state='normal')
        self.status_box.config(text='STOPPED', bg='#1a0000', fg=COLORS['red'])

    def _loop(self):
        while self.running:
            try:
                data  = self.collector.sample()
                rssi  = data['rssi']
                pct   = data['percent']
                ping  = data['ping']
                ts    = data['ts']

                self.engine.push(rssi, ping)
                level, conf, stats = self.engine.analyze()

                config.THRESHOLD_HIGH = self.sens.get()
                elapsed = (ts - self.session_start).total_seconds()

                self.plots.push(
                    elapsed, rssi, ping,
                    stats.get('score', 0),
                    self.engine.baseline_mean
                )

                self.logger.write(
                    ts, rssi, pct, ping,
                    stats.get('rssi_std', 0),
                    stats.get('score', 0),
                    level, conf
                )

                self.sample_count += 1
                if level == 'INTRUSION':
                    self.alert_count += 1

                self.root.after(0, self._refresh, rssi, pct, ping, level, conf, stats)

            except Exception:
                pass

            time.sleep(config.SAMPLE_RATE)

    def _refresh(self, rssi, pct, ping, level, conf, stats):
        cfg = STATUS_MAP.get(level, STATUS_MAP['CALIBRATING'])
        self.status_box.config(text=cfg['text'], bg=cfg['bg'], fg=cfg['fg'])

        self.conf_bar['value'] = conf
        self.conf_lbl.config(
            text=f'{conf}%',
            fg=COLORS['red'] if conf > 70 else COLORS['orange'] if conf > 40 else COLORS['green']
        )

        dur = '--'
        if self.session_start:
            secs   = int((datetime.datetime.now() - self.session_start).total_seconds())
            m, s   = divmod(secs, 60)
            dur    = f'{m:02d}:{s:02d}'

        self.m['rssi'].config(text=f"{rssi:.1f} dBm")
        self.m['pct'].config(text=f"{pct}%")
        self.m['ping'].config(text=f"{ping:.0f} ms")
        self.m['std'].config(text=f"{stats.get('rssi_std', 0):.4f}")
        self.m['score'].config(text=f"{stats.get('score', 0):.4f}")
        self.m['drift'].config(text=f"{stats.get('drift', 0):.2f}")
        self.m['alerts'].config(
            text=str(self.alert_count),
            fg=COLORS['red'] if self.alert_count else COLORS['green']
        )
        self.m['samples'].config(text=str(self.sample_count))
        self.m['session'].config(text=dur)

    def _tick_clock(self):
        self.clock.config(text=datetime.datetime.now().strftime('%Y-%m-%d   %H:%M:%S'))
        self.root.after(1000, self._tick_clock)

    def _on_close(self):
        self.running = False
        time.sleep(0.3)
        self.root.destroy()

    def _sep(self, p):
        ttk.Separator(p, orient='horizontal').pack(fill='x', padx=10, pady=5)

    def _section(self, p, text):
        tk.Label(
            p, text=text,
            font=('Courier New', 10, 'bold'),
            bg=COLORS['panel'], fg=COLORS['green']
        ).pack(pady=(6, 2))

    def _lbl(self, p, text):
        tk.Label(
            p, text=text,
            font=('Arial', 8),
            bg=COLORS['panel'], fg=COLORS['mid']
        ).pack(anchor='w', padx=12, pady=(4, 0))

    def _btn(self, p, text, bg, fg, cmd, state='normal'):
        b = tk.Button(
            p, text=text,
            font=('Arial', 10, 'bold'),
            bg=bg, fg=fg,
            activebackground=bg,
            relief='flat',
            cursor='hand2',
            command=cmd,
            state=state,
            height=2
        )
        b.pack(fill='x', padx=12, pady=3)
        return b

