"""
=============================================================
PREDICTION EN TEMPS REEL - MAINTENANCE PREDICTIVE
=============================================================
Version legere sans TensorFlow.
Utilise Isolation Forest + prediction par regression lineaire.

Usage:
    python3 predict_realtime.py
=============================================================
"""

import json
import time
import pickle
import os
import sys
import numpy as np
from datetime import datetime
from collections import deque

import paho.mqtt.client as mqtt

print("=" * 60)
print("  PREDICTION TEMPS REEL - MAINTENANCE PREDICTIVE")
print("=" * 60)
print(f"  Demarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ============================================================
# CONFIGURATION
# ============================================================
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "python-ml-predictor"

TOPIC_POMPES = "station/pompe/+/pt100/avant/temperature"
TOPIC_AMBIANCE = "station/ambiance/dht11"
TOPIC_PREDICTION = "station/pompe/{}/ml/prediction"
TOPIC_ML_STATUS = "station/status/ml"

PREDICTION_INTERVAL = 10
WINDOW_SIZE = 60
SEUIL_CRITIQUE = 70

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# ============================================================
# CHARGEMENT DU MODELE ISOLATION FOREST
# ============================================================
print("[1/3] Chargement du modele...")

if_path = os.path.join(MODELS_DIR, "isolation_forest.pkl")
if not os.path.exists(if_path):
    print(f"  ERREUR: {if_path} introuvable!")
    sys.exit(1)

with open(if_path, 'rb') as f:
    if_data = pickle.load(f)
    model_if = if_data['model']
    scaler_if = if_data['scaler']
    features_if = if_data['features']
print(f"  Isolation Forest charge (entraine le {if_data['trained_at'][:10]})")

# Charger le scaler LSTM pour les references
scaler_path = os.path.join(MODELS_DIR, "scaler_lstm.pkl")
lstm_available = False
if os.path.exists(scaler_path):
    with open(scaler_path, 'rb') as f:
        lstm_data = pickle.load(f)
        scaler_lstm = lstm_data['scaler']
        lstm_features = lstm_data['features']
    print("  Scaler LSTM charge (prediction par regression)")
    lstm_available = True
else:
    print("  Scaler LSTM non trouve - prediction par regression simple")

print()

# ============================================================
# ETAT GLOBAL
# ============================================================
historique = {}
for i in range(1, 6):
    historique[i] = deque(maxlen=WINDOW_SIZE)

ambiance = {"temperature": 25.0, "humidite": 50.0}

stats = {
    "messages_recus": 0,
    "predictions_faites": 0,
    "anomalies_detectees": 0,
    "demarrage": datetime.now().isoformat()
}

last_prediction_time = 0

# ============================================================
# FONCTIONS DE PREDICTION
# ============================================================
def predire_isolation_forest(pompe_id):
    """Detecte si la mesure actuelle est une anomalie."""
    if len(historique[pompe_id]) < 2:
        return None

    dernier = historique[pompe_id][-1]
    avant = historique[pompe_id][-2]
    pente = dernier['delta_T'] - avant['delta_T']

    X = np.array([[
        dernier['delta_T'],
        pente,
        dernier['health_score'],
        dernier['T_moteur']
    ]])

    X_scaled = scaler_if.transform(X)
    prediction = model_if.predict(X_scaled)[0]
    score = model_if.score_samples(X_scaled)[0]

    est_anomalie = prediction == -1
    score_anomalie = max(0, min(1, -score))

    # Ne signaler une anomalie que si delta_T est ELEVE (surchauffe)
    # Un delta_T bas n'est pas dangereux, c'est juste un moteur froid
    if est_anomalie and dernier['delta_T'] < 20:
        est_anomalie = False
        score_anomalie = min(score_anomalie, 0.3)

    return {
        "est_anomalie": bool(est_anomalie),
        "score_anomalie": round(float(score_anomalie), 3)
    }


def predire_tendance(pompe_id):
    """Predit la tendance future par regression lineaire sur l'historique."""
    points = list(historique[pompe_id])
    n = len(points)

    if n < 10:
        return None

    # Extraire les delta_T des derniers points
    deltas = np.array([p['delta_T'] for p in points])

    # Regression lineaire simple (moindres carres)
    x = np.arange(n)
    coeffs = np.polyfit(x, deltas, 1)
    pente_regression = coeffs[0]  # degres par point (1 point = 1 seconde)

    # Pente en degres/minute
    pente_par_min = pente_regression * 60

    # Predire delta_T dans 5 minutes (300 secondes = 300 points)
    horizon = 300
    delta_t_predit = np.polyval(coeffs, n + horizon)
    delta_t_predit = max(0, delta_t_predit)

    # Delta T actuel
    delta_t_actuel = deltas[-1]

    # RUL
    if pente_par_min > 0.1:
        reste = SEUIL_CRITIQUE - delta_t_actuel
        if reste > 0:
            rul_minutes = round(reste / pente_par_min)
        else:
            rul_minutes = 0
    else:
        rul_minutes = -1

    # Health score predit
    if delta_t_predit <= 15:
        health_predit = 100
    elif delta_t_predit <= 30:
        health_predit = 100 - ((delta_t_predit - 15) / 15) * 20
    elif delta_t_predit <= 45:
        health_predit = 80 - ((delta_t_predit - 30) / 15) * 30
    elif delta_t_predit <= 60:
        health_predit = 50 - ((delta_t_predit - 45) / 15) * 30
    else:
        health_predit = max(0, 20 - ((delta_t_predit - 60) / 20) * 20)

    return {
        "delta_t_predit": round(float(delta_t_predit), 2),
        "health_predit": round(float(np.clip(health_predit, 0, 100)), 1),
        "rul_minutes": int(rul_minutes) if rul_minutes >= 0 else -1,
        "tendance": round(float(pente_par_min), 3)
    }


def faire_predictions():
    """Lance les predictions pour toutes les pompes."""
    global last_prediction_time

    now = time.time()
    if now - last_prediction_time < PREDICTION_INTERVAL:
        return
    last_prediction_time = now

    for pompe_id in range(1, 6):
        if len(historique[pompe_id]) < 5:
            continue

        resultat_if = predire_isolation_forest(pompe_id)
        resultat_tendance = predire_tendance(pompe_id)

        resultat = {
            "pompe_id": pompe_id,
            "timestamp": datetime.now().isoformat(),
            "donnees_actuelles": {
                "T_moteur": historique[pompe_id][-1]['T_moteur'],
                "delta_T": historique[pompe_id][-1]['delta_T'],
                "health_score": historique[pompe_id][-1]['health_score']
            }
        }

        if resultat_if:
            resultat["isolation_forest"] = resultat_if
            if resultat_if["est_anomalie"]:
                stats["anomalies_detectees"] += 1

        if resultat_tendance:
            resultat["lstm"] = resultat_tendance

        # Niveau global
        niveau = "NORMAL"
        if resultat_if and resultat_if["est_anomalie"]:
            if resultat_if["score_anomalie"] > 0.7:
                niveau = "CRITIQUE"
            else:
                niveau = "ALERTE"
        elif resultat_tendance and resultat_tendance["rul_minutes"] >= 0 and resultat_tendance["rul_minutes"] < 30:
            niveau = "ATTENTION"

        resultat["niveau_ml"] = niveau
        resultat["confiance"] = round(float(
            resultat_if["score_anomalie"] if resultat_if else 0.5
        ), 2)

        # Publier sur MQTT
        topic = TOPIC_PREDICTION.format(pompe_id)
        payload = json.dumps(resultat)
        client.publish(topic, payload, qos=0)

        stats["predictions_faites"] += 1

        if niveau != "NORMAL":
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] POMPE {pompe_id} - {niveau} "
                  f"| Score: {resultat_if['score_anomalie'] if resultat_if else '?'} "
                  f"| RUL: {resultat_tendance['rul_minutes'] if resultat_tendance else '?'} min")


# ============================================================
# CALLBACKS MQTT
# ============================================================
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[MQTT] Connecte au broker")
        client.subscribe(TOPIC_POMPES)
        client.subscribe(TOPIC_AMBIANCE)
        client.publish(TOPIC_ML_STATUS, "online", retain=True)
        print(f"[MQTT] Abonne a: {TOPIC_POMPES}")
        print(f"[MQTT] Abonne a: {TOPIC_AMBIANCE}")
    else:
        print(f"[MQTT] Erreur connexion: rc={rc}")


def on_message(client, userdata, msg):
    global ambiance
    stats["messages_recus"] += 1

    try:
        payload = json.loads(msg.payload.decode())

        if "ambiance" in msg.topic:
            ambiance["temperature"] = payload.get("temperature", 25)
            ambiance["humidite"] = payload.get("humidite", 50)
            return

        if "pompe" in msg.topic:
            parts = msg.topic.split('/')
            pompe_id = int(parts[2])

            if pompe_id < 1 or pompe_id > 5:
                return

            t_moteur = payload.get("temperature", 0)
            t_ambiante = ambiance["temperature"]
            delta_t = max(0, t_moteur - t_ambiante)

            # Health score
            if delta_t <= 15:
                health = 100
            elif delta_t <= 30:
                health = 100 - ((delta_t - 15) / 15) * 20
            elif delta_t <= 45:
                health = 80 - ((delta_t - 30) / 15) * 30
            elif delta_t <= 60:
                health = 50 - ((delta_t - 45) / 15) * 30
            else:
                health = max(0, 20 - ((delta_t - 60) / 20) * 20)

            # Pente
            pente = 0
            if len(historique[pompe_id]) > 0:
                ancien_delta = historique[pompe_id][-1]['delta_T']
                pente = delta_t - ancien_delta

            point = {
                "T_moteur": round(t_moteur, 2),
                "T_ambiante": round(t_ambiante, 2),
                "delta_T": round(delta_t, 2),
                "health_score": round(health, 1),
                "pente": round(pente, 3),
                "timestamp": time.time()
            }
            historique[pompe_id].append(point)

            faire_predictions()

    except Exception as e:
        print(f"[ERREUR] {e}")


def on_disconnect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Deconnecte (rc={rc}), tentative de reconnexion...")


# ============================================================
# DEMARRAGE
# ============================================================
print("[2/3] Connexion MQTT...")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect
client.will_set(TOPIC_ML_STATUS, "offline", retain=True)

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    print(f"[ERREUR] Impossible de se connecter au broker MQTT: {e}")
    sys.exit(1)

print("[3/3] Boucle de prediction demarree")
print()
print("  En attente de donnees des capteurs...")
print("  (les predictions commencent apres 10 points)")
print()
print("-" * 60)

try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\n\nArret demande par l'utilisateur")
    print(f"  Messages recus: {stats['messages_recus']}")
    print(f"  Predictions faites: {stats['predictions_faites']}")
    print(f"  Anomalies detectees: {stats['anomalies_detectees']}")
    client.publish(TOPIC_ML_STATUS, "offline", retain=True)
    client.disconnect()
    print("  Deconnecte proprement.")
