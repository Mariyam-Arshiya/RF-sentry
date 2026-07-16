import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import config


class PlotPanel:
    def __init__(self, parent):
        self.rssi_buf  = deque(maxlen=config.PLOT_BUFFER)
        self.ping_buf  = deque(maxlen=config.PLOT_BUFFER)
        self.score_buf = deque(maxlen=config.PLOT_BUFFER)
        self.time_buf  = deque(maxlen=config.PLOT_BUFFER)
        self._build(parent)

    def _build(self, parent):
        plt.style.use('dark_background')
        self.fig = plt.Figure(figsize=(9, 6), facecolor='#0a0a0a')
        self.fig.subplots_adjust(
            hspace=0.45, left=0.08,
            right=0.97, top=0.93, bottom=0.07
        )

        self.ax_rssi  = self._make_axis(311, 'RSSI  (dBm)',        '#00FF66')
        self.ax_ping  = self._make_axis(312, 'Ping Latency  (ms)', '#4488FF')
        self.ax_score = self._make_axis(313, 'Anomaly Score',      '#FF4444')

        self.ln_rssi,  = self.ax_rssi.plot([],  [], color='#00FF66', lw=1.5, label='RSSI')
        self.ln_base,  = self.ax_rssi.plot([],  [], color='#FFA500', lw=1.0, ls='--', label='Baseline')
        self.ln_ping,  = self.ax_ping.plot([],  [], color='#4488FF', lw=1.5)
        self.ln_score, = self.ax_score.plot([], [], color='#FF4444', lw=1.5)

        self.thresh_ln = self.ax_score.axhline(
            y=config.THRESHOLD_HIGH,
            color='#FFA500', lw=1.0, ls='--',
            label=f'Threshold'
        )

        self.ax_rssi.legend(
            loc='upper right', fontsize=7,
            facecolor='#111111', edgecolor='#333333'
        )
        self.ax_score.legend(
            loc='upper right', fontsize=7,
            facecolor='#111111', edgecolor='#333333'
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

    def _make_axis(self, pos, title, color):
        ax = self.fig.add_subplot(pos)
        ax.set_facecolor('#0d0d0d')
        ax.set_title(title, color=color, fontsize=9, pad=4)
        ax.tick_params(colors='#555555', labelsize=7)
        ax.grid(True, color='#1c1c1c', lw=0.5)
        for spine in ax.spines.values():
            spine.set_color('#2a2a2a')
        return ax

    def push(self, t, rssi, ping, score, baseline=None):
        self.time_buf.append(t)
        self.rssi_buf.append(rssi)
        self.ping_buf.append(ping)
        self.score_buf.append(score)

        times  = list(self.time_buf)
        rssies = list(self.rssi_buf)
        pings  = list(self.ping_buf)
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

        self.canvas.draw_idle()

    def update_threshold(self, val):
        self.thresh_ln.set_ydata([float(val)] * 2)
        self.canvas.draw_idle()
