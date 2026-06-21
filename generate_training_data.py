"""
=============================================================
GENERATEUR DE DONNEES D'ENTRAINEMENT
MAINTENANCE PREDICTIVE - STATION POMPAGE AIT BAHA
=============================================================
Simule 30 jours de donnees pour 5 pompes.

5 scenarios principaux :
  1. Fonctionnement normal (temperature stable autour de 35-40 C)
  2. Demarrage moteur (montee progressive de 25 C vers regime)
  3. Arret moteur (descente progressive vers temperature ambiante)
  4. Surcharge progressive (montee lente sur plusieurs jours)
  5. Surchauffe critique (montee rapide, depassement seuil danger)

4 effets environnementaux (appliques a toutes les pompes) :
  - Temperature ambiante elevee (ete, jours 1-8)
  - Temperature ambiante faible (hiver, jours 22-30)
  - Humidite elevee (risque corrosion, jours 9-14)
  - Poussiere excessive (refroidissement reduit, jours 15-21)

Usage:
    python3 generate_training_data.py
=============================================================
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

np.random.seed(42)

# ============================================================
# CONFIGURATION
# ============================================================
NB_POMPES = 5
DUREE_JOURS = 30
FREQ_SECONDES = 30
POINTS_PAR_JOUR = 86400 // FREQ_SECONDES  # 2880 points/jour
TOTAL_POINTS = DUREE_JOURS * POINTS_PAR_JOUR

print("=" * 60)
print("  GENERATION DONNEES D'ENTRAINEMENT")
print("=" * 60)
print(f"  Duree: {DUREE_JOURS} jours")
print(f"  Pompes: {NB_POMPES}")
print(f"  Frequence: 1 point / {FREQ_SECONDES}s")
print(f"  Points par pompe: {TOTAL_POINTS}")
print(f"  Total: {TOTAL_POINTS * NB_POMPES} mesures")
print()

# Timestamp de depart
start_time = datetime(2026, 5, 14, 0, 0, 0)
timestamps = [start_time + timedelta(seconds=i * FREQ_SECONDES) for i in range(TOTAL_POINTS)]


# ============================================================
# EFFETS ENVIRONNEMENTAUX
# ============================================================
# Periodes environnementales sur les 30 jours :
#   Jours 1-8   : Ete (temperature ambiante elevee, +8 C)
#   Jours 9-14  : Humidite elevee (risque corrosion, +2 C moteur)
#   Jours 15-21 : Poussiere excessive (refroidissement reduit, +4 C moteur)
#   Jours 22-30 : Hiver (temperature ambiante basse, -6 C)

def get_condition_environnementale(jour):
    """Retourne la condition environnementale active pour un jour donne."""
    if jour < 8:
        return "ete"
    elif jour < 14:
        return "humidite"
    elif jour < 21:
        return "poussiere"
    else:
        return "hiver"


def generer_temperature_ambiante(timestamps):
    """
    Temperature ambiante avec effets environnementaux :
    - Ete (jours 1-8)   : base 38 C, pics a 44 C en journee
    - Normal (transition): base 28 C
    - Hiver (jours 22-30): base 18 C, min 12 C la nuit
    """
    temps = []
    for ts in timestamps:
        heure = ts.hour + ts.minute / 60.0
        jour = (ts - start_time).days
        condition = get_condition_environnementale(jour)

        # Base selon la saison
        if condition == "ete":
            base = 38  # Ete au Maroc, tres chaud
        elif condition == "hiver":
            base = 18  # Hiver, plus frais
        else:
            base = 28  # Normal (printemps/automne)

        # Cycle jour/nuit
        if 6 <= heure <= 18:
            if condition == "ete":
                cycle = 6 * np.sin((heure - 6) * np.pi / 12)  # +6 C en journee
            elif condition == "hiver":
                cycle = 5 * np.sin((heure - 6) * np.pi / 12)  # +5 C en journee
            else:
                cycle = 8 * np.sin((heure - 6) * np.pi / 12)
        else:
            if condition == "hiver":
                cycle = -6  # Nuits froides en hiver
            else:
                cycle = -3

        bruit = np.random.normal(0, 0.3)
        temps.append(base + cycle + bruit)

    return np.array(temps)


def generer_humidite(timestamps):
    """
    Humidite relative simulee :
    - Jours 9-14 : humidite elevee (80-95%)
    - Autres     : humidite normale (40-60%)
    """
    humidite = []
    for ts in timestamps:
        jour = (ts - start_time).days
        heure = ts.hour
        condition = get_condition_environnementale(jour)

        if condition == "humidite":
            base = 88
            variation = 7 * np.sin(heure * np.pi / 12)
            bruit = np.random.normal(0, 2)
        elif condition == "ete":
            base = 30
            variation = 5 * np.sin(heure * np.pi / 12)
            bruit = np.random.normal(0, 2)
        elif condition == "hiver":
            base = 55
            variation = 5 * np.sin(heure * np.pi / 12)
            bruit = np.random.normal(0, 2)
        else:
            base = 50
            variation = 10 * np.sin(heure * np.pi / 12)
            bruit = np.random.normal(0, 3)

        h = base + variation + bruit
        humidite.append(round(np.clip(h, 10, 99), 1))

    return np.array(humidite)


def effet_environnemental_moteur(jour, heure):
    """
    Retourne le surplus de temperature moteur du aux conditions
    environnementales (s'ajoute a la temperature de base).
    """
    condition = get_condition_environnementale(jour)

    if condition == "ete":
        # Ete : moteur sain mais tourne plus chaud car ambiante elevee
        # Le delta_T reste similaire mais T_moteur absolue est plus haute
        # Leger surplus car le refroidissement est moins efficace
        surplus = 3.0 + np.random.normal(0, 0.5)
        return max(0, surplus)

    elif condition == "humidite":
        # Humidite elevee : condensation, corrosion legere des
        # roulements, frottement accru -> +2 C
        surplus = 2.0 + np.random.normal(0, 0.4)
        # Plus d'effet la nuit (condensation au matin)
        if 4 <= heure <= 8:
            surplus += 1.5  # pic de condensation au matin
        return max(0, surplus)

    elif condition == "poussiere":
        # Poussiere excessive : colmatage des ailettes de
        # refroidissement, ventilation reduite -> +4 C
        # L'effet s'aggrave progressivement (accumulation)
        jour_poussiere = jour - 14  # jour 0-6 dans la periode
        accumulation = jour_poussiere * 0.5  # +0.5 C/jour d'accumulation
        surplus = 4.0 + accumulation + np.random.normal(0, 0.6)
        return max(0, surplus)

    elif condition == "hiver":
        # Hiver : temperature ambiante basse
        # Moteur tourne a temperature normale (bon refroidissement)
        # Pas de surplus, le moteur est meme legerement plus frais
        reduction = -1.5 + np.random.normal(0, 0.3)
        return reduction  # peut etre negatif (moteur plus frais)

    return 0


# ============================================================
# SCENARIOS PRINCIPAUX
# ============================================================

def scenario_normal(total_points, timestamps, base_temp):
    """
    SCENARIO 1 : Fonctionnement normal
    Moteur tourne a temperature stable avec petit bruit.
    Les effets environnementaux se superposent.
    """
    temp = np.zeros(total_points)
    labels = np.zeros(total_points, dtype=int)
    current = base_temp

    for i in range(total_points):
        jour = i // POINTS_PAR_JOUR
        heure = timestamps[i].hour
        charge_jour = 2.0 if 7 <= heure <= 19 else 0

        # Effet environnemental
        env = effet_environnemental_moteur(jour, heure)

        target = base_temp + charge_jour + env + np.random.normal(0, 0.4)
        current = current * 0.97 + target * 0.03
        current += np.random.normal(0, 0.1)
        current = max(20, current)
        temp[i] = round(current, 2)
        labels[i] = 0  # normal meme avec effets environnementaux

    return temp, labels


def scenario_demarrage(total_points, timestamps, base_temp):
    """
    SCENARIO 2 : Demarrage moteur
    Cycles marche/arret quotidiens.
    Montee vers regime en ~15 minutes au demarrage.
    """
    temp = np.zeros(total_points)
    labels = np.zeros(total_points, dtype=int)
    current = 28.0

    en_marche = False

    for i in range(total_points):
        jour = i // POINTS_PAR_JOUR
        heure = timestamps[i].hour
        minute = timestamps[i].minute

        # Demarrage a 6h00 et 14h00
        if (heure == 6 and minute == 0) or (heure == 14 and minute == 0):
            en_marche = True
        # Arret a 12h00 et 22h00
        if (heure == 12 and minute == 0) or (heure == 22 and minute == 0):
            en_marche = False

        # Effet environnemental
        env = effet_environnemental_moteur(jour, heure)

        if en_marche:
            target = base_temp + env + np.random.normal(0, 0.3)
            alpha = 0.04  # montee rapide (~15 min)
        else:
            # Moteur arrete -> revient vers ambiante
            condition = get_condition_environnementale(jour)
            if condition == "ete":
                t_repos = 38.0
            elif condition == "hiver":
                t_repos = 18.0
            else:
                t_repos = 28.0
            target = t_repos + np.random.normal(0, 0.3)
            alpha = 0.02  # refroidissement lent

        current = current * (1 - alpha) + target * alpha
        current += np.random.normal(0, 0.1)
        current = max(10, current)
        temp[i] = round(current, 2)
        labels[i] = 0

    return temp, labels


def scenario_arret(total_points, timestamps, base_temp):
    """
    SCENARIO 3 : Arret moteur prolonge + redemarrage
    Arrets programmes pour maintenance aux jours 5, 15, 25.
    """
    temp = np.zeros(total_points)
    labels = np.zeros(total_points, dtype=int)
    current = base_temp

    arrets = [
        (5, 10, 18),   # jour 5, arret de 10h a 18h
        (15, 8, 20),   # jour 15, arret de 8h a 20h
        (25, 14, 18),  # jour 25, arret de 14h a 18h
    ]

    for i in range(total_points):
        jour = i // POINTS_PAR_JOUR
        heure = timestamps[i].hour

        en_arret = False
        for (j_arret, h_debut, h_fin) in arrets:
            if jour == j_arret and h_debut <= heure < h_fin:
                en_arret = True
                break

        env = effet_environnemental_moteur(jour, heure)

        if en_arret:
            condition = get_condition_environnementale(jour)
            if condition == "ete":
                t_repos = 38.0
            elif condition == "hiver":
                t_repos = 18.0
            else:
                t_repos = 28.0
            target = t_repos + np.random.normal(0, 0.3)
            alpha = 0.015
        else:
            charge_jour = 2.0 if 7 <= heure <= 19 else 0
            target = base_temp + charge_jour + env + np.random.normal(0, 0.4)
            alpha = 0.03

        current = current * (1 - alpha) + target * alpha
        current += np.random.normal(0, 0.1)
        current = max(10, current)
        temp[i] = round(current, 2)
        labels[i] = 0

    return temp, labels


def scenario_surcharge(total_points, timestamps, base_temp):
    """
    SCENARIO 4 : Surcharge progressive
    Normal 10 jours, puis +0.5 C/jour, puis +1.0 C/jour.
    Simule usure des roulements / manque de lubrification.
    """
    temp = np.zeros(total_points)
    labels = np.zeros(total_points, dtype=int)
    current = base_temp

    for i in range(total_points):
        jour = i // POINTS_PAR_JOUR
        heure = timestamps[i].hour
        charge_jour = 2.0 if 7 <= heure <= 19 else 0

        env = effet_environnemental_moteur(jour, heure)

        # Degradation progressive
        if jour < 10:
            degradation = 0
        elif jour < 20:
            degradation = (jour - 10) * 0.5  # +0.5 C/jour
        else:
            degradation = 5.0 + (jour - 20) * 1.0  # +1.0 C/jour

        target = base_temp + charge_jour + env + degradation + np.random.normal(0, 0.5)
        current = current * 0.97 + target * 0.03
        current += np.random.normal(0, 0.1)
        current = max(20, current)
        temp[i] = round(current, 2)

        if degradation < 3:
            labels[i] = 0
        elif degradation < 8:
            labels[i] = 1  # anomalie
        else:
            labels[i] = 2  # critique

    return temp, labels


def scenario_surchauffe(total_points, timestamps, base_temp):
    """
    SCENARIO 5 : Surchauffe critique
    3 episodes de surchauffe brutale (blocage, perte ventilation).
    +25 a +35 C en quelques minutes.
    """
    temp = np.zeros(total_points)
    labels = np.zeros(total_points, dtype=int)
    current = base_temp

    episodes = [
        (7, 14, 45, 25),    # jour 7: +25 C pendant 45 min
        (18, 10, 30, 35),   # jour 18: +35 C pendant 30 min
        (26, 16, 60, 30),   # jour 26: +30 C pendant 60 min
    ]

    for i in range(total_points):
        jour = i // POINTS_PAR_JOUR
        heure = timestamps[i].hour + timestamps[i].minute / 60.0
        charge_jour = 2.0 if 7 <= heure <= 19 else 0

        env = effet_environnemental_moteur(jour, int(heure))

        # Verifier si un episode de surchauffe est actif
        surchauffe = 0
        for (j_ep, h_debut, duree_min, intensite) in episodes:
            h_fin = h_debut + duree_min / 60.0
            if jour == j_ep and h_debut <= heure < h_fin:
                progression = (heure - h_debut) / (duree_min / 60.0)
                surchauffe = intensite * min(1.0, progression * 2)
                break
            elif jour == j_ep and h_fin <= heure < h_fin + 1.0:
                progression = (heure - h_fin) / 1.0
                surchauffe = intensite * (1.0 - progression)
                surchauffe = max(0, surchauffe)
                break

        target = base_temp + charge_jour + env + surchauffe + np.random.normal(0, 0.4)

        if surchauffe > 0:
            alpha = 0.08
        else:
            alpha = 0.03

        current = current * (1 - alpha) + target * alpha
        current += np.random.normal(0, 0.1)
        current = max(20, min(120, current))
        temp[i] = round(current, 2)

        if surchauffe > 20:
            labels[i] = 2
        elif surchauffe > 10:
            labels[i] = 1
        else:
            labels[i] = 0

    return temp, labels


# ============================================================
# GENERATION
# ============================================================
print("Generation temperature ambiante (avec effets saisonniers)...")
temp_ambiante = generer_temperature_ambiante(timestamps)

print("Generation humidite...")
humidite = generer_humidite(timestamps)

# Chaque pompe a un scenario principal
scenarios = {
    1: ("Fonctionnement normal", scenario_normal, 35),
    2: ("Demarrage moteur", scenario_demarrage, 36),
    3: ("Arret moteur", scenario_arret, 34),
    4: ("Surcharge progressive", scenario_surcharge, 35),
    5: ("Surchauffe critique", scenario_surchauffe, 36),
}

all_data = []

print("\nGeneration des scenarios (avec effets environnementaux)...")
print("-" * 60)
print("  Conditions environnementales sur 30 jours:")
print("    Jours 1-8   : ETE (ambiante 38-44 C)")
print("    Jours 9-14  : HUMIDITE ELEVEE (80-95%, +2 C moteur)")
print("    Jours 15-21 : POUSSIERE (refroidissement -30%, +4-7 C)")
print("    Jours 22-30 : HIVER (ambiante 12-23 C)")
print("-" * 60)

for pompe_id, (nom, fn_scenario, base) in scenarios.items():
    print(f"  Pompe {pompe_id}: {nom} (base={base} C)")
    temp_moteur, labels = fn_scenario(TOTAL_POINTS, timestamps, base)

    for i in range(TOTAL_POINTS):
        delta_t = max(0, temp_moteur[i] - temp_ambiante[i])

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
        health = round(np.clip(health, 0, 100), 1)

        # Pente (C/min)
        if i >= 2:
            pente = (temp_moteur[i] - temp_moteur[i - 2]) / 1.0
        else:
            pente = 0
        pente = round(pente, 3)

        # RUL
        seuil_critique = 70
        if pente > 0.1:
            reste = seuil_critique - delta_t
            rul = max(0, round(reste / pente, 1)) if reste > 0 else 0
        else:
            rul = -1

        # Condition environnementale active
        jour = i // POINTS_PAR_JOUR
        condition = get_condition_environnementale(jour)

        all_data.append({
            "timestamp": timestamps[i].isoformat(),
            "pompe_id": pompe_id,
            "T_moteur": temp_moteur[i],
            "T_ambiante": round(temp_ambiante[i], 2),
            "humidite": humidite[i],
            "delta_T": round(delta_t, 2),
            "health_score": health,
            "pente": pente,
            "rul_minutes": rul,
            "condition_env": condition,
            "label": labels[i]
        })

print(f"\nTotal: {len(all_data)} lignes generees")

# ============================================================
# SAUVEGARDE
# ============================================================
output_dir = os.path.dirname(os.path.abspath(__file__))
df = pd.DataFrame(all_data)

# CSV
csv_path = os.path.join(output_dir, "training_data.csv")
df.to_csv(csv_path, index=False)
print(f"Fichier CSV: {csv_path} ({os.path.getsize(csv_path) / 1024 / 1024:.1f} MB)")

# Excel
excel_path = os.path.join(output_dir, "training_data.xlsx")
with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
    for pompe_id in range(1, NB_POMPES + 1):
        pompe_df = df[df["pompe_id"] == pompe_id].reset_index(drop=True)
        pompe_df.to_excel(writer, sheet_name=f'Pompe_{pompe_id}', index=False)
print(f"Fichier Excel: {excel_path} ({os.path.getsize(excel_path) / 1024 / 1024:.1f} MB)")

# ============================================================
# STATISTIQUES
# ============================================================
print("\n" + "=" * 60)
print("  STATISTIQUES PAR POMPE")
print("=" * 60)

for pompe_id in range(1, NB_POMPES + 1):
    pompe_data = df[df["pompe_id"] == pompe_id]
    nom = scenarios[pompe_id][0]
    normal = (pompe_data["label"] == 0).sum()
    anomalie = (pompe_data["label"] == 1).sum()
    critique = (pompe_data["label"] == 2).sum()
    print(f"\n  Pompe {pompe_id} - {nom}:")
    print(f"    Normal:   {normal:>6} ({normal/len(pompe_data)*100:.1f}%)")
    print(f"    Anomalie: {anomalie:>6} ({anomalie/len(pompe_data)*100:.1f}%)")
    print(f"    Critique: {critique:>6} ({critique/len(pompe_data)*100:.1f}%)")
    print(f"    T_moteur: min={pompe_data['T_moteur'].min():.1f}  max={pompe_data['T_moteur'].max():.1f}  moy={pompe_data['T_moteur'].mean():.1f}")
    print(f"    Delta T:  min={pompe_data['delta_T'].min():.1f}  max={pompe_data['delta_T'].max():.1f}  moy={pompe_data['delta_T'].mean():.1f}")

print("\n" + "=" * 60)
print("  STATISTIQUES PAR CONDITION ENVIRONNEMENTALE")
print("=" * 60)

conditions_labels = {
    "ete": "ETE (ambiante elevee, jours 1-8)",
    "humidite": "HUMIDITE ELEVEE (80-95%, jours 9-14)",
    "poussiere": "POUSSIERE (refroidissement reduit, jours 15-21)",
    "hiver": "HIVER (ambiante basse, jours 22-30)",
}

for cond, desc in conditions_labels.items():
    cond_data = df[df["condition_env"] == cond]
    print(f"\n  {desc}:")
    print(f"    Points:     {len(cond_data)}")
    print(f"    T_ambiante: min={cond_data['T_ambiante'].min():.1f}  max={cond_data['T_ambiante'].max():.1f}  moy={cond_data['T_ambiante'].mean():.1f}")
    print(f"    T_moteur:   min={cond_data['T_moteur'].min():.1f}  max={cond_data['T_moteur'].max():.1f}  moy={cond_data['T_moteur'].mean():.1f}")
    print(f"    Delta T:    min={cond_data['delta_T'].min():.1f}  max={cond_data['delta_T'].max():.1f}  moy={cond_data['delta_T'].mean():.1f}")
    print(f"    Humidite:   min={cond_data['humidite'].min():.1f}  max={cond_data['humidite'].max():.1f}  moy={cond_data['humidite'].mean():.1f}")

print("\n" + "=" * 60)
print("  RESUME")
print("=" * 60)
print()
print("  5 SCENARIOS PRINCIPAUX:")
print("    Pompe 1: Fonctionnement normal (regime stable)")
print("    Pompe 2: Demarrage moteur (cycles marche/arret)")
print("    Pompe 3: Arret moteur (arrets prolonges + redemarrage)")
print("    Pompe 4: Surcharge progressive (usure roulements)")
print("    Pompe 5: Surchauffe critique (blocage/perte ventilation)")
print()
print("  4 EFFETS ENVIRONNEMENTAUX (sur toutes les pompes):")
print("    Jours 1-8   : Ete - moteur +3 C (refroidissement moins efficace)")
print("    Jours 9-14  : Humidite 80-95% - moteur +2 C (corrosion roulements)")
print("    Jours 15-21 : Poussiere - moteur +4-7 C (ailettes colmatees)")
print("    Jours 22-30 : Hiver - moteur -1.5 C (bon refroidissement)")
print()
print("  Labels: 0=Normal, 1=Anomalie, 2=Critique")
print()
print("  Pret pour l'entrainement: python3 ml/train_model_rpi.py")
print("=" * 60)
