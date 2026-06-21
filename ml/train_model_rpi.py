"""
=============================================================
ENTRAINEMENT SIMPLIFIE - ISOLATION FOREST UNIQUEMENT
=============================================================
Version legere pour Raspberry Pi (pas besoin de TensorFlow).
Le script predict_realtime.py utilise la regression lineaire
a la place du LSTM, donc seul Isolation Forest est necessaire.

Usage:
    python3 train_model_rpi.py
=============================================================
"""

import pandas as pd
import numpy as np
import os
import pickle
from datetime import datetime

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import classification_report

print("=" * 60)
print("  ENTRAINEMENT ISOLATION FOREST (version RPi)")
print("=" * 60)
print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "training_data.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

IF_CONTAMINATION = 0.08
IF_N_ESTIMATORS = 200

# ============================================================
# CHARGEMENT DES DONNEES
# ============================================================
print("[1/4] Chargement des donnees...")

if not os.path.exists(DATA_PATH):
    print(f"  ERREUR: {DATA_PATH} introuvable!")
    print("  Lancez d'abord: python3 generate_training_data.py")
    exit(1)

df = pd.read_csv(DATA_PATH)
print(f"  Lignes: {len(df)}")
print(f"  Pompes: {sorted(df['pompe_id'].unique())}")
print()

# ============================================================
# PREPARATION
# ============================================================
print("[2/4] Preparation des donnees...")

df = df.dropna(subset=['T_moteur', 'T_ambiante', 'delta_T', 'health_score', 'pente'])

features_if = ['delta_T', 'pente', 'health_score', 'T_moteur']
X_if = df[features_if].values

scaler_if = MinMaxScaler()
X_if_scaled = scaler_if.fit_transform(X_if)

print(f"  Features: {features_if}")
print(f"  Donnees apres nettoyage: {len(df)} lignes")
print()

# ============================================================
# ENTRAINEMENT
# ============================================================
print("[3/4] Entrainement Isolation Forest...")
print(f"  n_estimators={IF_N_ESTIMATORS}, contamination={IF_CONTAMINATION}")

model_if = IsolationForest(
    n_estimators=IF_N_ESTIMATORS,
    contamination=IF_CONTAMINATION,
    random_state=42,
    n_jobs=-1
)
model_if.fit(X_if_scaled)

predictions_if = model_if.predict(X_if_scaled)
anomalies_detectees = (predictions_if == -1).sum()
print(f"  Anomalies detectees: {anomalies_detectees} ({anomalies_detectees/len(df)*100:.1f}%)")

if 'label' in df.columns:
    labels_reels = df['label'].values
    pred_binaire = (predictions_if == -1).astype(int)
    label_binaire = (labels_reels >= 1).astype(int)
    rapport = classification_report(label_binaire, pred_binaire,
                                    target_names=['Normal', 'Anomalie'], output_dict=True)
    print(f"  Precision: {rapport['Anomalie']['precision']:.2f}")
    print(f"  Recall:    {rapport['Anomalie']['recall']:.2f}")
    print(f"  F1-score:  {rapport['Anomalie']['f1-score']:.2f}")

print()

# ============================================================
# SAUVEGARDE
# ============================================================
print("[4/4] Sauvegarde du modele...")

if_path = os.path.join(MODELS_DIR, "isolation_forest.pkl")
with open(if_path, 'wb') as f:
    pickle.dump({
        'model': model_if,
        'scaler': scaler_if,
        'features': features_if,
        'contamination': IF_CONTAMINATION,
        'trained_at': datetime.now().isoformat()
    }, f)
print(f"  Sauvegarde: {if_path}")

scaler_path = os.path.join(MODELS_DIR, "scaler_lstm.pkl")
with open(scaler_path, 'wb') as f:
    pickle.dump({
        'scaler': scaler_if,
        'features': features_if,
        'target': 'delta_T',
        'target_idx': 0,
        'window': 60,
        'horizon': 10,
        'trained_at': datetime.now().isoformat()
    }, f)
print(f"  Sauvegarde: {scaler_path}")

print()
print("=" * 60)
print("  ENTRAINEMENT TERMINE!")
print("  Lancez maintenant: python3 predict_realtime.py")
print("=" * 60)
