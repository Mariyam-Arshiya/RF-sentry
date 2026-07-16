import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import numpy as np
import config

class PlotPanel:
    def __init__(self, parent):
        self.rssi_buf = deque(maxlen=config.PLOT_BUFFER)
        self.ping_buf = deque(maxlen=config.PLOT_BUFFER)
        self.score_buf = deque(maxlen=config.PLOT_BUFFER)
        self.time_buf = deque(maxlen=config.PLOT_BUFFER)
        self.heat_rows = []
        self.max_heat_rows = 40
        self._build(parent)

    def _build(self, parent):
        plt.style.use("dark_background")
        self.fig = plt.Figure(figsize=(9, 7), facecolor="#0a0a0a")
        self.fig.subplots_adjust(hspace=0.55, left=0.08, right=0.97, top=0.92, bottom=0.06)

        # RSSI Line
        self.ax_rssi = self._make_axis(411, "Live RSSI Signal  (dBm)", "#00FF66")
        self.ln_rssi, = self.ax_rssi.plot([], [], color="#00FF66", lw=1.5, label="RSSI")
        self.ln_base, = self.ax_rssi.plot([], [], color="#FFA500", lw=1.0, ls="--", label="Baseline")
        self.ax_rssi.legend(loc="upper right", fontsize=7, facecolor="#111111", edgecolor="#333333")

        # Ping Line
        self.ax_ping = self._make_axis(412, "Ping Latency  (ms)", "#4488FF")
        self.ln_ping, = self.ax_ping.plot([], [], color="#4488FF", lw=1.5)

        # Score Line
        self.ax_score = self._make_axis(413, "Anomaly Score", "#FF4444")
        self.ln_score, = self.ax_score.plot([], [], color="#FF4444", lw=1.5)
        self.thresh_ln = self.ax_score.axhline(y=config.THRESHOLD_HIGH, color="#FFA500", lw=1.0, ls="--")
        self.ax_score.legend(["Score", f"Threshold"], loc="upper right", fontsize=7, facecolor="#111111", edgecolor="#333333")

        # HEATMAP
        self.ax_heat = self.fig.add_subplot(414)
        self.ax_heat.set_facecolor("#050505")
        self.ax_heat.set_title("RF Interference Heatmap  (Time vs Metrics)", color="#FF4444", fontsize=9, pad=4)
        self.ax_heat.set_ylabel("Metric Layer", color="#888888", fontsize=7)
        self.ax_heat.set_xlabel("Recent Samples", color="#888888", fontsize=7)
        self.ax_heat.tick_params(colors="#555555", labelsize=6)
        for spine in self.ax_heat.spines.values():
            spine.set_color("#333333")

        empty_data = np.zeros((3, 20))
        self.heat_img = self.ax_heat.imshow(empty_data, aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=5, interpolation="nearest")
        cb = self.fig.colorbar(self.heat_img, ax=self.ax_heat, fraction=0.046, pad=0.04)
        cb.set_ticks([0, 2.5, 5])
        cb.set_ticklabels(["Safe", "Minor", "Intrusion"])
        cb.ax.tick_params(colors="#AAAAAA", labelsize=7)

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _make_axis(self, pos, title, color):
        ax = self.fig.add_subplot(pos)
        ax.set_facecolor("#0d0d0d")
        ax.set_title(title, color=color, fontsize=9, pad=4)
        ax.tick_params(colors="#555555", labelsize=7)
        ax.grid(True, color="#1c1c1c", lw=0.5)
        for spine in ax.spines.values():
            spine.set_color("#2a2a2a")
        return ax

    def push(self, t, rssi, ping, score, baseline=None, stats=None):
        self.time_buf.append(t)
        self.rssi_buf.append(rssi)
        self.ping_buf.append(ping)
        self.score_buf.append(score)

        times = list(self.time_buf)
        rssies = list(self.rssi_buf)
        pings = list(self.ping_buf)
        scores = list(self.score_buf)

        if len(times) < 2:
            return

        t_min, t_max = min(times), max(times) + 1

        self.ln_rssi.set_data(times, rssies)
        self.ax_rssi.set_xlim(t_min, t_max)
        self.ax_rssi.set_ylim(min(rssies) - 5, max(rssies) + 5)
        if baseline is not None:
            self.ln_base.set_data(times, [baseline] * len(times))

        self.ln_ping.set_data(times, pings)
        self.ax_ping.set_xlim(t_min, t_max)
        self.ax_ping.set_ylim(max(0, min(pings) - 5), max(pings) + 10)

        self.ln_score.set_data(times, scores)
        self.thresh_ln.set_ydata([config.THRESHOLD_HIGH] * 2)
        self.ax_score.set_xlim(t_min, t_max)
        self.ax_score.set_ylim(0, max(max(scores) + 0.5, config.THRESHOLD_HIGH + 1))

        # HEATMAP
        if stats is not None:
            # Build heat row from current stats
            std_rssi = stats.get("rssi_std", 0)
            std_ping = stats.get("ping_std", 0) if "ping_std" in stats else abs(ping - self.ping_buf[-2] if len(self.ping_buf) > 1 else ping) / 10
            sc = stats.get("score", 0)
            row = [std_rssi, std_ping if "ping_std" in stats else 0.5, sc]
            self.heat_rows.append(row)
            if len(self.heat_rows) > self.max_heat_rows:
                self.heat_rows.pop(0)

            if len(self.heat_rows) > 5:
                heat_matrix = np.array(self.heat_rows).T
                display_matrix = np.zeros((3, 30))
                cols = min(heat_matrix.shape[1], 30)
                display_matrix[:, :cols] = heat_matrix[:, -cols:]

                self.heat_img.set_data(display_matrix)
                vmax = max(5.0, float(display_matrix.max()))
                self.heat_img.set_clim(vmin=0, vmax=vmax)

                self.ax_heat.set_xticks([0, cols//2, cols-1])
                self.ax_heat.set_xticklabels([f"{int(t_min)}s", f"{int(t_min + (t_max-t_min)/2)}s", f"{int(t_max)}s"])
                self.ax_heat.set_yticks([0, 1, 2])
                self.ax_heat.set_yticklabels(["RSSI σ", "Ping σ", "Score"])

        self.canvas.draw_idle()

    def update_threshold(self, val):
        self.thresh_ln.set_ydata([float(val)] * 2)
        self.canvas.draw_idle()
