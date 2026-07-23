# RF-Sentry Pro

**Real-Time WiFi-Based Human Presence Detection — No Cameras, No Extra Hardware**

RF-Sentry Pro is a lightweight, real-time human movement detection system that uses only a standard laptop WiFi adapter and a mobile hotspot. By analyzing fluctuations in WiFi signal strength (RSSI), it detects environmental disturbances caused by human presence—without requiring cameras, PIR sensors, SDRs, or specialized RF hardware.

---

## 🚀 Overview

RF-Sentry Pro leverages statistical signal processing to monitor WiFi signal behavior and classify environmental activity into:

* 🟢 **Secure**
* 🟡 **Minor Movement**
* 🔴 **Intrusion Detected**

The system operates entirely on consumer-grade hardware, making it accessible, portable, and easy to deploy.

---

## 🧠 How It Works

WiFi signals at **2.4 GHz / 5 GHz** interact with the human body, which is ~70% water. When a person moves within the signal path:

* RF signals are **absorbed, reflected, and scattered**
* **Multipath propagation changes**
* Measurable fluctuations appear in:

  * RSSI (signal strength)
  * Ping latency

RF-Sentry Pro captures and analyzes these fluctuations in real time.

---

## ⚙️ Architecture

```
rf_sentry/
├── main.py        # Entry point
├── config.py      # Configuration constants
├── kalman.py      # Noise filtering (Kalman filter)
├── collector.py   # Data collection (netsh + ping)
├── engine.py      # Statistical analysis + anomaly scoring
├── logger.py      # CSV logging
├── plots.py       # Real-time visualization
└── dashboard.py   # Tkinter-based UI
```

---

## 📊 Detection Method

### Rolling Metrics

* **rssi_std** → RSSI standard deviation
* **rssi_range** → Peak-to-peak RSSI spread
* **ping_std** → Ping latency variation
* **drift** → Deviation from baseline

### Fusion Score

```
score = (σ_rssi × 0.50)
      + (range × 0.20)
      + (drift × 0.20)
      + (σ_ping × 0.10)
```

### Classification

| Score Range | Status                |
| ----------- | --------------------- |
| < 1.5       | 🟢 Secure             |
| 1.5 – 3.5   | 🟡 Minor Movement     |
| ≥ 3.5       | 🔴 Intrusion Detected |

---

## 🛠️ Requirements

* Windows 10 / 11
* Python 3.8+
* Active mobile hotspot connection

Install dependencies:

```
pip install matplotlib numpy scipy
```

---

## 🔧 Setup

```
git clone https://github.com/Mariyam-Arshiya/RF-sentry.git
cd RF-sentry
pip install -r requirements.txt
python main.py
```

Update your hotspot gateway IP in `config.py` (use `ipconfig` to find it).

---

## ▶️ Usage

1. Connect your laptop to your phone's hotspot
2. Click **Calibrate Baseline**

   * Stay still for ~10 seconds
3. Click **Start Monitoring**
4. Move between the laptop and hotspot
5. Observe real-time signal changes and anomaly score
6. Export session logs as CSV for analysis

---

## 📉 Limitations

* **Single Access Point**
  Detects motion, not exact location

* **Windows Only**
  Depends on `netsh` and Windows ping behavior

* **RSSI-Based (Not CSI)**
  Lower precision than CSI-based systems

* **Static Thresholds**
  Uses rule-based classification (not ML yet)

* **Environmental Sensitivity**
  Interference from objects/networks may cause noise

---

## 🗺️ Roadmap

* Labeled dataset with precision/recall/F1 metrics
* Adaptive thresholding (baseline-driven)
* Machine learning models (Random Forest / SVM)
* Mahalanobis distance–based anomaly detection
* Multi-AP support for directionality
* Session replay system
* Unit testing (pytest)
* Optional Flask web dashboard

---

## 🧰 Tech Stack

* Python
* NumPy, SciPy
* Matplotlib
* Tkinter
* Kalman Filtering
* Statistical Signal Processing

---

## 💡 Inspiration

Inspired by *Pritam & Pedro (2026)* — the idea from the viral scene where Martin tracks minister house using wifi sensing and router. This project translates that concept into a practical engineering system grounded in RF physics and data analysis.

---
## Demo


<img width="1280" height="720" alt="Screenshot (223)" src="https://github.com/user-attachments/assets/5c2f453e-a676-4a0d-bebb-c75689c303f0" />


https://github.com/user-attachments/assets/479cb43f-b5a0-4d1f-a188-82c7a5f349a1



## 📄 License

MIT License — see `LICENSE` for details.

---

## 👩‍💻 Author

**Mariyam Arshiya**

---

## ⭐ Contributing

Contributions, ideas, and improvements are welcome. Feel free to open issues or submit pull requests.

---
