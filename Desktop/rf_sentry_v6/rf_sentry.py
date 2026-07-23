import subprocess, threading, time, platform
from collections import deque
from datetime import datetime
import numpy as np
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Wedge
import matplotlib as mpl
mpl.rcParams["font.family"] = "Consolas"
mpl.rcParams["font.size"] = 8


class WiFiReader:
    def __init__(self):
        self.win = platform.system().lower() == "windows"
    def read(self):
        if not self.win: return None, "OS_UNSUPPORTED"
        try:
            flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"],
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="ignore", creationflags=flags)
        except Exception as e:
            return None, f"ERR:{e}"
        d = {}
        for line in out.splitlines():
            line = line.strip()
            if " : " in line:
                k, v = line.split(" : ", 1)
                d[k.strip().lower()] = v.strip()
        if "signal" not in d: return None, "NO_WIFI"
        try: pct = float(d["signal"].replace("%", "").strip())
        except: return None, "PARSE_ERR"
        return {"ssid": d.get("ssid", "?"), "signal_pct": pct,
                "dbm": (pct / 2.0) - 100.0, "channel": d.get("channel", "?")}, None


class Beeper:
    def __init__(self): self.last = 0
    def alert(self):
        now = time.time()
        if now - self.last < 1.0: return
        self.last = now
        threading.Thread(target=self._go, daemon=True).start()
    def _go(self):
        try:
            import winsound
            winsound.Beep(1600, 60); winsound.Beep(2200, 45)
        except: pass


class Engine:
    def __init__(self):
        self.baseline_mean = None; self.baseline_std = None; self.baseline_var = None
        self.ema = None; self.last_ema = None
        self.var_win = deque(maxlen=12); self.delta_win = deque(maxlen=6)
        self.consec_hits = 0; self.consec_clear = 0
        self.locked = False; self.lock_hold = 0
        self.total_events = 0; self.activity_level = 0.0
    def set_baseline(self, samples):
        arr = np.array(samples, dtype=np.float64)
        self.baseline_mean = float(np.mean(arr))
        self.baseline_std = max(0.3, float(np.std(arr)))
        self.baseline_var = float(np.var(arr))
        self.ema = self.baseline_mean; self.last_ema = self.baseline_mean
    def update(self, dbm, sens):
        if self.baseline_mean is None: return None
        self.last_ema = self.ema
        self.ema = 0.3 * dbm + 0.7 * self.ema
        z = abs(self.ema - self.baseline_mean) / self.baseline_std
        delta = abs(self.ema - self.last_ema)
        self.delta_win.append(delta)
        avg_d = float(np.mean(list(self.delta_win)))
        self.var_win.append(dbm)
        rvar = float(np.var(list(self.var_win))) if len(self.var_win) >= 6 else 0.0
        s = float(sens) / 100.0
        z_th = max(1.8, 5.0 - s * 3.0)
        d_th = max(0.8, 2.5 - s * 1.5)
        v_th = max(0.3, self.baseline_var * (4.0 - s * 2.5))
        gates = int(z >= z_th) + int(avg_d >= d_th) + int(rvar >= v_th)
        hit = gates >= 2
        if hit:
            self.consec_hits += 1; self.consec_clear = 0
        else:
            self.consec_clear += 1
            if self.consec_clear >= 3: self.consec_hits = max(0, self.consec_hits - 1)
        self.consec_hits = min(self.consec_hits, 20)
        was_locked = self.locked
        if self.consec_hits >= 3:
            self.locked = True; self.lock_hold = 10
        else:
            if self.lock_hold > 0:
                self.lock_hold -= 1
                if self.lock_hold == 0: self.locked = False
            else: self.locked = False
        if self.locked and not was_locked: self.total_events += 1
        if hit: self.activity_level = min(100, self.activity_level + 8)
        else: self.activity_level = max(0, self.activity_level - 1.5)
        c1 = min(z / z_th, 1.5); c2 = min(avg_d / d_th, 1.5); c3 = min(rvar / v_th, 1.5)
        conf = float(np.clip((c1 + c2 + c3) / 3.0, 0, 1))
        return {"conf": conf, "z": z, "z_th": z_th, "locked": self.locked,
                "events": self.total_events, "activity": self.activity_level, "rvar": rvar}


class RFSentry:
    BG="#020604"; PANEL="#060d0a"; PANEL_HI="#0a1712"
    BORDER="#0f3a26"; FG="#4dff9e"; FG_BR="#8dffbf"
    DIM="#3a6b52"; MUTED="#5a8a72"
    AMBER="#ffb84d"; RED="#ff4d5e"; CYAN="#4dd8ff"
    WHITE="#dfffe8"; DARK="#010301"

    def __init__(self, root):
        self.root = root
        self.root.title("RF-SENTRY // Operator Console")
        self.root.geometry("1500x900")
        self.root.configure(bg=self.BG)
        self.reader = WiFiReader(); self.beeper = Beeper(); self.engine = Engine()
        self.running = False; self.calibrating = False; self.tick = 0
        self.cal_buf = deque(maxlen=100)
        self.rssi_smooth = deque(maxlen=8); self.current_distance = 0.0
        self.radar_max_range = 12.0
        self.trail = deque(maxlen=250); self.trail_start = None
        self.radar_angle = 0.0
        self.wf_rows = 160; self.wf_cols = 200
        self.waterfall = np.zeros((self.wf_rows, self.wf_cols), dtype=np.float32)
        self.wf_mark = np.zeros((self.wf_rows, self.wf_cols, 4), dtype=np.float32)
        self.hm_rows = 60; self.hm_cols = 90
        self.heatmap = np.zeros((self.hm_rows, self.hm_cols), dtype=np.float32)
        self.ts_len = 280
        self.ts_rssi = deque([-70.0]*self.ts_len, maxlen=self.ts_len)
        self.ts_z = deque([0.0]*self.ts_len, maxlen=self.ts_len)
        self.ts_threat = deque([0.0]*self.ts_len, maxlen=self.ts_len)
        self.ts_var = deque([0.0]*self.ts_len, maxlen=self.ts_len)
        self.current_tab = "radar"
        self._build()
        self.root.after(200, self.loop)

    def _dist(self, rssi):
        A = -40.0; n = 2.8
        rssi = max(min(rssi, -20), -100)
        return max(0.5, min(10 ** ((A - rssi) / (10 * n)), 15.0))

    def _build(self):
        top = tk.Frame(self.root, bg=self.DARK, height=34)
        top.pack(fill=tk.X); top.pack_propagate(False)
        tk.Label(top, text=" RF-SENTRY ", bg=self.DARK, fg=self.FG_BR,
            font=("Consolas", 12, "bold")).pack(side=tk.LEFT, padx=8)
        self.top_status = tk.Label(top, text="", bg=self.DARK, fg=self.MUTED, font=("Consolas", 9))
        self.top_status.pack(side=tk.LEFT, padx=20)
        self.top_clock = tk.Label(top, text="", bg=self.DARK, fg=self.AMBER, font=("Consolas", 10, "bold"))
        self.top_clock.pack(side=tk.RIGHT, padx=14)

        tabbar = tk.Frame(self.root, bg=self.PANEL, height=36)
        tabbar.pack(fill=tk.X); tabbar.pack_propagate(False)
        self.tab_r = tk.Button(tabbar, text="  RADAR VIEW  ",
            command=lambda: self.switch("radar"), bg=self.PANEL_HI, fg=self.FG_BR,
            font=("Consolas", 10, "bold"), relief="flat", bd=0, padx=14, pady=6)
        self.tab_r.pack(side=tk.LEFT, padx=(8, 2), pady=4)
        self.tab_h = tk.Button(tabbar, text="  HEATMAP VIEW  ",
            command=lambda: self.switch("heatmap"), bg=self.PANEL, fg=self.DIM,
            font=("Consolas", 10, "bold"), relief="flat", bd=0, padx=14, pady=6)
        self.tab_h.pack(side=tk.LEFT, padx=2, pady=4)

        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = tk.Frame(body, bg=self.PANEL, width=280,
            highlightbackground=self.BORDER, highlightthickness=1)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        left.pack_propagate(False)

        tk.Label(left, text="  CONTROL", bg=self.PANEL, fg=self.FG,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X, padx=6, pady=(10, 4))
        for txt, col, cmd, hk in [("CALIBRATE", self.AMBER, self.cal, "F1"),
                                    ("START", self.FG, self.start, "F2"),
                                    ("STOP", self.RED, self.stop, "F3")]:
            b = tk.Button(left, text=f"  {txt}  [{hk}]", command=cmd,
                bg=self.PANEL_HI, fg=col, font=("Consolas", 10, "bold"),
                relief="flat", bd=0, anchor="w", padx=8, pady=6)
            b.pack(fill=tk.X, padx=10, pady=2)

        self.root.bind("<F1>", lambda e: self.cal())
        self.root.bind("<F2>", lambda e: self.start())
        self.root.bind("<F3>", lambda e: self.stop())

        tk.Label(left, text="  SENSITIVITY", bg=self.PANEL, fg=self.FG,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X, padx=6, pady=(10, 4))
        self.sens = tk.IntVar(value=50)
        ttk.Scale(left, from_=10, to=100, orient="horizontal", variable=self.sens).pack(fill=tk.X, padx=14, pady=4)

        tk.Label(left, text="  STATUS", bg=self.PANEL, fg=self.FG,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X, padx=6, pady=(10, 4))
        self.status_lbl = tk.Label(left, text="  IDLE", bg=self.PANEL_HI, fg=self.DIM,
            font=("Consolas", 15, "bold"), anchor="w", height=2)
        self.status_lbl.pack(fill=tk.X, padx=10, pady=(0, 2))
        self.status_sub = tk.Label(left, text="  press F1 to start", bg=self.PANEL,
            fg=self.MUTED, font=("Consolas", 9), anchor="w")
        self.status_sub.pack(fill=tk.X, padx=14, pady=(0, 8))

        tk.Label(left, text="  ACTIVITY", bg=self.PANEL, fg=self.FG,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X, padx=6, pady=(10, 4))
        self.act_val = tk.Label(left, text="  0%", bg=self.PANEL, fg=self.DIM,
            font=("Consolas", 20, "bold"), anchor="w")
        self.act_val.pack(fill=tk.X, padx=14)
        self.act_word = tk.Label(left, text="  quiet", bg=self.PANEL, fg=self.FG_BR,
            font=("Consolas", 10), anchor="w")
        self.act_word.pack(fill=tk.X, padx=14, pady=(0, 8))

        tk.Label(left, text="  EVENTS", bg=self.PANEL, fg=self.FG,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X, padx=6, pady=(10, 4))
        self.ev_val = tk.Label(left, text="  0", bg=self.PANEL, fg=self.RED,
            font=("Consolas", 20, "bold"), anchor="w")
        self.ev_val.pack(fill=tk.X, padx=14, pady=(0, 8))

        self.dist_lbl = tk.Label(left, text="  distance :  -- m", bg=self.PANEL,
            fg=self.WHITE, font=("Consolas", 9), anchor="w")
        self.dist_lbl.pack(fill=tk.X, padx=14)
        self.tele = tk.Label(left, text="", bg=self.PANEL, fg=self.WHITE,
            font=("Consolas", 9), anchor="nw", justify="left")
        self.tele.pack(fill=tk.BOTH, padx=14, pady=8)

        self.tab_ct = tk.Frame(body, bg=self.BG)
        self.tab_ct.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.rad_tab = tk.Frame(self.tab_ct, bg=self.BG)
        self.heat_tab = tk.Frame(self.tab_ct, bg=self.BG)
        self._build_radar(self.rad_tab)
        self._build_heat(self.heat_tab)
        self.rad_tab.pack(fill=tk.BOTH, expand=True)

    def _build_radar(self, parent):
        ch = tk.Frame(parent, bg=self.BG); ch.pack(fill=tk.BOTH, expand=True)
        lc = tk.Frame(ch, bg=self.BG); lc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        rf = tk.Frame(lc, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
        rf.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        tk.Label(rf, text=" RADAR VIEW ", bg=self.PANEL_HI, fg=self.FG_BR,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.fig_r = Figure(figsize=(5, 4), dpi=100, facecolor=self.PANEL)
        self.ax_r = self.fig_r.add_subplot(111)
        self.ax_r.set_facecolor("#020806")
        self.ax_r.set_xlim(-12, 12); self.ax_r.set_ylim(-12, 12)
        self.ax_r.set_aspect("equal")
        self.ax_r.set_xticks([]); self.ax_r.set_yticks([])
        for s in self.ax_r.spines.values():
            s.set_color(self.BORDER); s.set_linewidth(0.8)
        for i in range(3):
            r = 12 * (i+1) / 3
            self.ax_r.add_patch(Circle((0, 0), r, fill=False,
                edgecolor=self.BORDER, linewidth=0.6, linestyle="--", alpha=0.5))
        self.ax_r.plot([0], [0], marker="^", markersize=15, color=self.FG, zorder=5)
        self.ax_r.text(0, -1.2, "ROUTER", color=self.FG, fontsize=7, ha="center", weight="bold")
        self.sweep = Wedge((0, 0), 12, 0, 30, facecolor=self.FG, alpha=0.10, edgecolor="none")
        self.ax_r.add_patch(self.sweep)
        self.det_dot, = self.ax_r.plot([0], [0], "o", color=self.RED, markersize=18,
            markeredgecolor="#ffffff", markeredgewidth=2, zorder=10, alpha=0)
        self.det_ring = Circle((0, 0), 0, fill=False, edgecolor=self.RED, linewidth=2, alpha=0, zorder=9)
        self.ax_r.add_patch(self.det_ring)
        self.det_lbl = self.ax_r.text(0, 0, "", color=self.RED, fontsize=10, weight="bold", zorder=11)
        self.idle_txt = self.ax_r.text(0, 10, "IDLE", color=self.DIM, fontsize=10,
            weight="bold", ha="center", alpha=0.7)
        self.fig_r.tight_layout(pad=0.5)
        self.canvas_r = FigureCanvasTkAgg(self.fig_r, master=rf)
        self.canvas_r.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        tf = tk.Frame(lc, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
        tf.pack(fill=tk.BOTH, expand=True)
        tk.Label(tf, text=" MOVEMENT TRAIL ", bg=self.PANEL_HI, fg=self.FG_BR,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.fig_t = Figure(figsize=(5, 2.5), dpi=100, facecolor=self.PANEL)
        self.ax_t = self.fig_t.add_subplot(111)
        self._sa(self.ax_t, "distance (m)", "seconds ago")
        self.ax_t.set_xlim(0, 15); self.ax_t.set_ylim(60, 0)
        self.tlc = LineCollection([], linewidths=3, cmap="Reds", norm=mpl.colors.Normalize(0, 1))
        self.ax_t.add_collection(self.tlc)
        self.tdot, = self.ax_t.plot([], [], "o", color=self.RED, markersize=13,
            markeredgecolor="#ffffff", markeredgewidth=1.5, zorder=10)
        self.fig_t.tight_layout(pad=0.5)
        self.canvas_t = FigureCanvasTkAgg(self.fig_t, master=tf)
        self.canvas_t.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        rc = tk.Frame(ch, bg=self.BG); rc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        wf = tk.Frame(rc, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
        wf.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        tk.Label(wf, text=" WATERFALL ", bg=self.PANEL_HI, fg=self.FG_BR,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.fig_w = Figure(figsize=(5, 2.5), dpi=100, facecolor=self.PANEL)
        self.ax_w = self.fig_w.add_subplot(111)
        self._sa(self.ax_w, "spread", "time")
        self.im_w = self.ax_w.imshow(self.waterfall, cmap="inferno", vmin=0, vmax=1,
            aspect="auto", interpolation="bilinear")
        self.im_wm = self.ax_w.imshow(self.wf_mark, aspect="auto", interpolation="bilinear")
        self.fig_w.tight_layout(pad=0.5)
        self.canvas_w = FigureCanvasTkAgg(self.fig_w, master=wf)
        self.canvas_w.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        sf = tk.Frame(rc, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
        sf.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        tk.Label(sf, text=" SIGNAL ", bg=self.PANEL_HI, fg=self.FG_BR,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.fig_s = Figure(figsize=(5, 1.6), dpi=100, facecolor=self.PANEL)
        self.ax_s = self.fig_s.add_subplot(111)
        self._sa(self.ax_s, "time", "dBm")
        self.ln_s, = self.ax_s.plot(range(self.ts_len), list(self.ts_rssi), color=self.FG, linewidth=1.4)
        self.bln = self.ax_s.axhline(-70, color=self.AMBER, linewidth=0.8, linestyle="--", alpha=0.7)
        self.ax_s.set_ylim(-95, -30); self.ax_s.set_xlim(0, self.ts_len)
        self.fig_s.tight_layout(pad=0.5)
        self.canvas_s = FigureCanvasTkAgg(self.fig_s, master=sf)
        self.canvas_s.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        zf = tk.Frame(rc, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
        zf.pack(fill=tk.BOTH, expand=True)
        tk.Label(zf, text=" SCORE ", bg=self.PANEL_HI, fg=self.FG_BR,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.fig_z = Figure(figsize=(5, 1.6), dpi=100, facecolor=self.PANEL)
        self.ax_z = self.fig_z.add_subplot(111)
        self._sa(self.ax_z, "time", "z")
        self.ln_z, = self.ax_z.plot(range(self.ts_len), list(self.ts_z), color=self.CYAN, linewidth=1.4)
        self.thln = self.ax_z.axhline(3.0, color=self.RED, linewidth=0.9, linestyle="--", alpha=0.8)
        self.ax_z.set_ylim(0, 8); self.ax_z.set_xlim(0, self.ts_len)
        self.fig_z.tight_layout(pad=0.5)
        self.canvas_z = FigureCanvasTkAgg(self.fig_z, master=zf)
        self.canvas_z.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _build_heat(self, parent):
        ch = tk.Frame(parent, bg=self.BG); ch.pack(fill=tk.BOTH, expand=True)
        hf = tk.Frame(ch, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
        hf.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        tk.Label(hf, text=" RF THERMAL HEATMAP ", bg=self.PANEL_HI, fg=self.FG_BR,
            font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.fig_h = Figure(figsize=(8, 4), dpi=100, facecolor=self.PANEL)
        self.ax_h = self.fig_h.add_subplot(111)
        self.ax_h.set_facecolor("#000000")
        self.ax_h.set_xticks([]); self.ax_h.set_yticks([])
        for s in self.ax_h.spines.values():
            s.set_color(self.BORDER); s.set_linewidth(0.8)
        self.im_h = self.ax_h.imshow(self.heatmap, cmap="turbo", vmin=0, vmax=1,
            aspect="auto", interpolation="bilinear")
        self.h_st = self.ax_h.text(2, 58, "IDLE", color=self.DIM, fontsize=10, weight="bold")
        self.fig_h.tight_layout(pad=0.4)
        self.canvas_h = FigureCanvasTkAgg(self.fig_h, master=hf)
        self.canvas_h.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        bt = tk.Frame(ch, bg=self.BG); bt.pack(fill=tk.BOTH, expand=True)
        for title, key, color, ylim in [("LIVE RSSI", "rssi", self.FG, (-95, -30)),
                                          ("NOISE", "var", self.CYAN, (0, 6)),
                                          ("THREAT", "thr", self.RED, (0, 5))]:
            f = tk.Frame(bt, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
            f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            tk.Label(f, text=f" {title} ", bg=self.PANEL_HI, fg=self.FG_BR,
                font=("Consolas", 9, "bold"), anchor="w").pack(fill=tk.X)
            fig = Figure(figsize=(3, 2), dpi=100, facecolor=self.PANEL)
            ax = fig.add_subplot(111)
            self._sa(ax, "", "")
            if key == "rssi": data = self.ts_rssi
            elif key == "var": data = self.ts_var
            else: data = self.ts_threat
            ln, = ax.plot(range(self.ts_len), list(data), color=color, linewidth=1.6)
            ax.set_ylim(*ylim); ax.set_xlim(0, self.ts_len)
            fig.tight_layout(pad=0.4)
            cv = FigureCanvasTkAgg(fig, master=f)
            cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            setattr(self, f"ln_h_{key}", ln)
            setattr(self, f"ax_h_{key}", ax)
            setattr(self, f"canvas_h_{key}", cv)

    def _sa(self, ax, xl, yl):
        ax.set_facecolor("#020806")
        for s in ax.spines.values():
            s.set_color(self.BORDER); s.set_linewidth(0.8)
        ax.tick_params(colors=self.DIM, labelsize=7)
        ax.grid(True, color=self.BORDER, alpha=0.35, linewidth=0.4)
        ax.set_xlabel(xl, color=self.MUTED, fontsize=7)
        ax.set_ylabel(yl, color=self.MUTED, fontsize=7)

    def switch(self, tab):
        if tab == self.current_tab: return
        self.current_tab = tab
        if tab == "radar":
            self.heat_tab.pack_forget()
            self.rad_tab.pack(fill=tk.BOTH, expand=True)
            self.tab_r.configure(bg=self.PANEL_HI, fg=self.FG_BR)
            self.tab_h.configure(bg=self.PANEL, fg=self.DIM)
        else:
            self.rad_tab.pack_forget()
            self.heat_tab.pack(fill=tk.BOTH, expand=True)
            self.tab_h.configure(bg=self.PANEL_HI, fg=self.FG_BR)
            self.tab_r.configure(bg=self.PANEL, fg=self.DIM)

    def cal(self):
        self.cal_buf.clear(); self.calibrating = True; self.running = False
        self.engine = Engine()

    def start(self):
        if self.engine.baseline_mean is None: return
        self.running = True; self.trail.clear(); self.trail_start = time.time()

    def stop(self):
        self.running = False

    def loop(self):
        self.top_clock.configure(text=datetime.now().strftime("%H:%M:%S"))
        mode = "idle"
        if self.calibrating: mode = "calibrating"
        elif self.engine.locked: mode = "MOVEMENT"
        elif self.running: mode = "watching"
        sample, err = self.reader.read()
        iface = sample["ssid"] if sample else (err or "no wifi")
        self.top_status.configure(text=f"mode: {mode}  |  {iface[:24]}  |  {self.current_tab}")
        if sample: self._proc(sample)
        else: self.tele.configure(text=f"  no wifi\n  {err}")
        self.radar_angle = (self.radar_angle + 6) % 360
        self.sweep.set_theta1(self.radar_angle)
        self.sweep.set_theta2(self.radar_angle + 30)
        self.waterfall *= 0.985
        self.wf_mark[...,3] *= 0.94; self.wf_mark[...,0] *= 0.96
        self.heatmap *= 0.94
        shimmer = np.random.rand(self.hm_rows, self.hm_cols).astype(np.float32) * 0.03
        self.heatmap = np.maximum(self.heatmap, shimmer)
        if self.current_tab == "radar": self._render_r()
        else: self._render_h()
        self.tick += 1
        self.root.after(220, self.loop)

    def _proc(self, s):
        dbm = s["dbm"]; self.rssi_smooth.append(dbm)
        if self.calibrating:
            self.cal_buf.append(dbm)
            n = len(self.cal_buf); pct = min(100, int(n/60*100))
            self.status_lbl.configure(text=f"  LEARN {pct}%", fg=self.AMBER)
            self.status_sub.configure(text="  stay still")
            if n >= 60:
                self.engine.set_baseline(list(self.cal_buf))
                self.calibrating = False
                self.bln.set_ydata([self.engine.baseline_mean]*2)
                self.status_lbl.configure(text="  READY", fg=self.FG_BR)
                self.status_sub.configure(text="  press START (F2)")
            return
        det = self.engine.update(dbm, self.sens.get())
        if det is None: return
        sm = float(np.mean(list(self.rssi_smooth)))
        self.current_distance = self._dist(sm)
        if self.running and self.trail_start:
            t_sec = time.time() - self.trail_start
            self.trail.append((t_sec, self.current_distance, det["conf"], det["locked"]))
        if det["locked"]:
            self.status_lbl.configure(text="  MOVEMENT!", fg=self.RED)
            self.status_sub.configure(text=f"  ~{self.current_distance:.1f}m away")
            self.beeper.alert()
        elif self.running:
            self.status_lbl.configure(text="  CLEAR", fg=self.FG_BR)
            self.status_sub.configure(text="  no movement")
        act = int(det["activity"])
        if act >= 70: aw, ac = "VERY ACTIVE", self.RED
        elif act >= 40: aw, ac = "active", self.AMBER
        elif act >= 15: aw, ac = "slight", self.FG
        else: aw, ac = "quiet", self.DIM
        self.act_val.configure(text=f"  {act}%", fg=ac)
        self.act_word.configure(text=f"  {aw}", fg=ac)
        self.ev_val.configure(text=f"  {det['events']}")
        self.dist_lbl.configure(text=f"  distance :  {self.current_distance:.1f} m")
        base = f"{self.engine.baseline_mean:.1f}" if self.engine.baseline_mean else "--"
        self.tele.configure(text=f"  net    {s['ssid']}\n  sig    {int(s['signal_pct'])}%\n  dBm    {dbm:.1f}\n  base   {base}")
        self.ts_rssi.append(dbm); self.ts_z.append(det["z"])
        self.ts_var.append(det["rvar"])
        self.ts_threat.append(min(5.0, det["conf"] * 5.0))
        self.thln.set_ydata([det["z_th"]]*2)
        self._pwf(dbm, det["conf"], det["locked"])
        self._phm(dbm, det["conf"], det["activity"])

    def _pwf(self, dbm, conf, locked):
        self.waterfall[1:] = self.waterfall[:-1]
        self.wf_mark[1:] = self.wf_mark[:-1]
        row = np.random.rand(self.wf_cols).astype(np.float32) * 0.04
        pos = int(np.clip((dbm + 95) / 65.0 * self.wf_cols, 0, self.wf_cols-1))
        w = 4 + int(conf * 18); ph = 0.3 + conf * 0.7
        x = np.arange(self.wf_cols)
        row = np.maximum(row, ph * np.exp(-((x-pos)**2)/(2*w**2)))
        self.waterfall[0] = row
        mrow = np.zeros((self.wf_cols, 4), dtype=np.float32)
        if locked:
            hw = 8 + int(conf * 22)
            g = np.exp(-((x-pos)**2)/(2*hw**2)) * min(1.0, conf)
            mrow[:,0] = g; mrow[:,3] = g * 0.9
        self.wf_mark[0] = mrow

    def _phm(self, dbm, conf, activity):
        if self.engine.baseline_mean is not None:
            rel = np.clip((dbm - self.engine.baseline_mean) / max(1, self.engine.baseline_std * 3), -1.0, 1.0)
        else: rel = 0.0
        cy = int(np.clip(self.hm_rows / 2 + rel * self.hm_rows / 3, 8, self.hm_rows - 8))
        num = 3 + int(activity / 20)
        yy, xx = np.ogrid[:self.hm_rows, :self.hm_cols]
        for _ in range(num):
            px = np.random.randint(0, self.hm_cols)
            py = int(np.clip(cy + np.random.randint(-12, 12), 0, self.hm_rows - 1))
            radius = 4 + activity / 20 + np.random.uniform(0, 4)
            power = 0.2 + conf * 0.7
            blob = power * np.exp(-((yy - py)**2 + (xx - px)**2) / (2 * radius**2))
            self.heatmap = np.maximum(self.heatmap, blob.astype(np.float32))
        np.clip(self.heatmap, 0, 1, out=self.heatmap)

    def _render_r(self):
        self.im_w.set_data(self.waterfall); self.im_wm.set_data(self.wf_mark)
        self.canvas_w.draw_idle()
        self.ln_s.set_ydata(list(self.ts_rssi))
        arr = np.array(self.ts_rssi); lo, hi = arr.min()-2, arr.max()+2
        if hi-lo < 6: hi = lo + 6
        self.ax_s.set_ylim(lo, hi); self.canvas_s.draw_idle()
        self.ln_z.set_ydata(list(self.ts_z))
        self.ax_z.set_ylim(0, max(6, max(self.ts_z) * 1.2))
        self.canvas_z.draw_idle()
        if self.running and self.engine.baseline_mean is not None:
            if self.engine.locked or self.engine.activity_level > 10:
                dy = -min(self.current_distance, 11)
                self.det_dot.set_data([0], [dy])
                self.det_dot.set_alpha(min(1.0, 0.5 + self.engine.activity_level / 200))
                pulse = (self.tick % 20) / 20
                self.det_ring.set_radius(0.4 + pulse * 1.8)
                self.det_ring.set_alpha(max(0, 1 - pulse) * 0.7)
                self.det_ring.center = (0, dy)
                self.det_lbl.set_position((0.4, dy + 0.4))
                self.det_lbl.set_text(f"{self.current_distance:.1f}m")
                self.det_lbl.set_color(self.RED if self.engine.locked else self.AMBER)
                self.idle_txt.set_alpha(0)
            else:
                self.idle_txt.set_alpha(0.6); self.idle_txt.set_text("SCANNING")
                cur = self.det_dot.get_alpha() or 0
                self.det_dot.set_alpha(max(0, cur - 0.1))
        else:
            self.det_dot.set_alpha(0); self.det_ring.set_alpha(0)
            self.det_lbl.set_text(""); self.idle_txt.set_alpha(0.6)
            self.idle_txt.set_text("IDLE")
        self.canvas_r.draw_idle()
        if len(self.trail) >= 2:
            data = list(self.trail); now_t = data[-1][0]
            points = [(d[1], now_t - d[0]) for d in data]
            confs = [d[2] for d in data]
            pts = np.array(points)
            segs = [[pts[i], pts[i+1]] for i in range(len(pts) - 1)]
            cols = confs[1:]
            if segs:
                self.tlc.set_segments(segs)
                self.tlc.set_array(np.array(cols))
                self.tlc.set_linewidth(np.array([1 + c * 3.5 for c in cols]))
                self.tlc.set_clim(0, 1)
            self.tdot.set_data([pts[-1][0]], [pts[-1][1]])
            self.ax_t.set_xlim(0, min(20, max(8, max(p[0] for p in points) + 2)))
        self.canvas_t.draw_idle()

    def _render_h(self):
        self.im_h.set_data(self.heatmap)
        if self.engine.locked:
            self.h_st.set_text("MOVEMENT DETECTED"); self.h_st.set_color(self.RED)
        elif self.running:
            self.h_st.set_text("SCANNING"); self.h_st.set_color(self.FG_BR)
        else:
            self.h_st.set_text("IDLE"); self.h_st.set_color(self.DIM)
        self.canvas_h.draw_idle()
        self.ln_h_rssi.set_ydata(list(self.ts_rssi))
        arr = np.array(self.ts_rssi); lo, hi = arr.min()-2, arr.max()+2
        if hi-lo < 6: hi = lo + 6
        self.ax_h_rssi.set_ylim(lo, hi); self.canvas_h_rssi.draw_idle()
        self.ln_h_var.set_ydata(list(self.ts_var))
        self.ax_h_var.set_ylim(0, max(4, max(self.ts_var) * 1.2))
        self.canvas_h_var.draw_idle()
        self.ln_h_thr.set_ydata(list(self.ts_threat))
        self.canvas_h_thr.draw_idle()


def main():
    root = tk.Tk()
    RFSentry(root)
    root.mainloop()

if __name__ == "__main__":
    main()
