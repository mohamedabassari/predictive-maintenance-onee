var deltaT = msg.deltaT;
var pente = msg.pente;
var pompeId = msg.pompe_id;
var tempMoteur = msg.temperature;
var ambiance = msg.ambiance;

// === HEALTH SCORE (0-100) ===
var score = 100;

if (deltaT <= 15) {
    score = 100;
} else if (deltaT <= 30) {
    score = 100 - ((deltaT - 15) / 15) * 20;
} else if (deltaT <= 45) {
    score = 80 - ((deltaT - 30) / 15) * 30;
} else if (deltaT <= 60) {
    score = 50 - ((deltaT - 45) / 15) * 30;
} else {
    score = 20 - ((deltaT - 60) / 20) * 20;
}

if (pente > 0.5) {
    score -= pente * 10;
}

score = Math.max(0, Math.min(100, Math.round(score)));

// === RUL (minutes avant seuil critique) ===
var seuilCritique = 70;
var rul = null;

if (pente > 0.1) {
    var reste = seuilCritique - deltaT;
    if (reste > 0) {
        rul = Math.round(reste / pente);
    } else {
        rul = 0;
    }
} else {
    rul = -1;
}

// === NIVEAU ===
var niveau;
if (score >= 80) niveau = 'NORMAL';
else if (score >= 50) niveau = 'ATTENTION';
else if (score >= 20) niveau = 'ALERTE';
else niveau = 'CRITIQUE';

// Stocker pour contexte
var scores = flow.get('health_scores') || {};
scores[pompeId] = {
    score: score, deltaT: deltaT, pente: pente,
    rul: rul, niveau: niveau, temperature: tempMoteur,
    timestamp: Date.now()
};
flow.set('health_scores', scores);

// === SORTIE 1 : Gauge Health ===
var msg1 = {
    payload: score,
    topic: 'Pompe ' + pompeId,
    pompe_id: pompeId
};

// === SORTIE 2 : RUL texte ===
var rulText;
if (rul === -1) rulText = 'Stable';
else if (rul === 0) rulText = 'CRITIQUE!';
else if (rul >= 60) rulText = Math.floor(rul/60) + 'h' + (rul%60) + 'min';
else if (rul > 0) rulText = rul + ' min';
else rulText = 'N/A';

var msg2 = {
    payload: 'P' + pompeId + ': ' + rulText,
    topic: 'Pompe ' + pompeId
};

// === SORTIE 3 : Alerte ===
var msg3 = null;
if (niveau === 'ALERTE' || niveau === 'CRITIQUE') {
    msg3 = {
        payload: 'POMPE ' + pompeId + ' - ' + niveau + ' | Score: ' + score + '/100 | Delta T: ' + deltaT + ' C | RUL: ' + rulText,
        topic: 'alerte',
        pompe_id: pompeId,
        niveau: niveau
    };
}

// === SORTIE 4 : InfluxDB ===
var msg4 = {
    measurement: 'temperature_moteur',
    payload: {
        T_moteur: tempMoteur,
        T_ambiante: ambiance,
        delta_T: deltaT,
        health_score: score,
        pente: pente,
        rul_minutes: (rul !== null && rul >= 0) ? rul : 0
    },
    tags: {
        pompe_id: 'pompe_' + pompeId
    }
};

// === SORTIE 5 : MQTT vers ML Python ===
var msg5 = {
    payload: JSON.stringify({
        pompe_id: pompeId,
        T_moteur: tempMoteur,
        T_ambiante: ambiance,
        delta_T: deltaT,
        health_score: score,
        pente: pente,
        rul_minutes: rul,
        niveau: niveau,
        timestamp: Date.now()
    }),
    topic: 'station/pompe/' + pompeId + '/analyse'
};

// === Partager avec l'API REST via global ===
var pompesData = global.get('pompes_data') || {};
pompesData["pompe_" + pompeId] = {
    T_moteur: tempMoteur,
    T_ambiante: ambiance,
    delta_T: deltaT,
    health_score: score,
    pente: pente,
    rul_minutes: rul
};
global.set('pompes_data', pompesData);

return [msg1, msg2, msg3, msg4, msg5];
