# RF-sentry
RF-Sentry Pro

Real-time WiFi-based human presence detection using only a laptop's WiFi adapter and a mobile hotspot — no cameras, no PIR sensors, no dedicated hardware.

Show Image
Show Image
Show Image
Show Image


What it does

RF-Sentry Pro detects human movement inside a room by analyzing fluctuations in WiFi signal strength (RSSI). It reads live signal data from a standard Windows WiFi adapter, filters noise with a Kalman filter, computes rolling statistical variance, and fuses several metrics into an anomaly score — classifying the environment in real time as Secure, Minor Movement, or Intrusion Detected.

No specialized RF hardware, no SDR, no CSI-capable network card. Just a laptop, a phone's hotspot, and signal processing.

Why this works (the physics)


WiFi operates at 2.4GHz / 5GHz.
The human body is roughly 70% water, and water absorbs and scatters RF energy at these frequencies.
When a person moves through the RF field between two devices, they don't just "block" the signal — they measurably alter multipath propagation, causing attenuation and reflection changes.
This shows up as fluctuation in RSSI (signal strength) and, secondarily, in ping latency as packets take disrupted paths.


This is the same underlying phenomenon studied in academic WiFi-sensing research using Channel State Information (CSI). RF-Sentry Pro is intentionally scoped to work with the coarser RSSI signal available on any consumer Windows laptop, trading some precision for zero hardware requirements.

Architecture

rf_sentry/
├── main.py          → Entry point, launches the dashboard
├── config.py        → Constants: sample rate, thresholds, file paths
├── kalman.py         → Kalman filter for RSSI/ping noise reduction
├── collector.py       → Live data collection via netsh + ping (subprocess)
├── engine.py         → Rolling-window statistics + anomaly fusion score
├── logger.py          → Timestamped CSV logging for reproducible research data
├── plots.py           → Live 4-panel visualization (RSSI, ping, score, heatmap)
└── dashboard.py        → Tkinter UI: controls, live metrics, status panel

Detection method

Rolling metrics (per cycle):


rssi_std — standard deviation of recent RSSI readings
rssi_range — peak-to-peak spread of recent readings
ping_std — standard deviation of ping latency
drift — deviation from the calibrated baseline mean


Fusion score:

score = (σ_rssi × 0.50) + (range × 0.20) + (drift × 0.20) + (σ_ping × 0.10)

Classification:

ScoreStatus< 1.5🟢 Secure1.5 – 3.5🟡 Minor Movement≥ 3.5🔴 Intrusion Detected

Getting started

Requirements


Windows 10/11
Python 3.8+
An active mobile hotspot connection
pip install matplotlib numpy scipy


Setup

bashgit clone https://github.com/Mariyam-Arshiya/RF-sentry.git
cd RF-sentry
pip install -r requirements.txt
python main.py

Set your hotspot gateway IP in config.py (find it via ipconfig).

Usage


Connect your laptop to your phone's mobile hotspot.
Click Calibrate Baseline and stay still in an empty area for 10 seconds.
Click Start Monitoring.
Walk between the laptop and phone — watch RSSI shift and the anomaly score rise.
Export the session as CSV for further analysis.


Screenshots

(add your dashboard screenshot / demo GIF here)

Honest limitations


Single access point — detects "something moved," not precise location. No triangulation without multiple APs.
Windows-only — relies on netsh and Windows-specific ping behavior.
RSSI, not CSI — this project uses signal-strength aggregates rather than full Channel State Information. CSI-based systems (using specialized network cards) achieve sub-meter precision; RSSI-based systems trade that precision for zero extra hardware.
Statistical thresholds, not a trained model — current detection uses tuned statistical rules rather than a classifier trained on labeled data (see Roadmap).
Environmental sensitivity — large metal objects or overlapping WiFi networks can cause false positives; the Kalman filter mitigates but does not eliminate this.


Roadmap


 Ground-truth-labeled validation dataset with precision/recall/F1 reporting
 Adaptive, self-calibrating thresholds (mean + k·σ from baseline) instead of fixed constants
 scikit-learn classifier (Random Forest / SVM) trained on logged sessions, benchmarked against the statistical baseline
 Multivariate anomaly scoring (Mahalanobis distance) in place of the linear fusion score
 Passive multi-AP RSSI logging for basic directionality
 Session replay mode for reproducible demos
 Unit test suite (pytest) for the Kalman filter and fusion score math
 Optional Flask-based web dashboard mirror


Tech stack

Python · NumPy · SciPy · Matplotlib · Tkinter · Kalman Filtering · Statistical Signal Processing

Inspiration

This project was inspired by a scene in Pritam & Pedro (2026) that explored the contrast between traditional investigative intuition and modern signal intelligence — the idea of "reading a signal others miss." That inspiration shaped the concept; the physics, math, and implementation are original engineering work.

License

MIT — see LICENSE for details.

Author

Mariyam Arshiya
