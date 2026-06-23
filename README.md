# Predictive Maintenance System - Pump Motors

Real-time predictive maintenance system for pump motors at ONEE water pumping station (Ait Baha, Morocco).

## Architecture

```
PT100 Sensors → ESP32 → MQTT → Raspberry Pi 4B → Dashboard
                                    ├── Node-RED (calculations)
                                    ├── Python ML (Isolation Forest)
                                    ├── InfluxDB (storage)
                                    └── Web Dashboard (visualization)
```

## Components

| Component | Role |
|-----------|------|
| 5x PT100 + MAX31865 | Motor temperature sensing |
| DHT11 | Ambient temperature & humidity |
| ESP32-WROOM-32 | Data acquisition + WiFi |
| Raspberry Pi 4B | Edge server (MQTT, ML, DB, API) |
| 3 LEDs + Buzzer | Local alerts |

## Features

- Real-time temperature monitoring (5 pumps)
- Anomaly detection using Isolation Forest (unsupervised ML)
- Health Score calculation (0-100)
- RUL prediction (Remaining Useful Life)
- Trend analysis (linear regression)
- Web dashboard with live updates
- Excel data export
- Automatic alerts (LED + Buzzer + Dashboard)

## Project Structure

```
├── esp32_final.ino              # ESP32 firmware (Arduino)
├── generate_training_data.py    # Training data generator (5 scenarios)
├── function_health_score.js     # Node-RED function node
├── nodered_flow_principal.json  # Node-RED main flow
├── nodered_flow_ml.json         # Node-RED ML flow
├── ml/
│   ├── train_model_rpi.py       # Model training script
│   └── predict_realtime.py      # Real-time prediction service
├── dashboard/
│   ├── index.html               # Web interface
│   ├── app.js                   # Dashboard logic
│   ├── style.css                # Styling
│   └── logo-onee.png            # Logo
└── kicad_projet/                # PCB schematic (KiCad 8)
```

## Key Equations

- **Delta T** = T_motor - T_ambient (eliminates climate variation)
- **Health Score** = tiered function (100→0 based on Delta T)
- **RUL** = (critical_threshold - Delta_T) / slope
- **Anomaly Score** = Isolation Forest isolation depth

## ML Model

- Algorithm: Isolation Forest (unsupervised)
- Features: [delta_T, slope, health_score, T_motor]
- Training: 432,000 data points (5 scenarios + 4 environmental effects)
- Parameters: n_estimators=200, contamination=0.08

## Deployment

### Raspberry Pi Services

```bash
sudo systemctl start mosquitto
sudo systemctl start nodered
sudo systemctl start influxdb
sudo systemctl start ml-predictor
```

### MQTT Topics

```
station/pompe/{1-5}/pt100/avant/temperature  # Sensor data
station/ambiance/dht11                        # Ambient
station/pompe/{1-5}/ml/prediction             # ML results
```

### Dashboard

Open browser: `http://<raspberry-pi-ip>:1880/dashboard`

## Technologies

- **Hardware**: ESP32, MAX31865, PT100, DHT11, Raspberry Pi 4B
- **Communication**: MQTT (Mosquitto)
- **Backend**: Node-RED, Python 3, scikit-learn
- **Database**: InfluxDB 2.x
- **Frontend**: HTML5, CSS3, JavaScript, Chart.js
- **PCB Design**: KiCad 8

## Author

PFE Project - ONEE Ait Baha - 2025/2026
