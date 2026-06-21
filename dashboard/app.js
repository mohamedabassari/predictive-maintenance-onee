// ============================================================
// CONFIGURATION
// ============================================================
const CONFIG = {
    API_BASE: 'http://192.168.137.5:1880',
    REFRESH_INTERVAL: 2000,
    HISTORY_POINTS: 120,
    SEUILS: {
        NORMAL: 80,
        ATTENTION: 50,
        ALERTE: 20
    }
};

// ============================================================
// ETAT GLOBAL
// ============================================================
let historique = {
    labels: [],
    deltaT: { pompe_1: [], pompe_2: [], pompe_3: [], pompe_4: [], pompe_5: [] },
    health: { pompe_1: [], pompe_2: [], pompe_3: [], pompe_4: [], pompe_5: [] },
    temps: { pompe_1: [], pompe_2: [], pompe_3: [], pompe_4: [], pompe_5: [] },
    pente: { pompe_1: [], pompe_2: [], pompe_3: [], pompe_4: [], pompe_5: [] }
};

let alertes = [];
let charts = {};
let startTime = Date.now();
let mlData = {};

// ============================================================
// INITIALISATION
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    genererCartesPompes();
    genererCartesML();
    initialiserGraphiques();
    demarrerHorloge();
    demarrerActualisation();
    demarrerActualisationML();
});

// ============================================================
// HORLOGE
// ============================================================
function demarrerHorloge() {
    mettreAJourHorloge();
    setInterval(mettreAJourHorloge, 1000);
}

function mettreAJourHorloge() {
    const now = new Date();
    document.getElementById('clockTime').textContent = now.toLocaleTimeString('fr-FR');
    document.getElementById('clockDate').textContent = now.toLocaleDateString('fr-FR', {
        weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
    });

    // Uptime
    const uptimeMs = Date.now() - startTime;
    const uptimeMin = Math.floor(uptimeMs / 60000);
    const uptimeH = Math.floor(uptimeMin / 60);
    const uptimeM = uptimeMin % 60;
    if (uptimeH > 0) {
        document.getElementById('summaryUptime').textContent = uptimeH + 'h' + uptimeM + 'm';
    } else {
        document.getElementById('summaryUptime').textContent = uptimeM + ' min';
    }
}

// ============================================================
// GENERATION DES CARTES POMPES
// ============================================================
function genererCartesPompes() {
    const grid = document.getElementById('pompesGrid');
    let html = '';

    for (let i = 1; i <= 5; i++) {
        html += `
        <div class="pompe-card normal" id="pompeCard${i}">
            <div class="pompe-header">
                <h3>Pompe ${i}</h3>
                <span class="pompe-badge badge-normal" id="badge${i}">Normal</span>
            </div>
            <div class="pompe-metrics">
                <div class="metric-row">
                    <span class="metric-label">T moteur</span>
                    <span class="metric-value" id="temp${i}">-- °C</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Delta T</span>
                    <span class="metric-value" id="delta${i}">-- °C</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Health Score</span>
                    <span class="metric-value" id="health${i}">--/100</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">RUL</span>
                    <span class="metric-value" id="rul${i}">--</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Pente</span>
                    <span class="metric-value" id="pente${i}">-- °C/min</span>
                </div>
            </div>
            <div class="health-bar">
                <div class="health-bar-fill good" id="healthBar${i}" style="width: 100%"></div>
            </div>
        </div>`;
    }

    grid.innerHTML = html;
}

// ============================================================
// GRAPHIQUES (Chart.js)
// ============================================================
const COULEURS_POMPES = [
    'rgba(76, 161, 255, 1)',
    'rgba(249, 115, 22, 1)',
    'rgba(52, 211, 153, 1)',
    'rgba(239, 68, 68, 1)',
    'rgba(167, 139, 250, 1)'
];

const COULEURS_POMPES_ALPHA = [
    'rgba(76, 161, 255, 0.08)',
    'rgba(249, 115, 22, 0.08)',
    'rgba(52, 211, 153, 0.08)',
    'rgba(239, 68, 68, 0.08)',
    'rgba(167, 139, 250, 0.08)'
];

function creerConfigChart(yMin, yMax) {
    return {
        type: 'line',
        data: {
            labels: [],
            datasets: Array.from({length: 5}, (_, i) => ({
                label: 'Pompe ' + (i + 1),
                data: [],
                borderColor: COULEURS_POMPES[i],
                backgroundColor: COULEURS_POMPES_ALPHA[i],
                borderWidth: 1.8,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.35,
                fill: true
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 200 },
            interaction: {
                mode: 'index',
                intersect: false
            },
            scales: {
                x: {
                    display: true,
                    grid: { color: 'rgba(36, 48, 64, 0.5)', drawBorder: false },
                    ticks: { color: '#4d5b69', maxTicksLimit: 6, font: { size: 10 } }
                },
                y: {
                    min: yMin,
                    max: yMax,
                    grid: { color: 'rgba(36, 48, 64, 0.5)', drawBorder: false },
                    ticks: { color: '#4d5b69', font: { size: 10 } }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#7d8b99',
                        boxWidth: 10,
                        boxHeight: 10,
                        padding: 12,
                        font: { size: 11 },
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 32, 0.95)',
                    borderColor: 'rgba(36, 48, 64, 1)',
                    borderWidth: 1,
                    titleFont: { size: 11 },
                    bodyFont: { size: 11 },
                    padding: 10,
                    cornerRadius: 8
                }
            }
        }
    };
}

function initialiserGraphiques() {
    charts.deltaT = new Chart(
        document.getElementById('chartDeltaT'),
        creerConfigChart(0, 80)
    );
    charts.health = new Chart(
        document.getElementById('chartHealth'),
        creerConfigChart(0, 100)
    );
    charts.temps = new Chart(
        document.getElementById('chartTemps'),
        creerConfigChart(0, 120)
    );
    charts.pente = new Chart(
        document.getElementById('chartPente'),
        creerConfigChart(-2, 5)
    );
}

// ============================================================
// ACTUALISATION DES DONNEES
// ============================================================
function demarrerActualisation() {
    actualiserDonnees();
    setInterval(actualiserDonnees, CONFIG.REFRESH_INTERVAL);
}

async function actualiserDonnees() {
    try {
        const response = await fetch(CONFIG.API_BASE + '/api/pt100');

        if (!response.ok) {
            setConnectionStatus('error', 'Erreur ' + response.status);
            return;
        }

        const data = await response.json();

        if (data.status !== 'ok') {
            setConnectionStatus('error', data.message || 'Erreur');
            return;
        }

        setConnectionStatus('connected', 'En ligne');
        mettreAJourInterface(data);

    } catch (err) {
        setConnectionStatus('error', 'Hors ligne');
    }
}

// ============================================================
// MISE A JOUR DE L'INTERFACE
// ============================================================
function mettreAJourInterface(data) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('fr-FR');
    document.getElementById('lastUpdateBadge').textContent = 'Derniere MAJ: ' + timeStr;

    const timeLabel = now.toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
    historique.labels.push(timeLabel);
    if (historique.labels.length > CONFIG.HISTORY_POINTS) {
        historique.labels.shift();
    }

    let compteurs = { normal: 0, attention: 0, alerte: 0, critique: 0 };
    let scoreTotal = 0;
    let scoreCount = 0;
    let ambiance = null;

    for (let i = 1; i <= 5; i++) {
        const key = 'pompe_' + i;
        const pompe = data.pompes[key];

        if (pompe) {
            mettreAJourCartePompe(i, pompe);
            ajouterPointHistorique(key, pompe);

            let niveau = determinerNiveau(pompe.health_score);
            compteurs[niveau]++;
            if (pompe.health_score !== null) {
                scoreTotal += pompe.health_score;
                scoreCount++;
            }
            if (pompe.T_ambiante !== null) ambiance = pompe.T_ambiante;
        } else {
            ajouterPointVide(key);
        }
    }

    // Resume global
    document.getElementById('summaryAmbiance').textContent = ambiance !== null ? ambiance.toFixed(1) + '°C' : '--°C';
    document.getElementById('summaryNormal').textContent = compteurs.normal;
    document.getElementById('summaryWarning').textContent = compteurs.attention;
    document.getElementById('summaryCritique').textContent = compteurs.alerte + compteurs.critique;
    document.getElementById('summaryScore').textContent = scoreCount > 0 ? Math.round(scoreTotal / scoreCount) + '/100' : '--';
    document.getElementById('alerteCount').textContent = alertes.length + ' alerte' + (alertes.length > 1 ? 's' : '');

    mettreAJourGraphiques();
}

function mettreAJourCartePompe(id, pompe) {
    const tMoteur = pompe.T_moteur;
    const deltaT = pompe.delta_T;
    const score = pompe.health_score;
    const pente = pompe.pente;
    const rul = pompe.rul_minutes;

    document.getElementById('temp' + id).textContent = tMoteur !== null ? tMoteur.toFixed(1) + ' °C' : '-- °C';
    document.getElementById('delta' + id).textContent = deltaT !== null ? deltaT.toFixed(1) + ' °C' : '-- °C';
    document.getElementById('health' + id).textContent = score !== null ? score + '/100' : '--/100';
    document.getElementById('pente' + id).textContent = pente !== null ? pente.toFixed(2) + ' °C/min' : '-- °C/min';

    let rulText = '--';
    if (rul === 0) rulText = 'CRITIQUE!';
    else if (rul > 0 && rul < 60) rulText = rul + ' min';
    else if (rul >= 60) rulText = Math.floor(rul / 60) + 'h' + (rul % 60) + 'min';
    else if (rul === -1 || rul === null) rulText = 'Stable';
    document.getElementById('rul' + id).textContent = rulText;

    let niveau = determinerNiveau(score);
    let card = document.getElementById('pompeCard' + id);
    let badge = document.getElementById('badge' + id);

    card.className = 'pompe-card ' + niveau;
    badge.className = 'pompe-badge badge-' + niveau;
    badge.textContent = niveau.charAt(0).toUpperCase() + niveau.slice(1);

    let bar = document.getElementById('healthBar' + id);
    bar.style.width = (score || 0) + '%';
    if (score >= 70) bar.className = 'health-bar-fill good';
    else if (score >= 50) bar.className = 'health-bar-fill warning';
    else if (score >= 20) bar.className = 'health-bar-fill danger';
    else bar.className = 'health-bar-fill critical';

    if (niveau === 'alerte' || niveau === 'critique') {
        ajouterAlerte(id, niveau, score, deltaT, rulText);
    }
}

function determinerNiveau(score) {
    if (score === null) return 'normal';
    if (score >= CONFIG.SEUILS.NORMAL) return 'normal';
    if (score >= CONFIG.SEUILS.ATTENTION) return 'attention';
    if (score >= CONFIG.SEUILS.ALERTE) return 'alerte';
    return 'critique';
}

// ============================================================
// HISTORIQUE ET GRAPHIQUES
// ============================================================
function ajouterPointHistorique(key, pompe) {
    historique.deltaT[key].push(pompe.delta_T);
    historique.health[key].push(pompe.health_score);
    historique.temps[key].push(pompe.T_moteur);
    historique.pente[key].push(pompe.pente);

    if (historique.deltaT[key].length > CONFIG.HISTORY_POINTS) {
        historique.deltaT[key].shift();
        historique.health[key].shift();
        historique.temps[key].shift();
        historique.pente[key].shift();
    }
}

function ajouterPointVide(key) {
    historique.deltaT[key].push(null);
    historique.health[key].push(null);
    historique.temps[key].push(null);
    historique.pente[key].push(null);

    if (historique.deltaT[key].length > CONFIG.HISTORY_POINTS) {
        historique.deltaT[key].shift();
        historique.health[key].shift();
        historique.temps[key].shift();
        historique.pente[key].shift();
    }
}

function mettreAJourGraphiques() {
    charts.deltaT.data.labels = historique.labels;
    for (let i = 0; i < 5; i++) {
        charts.deltaT.data.datasets[i].data = historique.deltaT['pompe_' + (i + 1)];
    }
    charts.deltaT.update('none');

    charts.health.data.labels = historique.labels;
    for (let i = 0; i < 5; i++) {
        charts.health.data.datasets[i].data = historique.health['pompe_' + (i + 1)];
    }
    charts.health.update('none');

    charts.temps.data.labels = historique.labels;
    for (let i = 0; i < 5; i++) {
        charts.temps.data.datasets[i].data = historique.temps['pompe_' + (i + 1)];
    }
    charts.temps.update('none');

    charts.pente.data.labels = historique.labels;
    for (let i = 0; i < 5; i++) {
        charts.pente.data.datasets[i].data = historique.pente['pompe_' + (i + 1)];
    }
    charts.pente.update('none');
}

// ============================================================
// ALERTES
// ============================================================
function ajouterAlerte(pompeId, niveau, score, deltaT, rul) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('fr-FR');

    const recent = alertes.find(a =>
        a.pompeId === pompeId &&
        (now - a.date) < 10000
    );
    if (recent) return;

    alertes.unshift({
        pompeId: pompeId,
        niveau: niveau,
        message: `Pompe ${pompeId} - ${niveau.toUpperCase()} | Score: ${score}/100 | Delta T: ${deltaT}°C | RUL: ${rul}`,
        time: timeStr,
        date: now
    });

    if (alertes.length > 50) alertes.pop();
    afficherAlertes();
}

function afficherAlertes() {
    const container = document.getElementById('alertesContainer');

    if (alertes.length === 0) {
        container.innerHTML = '<div class="alerte-empty">Aucune alerte pour le moment</div>';
        return;
    }

    let html = '';
    alertes.forEach(function(a) {
        const icon = a.niveau === 'critique' ? '!!' : '!';
        html += `
        <div class="alerte-item">
            <div class="alerte-icon ${a.niveau}">${icon}</div>
            <div class="alerte-content">
                <div class="alerte-message">${a.message}</div>
                <div class="alerte-time">${a.time}</div>
            </div>
        </div>`;
    });

    container.innerHTML = html;
}

// ============================================================
// PREDICTIONS ML
// ============================================================
function genererCartesML() {
    const grid = document.getElementById('mlGrid');
    let html = '';

    for (let i = 1; i <= 5; i++) {
        html += `
        <div class="ml-card" id="mlCard${i}">
            <div class="ml-card-header">
                <h4>Pompe ${i}</h4>
                <span class="ml-badge" id="mlBadge${i}">IA</span>
            </div>
            <div class="ml-metrics">
                <div class="ml-metric-row">
                    <span class="ml-metric-label">Anomalie</span>
                    <span class="ml-metric-value" id="mlAnomalie${i}">--%</span>
                </div>
                <div class="ml-metric-row">
                    <span class="ml-metric-label">Delta T predit</span>
                    <span class="ml-metric-value" id="mlDeltaPredit${i}">-- °C</span>
                </div>
                <div class="ml-metric-row">
                    <span class="ml-metric-label">Health predit</span>
                    <span class="ml-metric-value" id="mlHealthPredit${i}">--/100</span>
                </div>
                <div class="ml-metric-row">
                    <span class="ml-metric-label">RUL (IA)</span>
                    <span class="ml-metric-value" id="mlRul${i}">--</span>
                </div>
                <div class="ml-metric-row">
                    <span class="ml-metric-label">Tendance</span>
                    <span class="ml-metric-value" id="mlTendance${i}">--</span>
                </div>
            </div>
            <div class="ml-anomalie-bar">
                <div class="ml-anomalie-fill" id="mlAnomalieBar${i}" style="width: 0%"></div>
            </div>
        </div>`;
    }

    grid.innerHTML = html;
}

function demarrerActualisationML() {
    actualiserML();
    setInterval(actualiserML, 5000);
}

async function actualiserML() {
    try {
        const response = await fetch(CONFIG.API_BASE + '/api/ml/predictions');
        if (!response.ok) {
            document.getElementById('mlStatus').textContent = 'IA: Hors ligne';
            return;
        }

        const data = await response.json();

        if (!data.ml_active) {
            document.getElementById('mlStatus').textContent = 'IA: En attente';
            return;
        }

        document.getElementById('mlStatus').textContent = 'IA: Active';
        mlData = data.predictions;
        mettreAJourCartesML();

    } catch (err) {
        document.getElementById('mlStatus').textContent = 'IA: Hors ligne';
    }
}

function mettreAJourCartesML() {
    for (let i = 1; i <= 5; i++) {
        const key = 'pompe_' + i;
        const pred = mlData[key];

        if (!pred) {
            document.getElementById('mlAnomalie' + i).textContent = '--%';
            continue;
        }

        // Score anomalie
        const scoreAnomalie = Math.round((pred.score_anomalie || 0) * 100);
        document.getElementById('mlAnomalie' + i).textContent = scoreAnomalie + '%';

        // Delta T predit
        document.getElementById('mlDeltaPredit' + i).textContent =
            pred.delta_t_predit !== null ? pred.delta_t_predit.toFixed(1) + ' °C' : '-- °C';

        // Health predit
        document.getElementById('mlHealthPredit' + i).textContent =
            pred.health_predit !== null ? Math.round(pred.health_predit) + '/100' : '--/100';

        // RUL predit
        let rulText = 'Stable';
        if (pred.rul_predit === 0) rulText = 'CRITIQUE!';
        else if (pred.rul_predit > 0 && pred.rul_predit < 60) rulText = pred.rul_predit + ' min';
        else if (pred.rul_predit >= 60) rulText = Math.floor(pred.rul_predit / 60) + 'h' + (pred.rul_predit % 60) + 'min';
        document.getElementById('mlRul' + i).textContent = rulText;

        // Tendance
        const tendance = pred.tendance || 0;
        let tendanceText = tendance.toFixed(3) + ' °C';
        if (tendance > 0) tendanceText = '+' + tendanceText;
        document.getElementById('mlTendance' + i).textContent = tendanceText;

        // Badge et couleur
        const card = document.getElementById('mlCard' + i);
        const badge = document.getElementById('mlBadge' + i);
        const niveau = pred.niveau_ml || 'NORMAL';

        card.className = 'ml-card';
        badge.className = 'ml-badge';

        if (niveau === 'CRITIQUE') {
            card.classList.add('ml-critique');
            badge.classList.add('ml-badge-critique');
            badge.textContent = 'CRITIQUE';
        } else if (niveau === 'ALERTE') {
            card.classList.add('ml-alerte');
            badge.classList.add('ml-badge-alerte');
            badge.textContent = 'ALERTE';
        } else if (niveau === 'ATTENTION') {
            badge.textContent = 'ATTENTION';
        } else {
            badge.textContent = 'NORMAL';
        }

        // Barre anomalie
        const bar = document.getElementById('mlAnomalieBar' + i);
        bar.style.width = scoreAnomalie + '%';
    }
}

// ============================================================
// EXPORT EXCEL
// ============================================================
function exporterHistoriqueExcel() {
    const data = [];

    for (let idx = 0; idx < historique.labels.length; idx++) {
        for (let p = 1; p <= 5; p++) {
            const key = 'pompe_' + p;
            data.push({
                'Heure': historique.labels[idx],
                'Pompe': 'Pompe ' + p,
                'T_moteur (C)': historique.temps[key][idx],
                'Delta_T (C)': historique.deltaT[key][idx],
                'Health_Score': historique.health[key][idx],
                'Pente (C/min)': historique.pente[key][idx]
            });
        }
    }

    if (data.length === 0) {
        alert('Aucune donnee disponible. Attendez quelques secondes.');
        return;
    }

    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Historique');

    const now = new Date();
    const filename = 'historique_' + now.toISOString().slice(0, 10) + '_' +
        now.toLocaleTimeString('fr-FR').replace(/:/g, 'h') + '.xlsx';
    XLSX.writeFile(wb, filename);
}

function exporterPredictionsExcel() {
    const data = [];
    const now = new Date().toLocaleString('fr-FR');

    for (let p = 1; p <= 5; p++) {
        const key = 'pompe_' + p;
        const pred = mlData[key];

        if (pred) {
            data.push({
                'Date/Heure': now,
                'Pompe': 'Pompe ' + p,
                'Niveau IA': pred.niveau_ml || 'N/A',
                'Score Anomalie (%)': Math.round((pred.score_anomalie || 0) * 100),
                'Delta_T Predit (C)': pred.delta_t_predit,
                'Health Predit': pred.health_predit ? Math.round(pred.health_predit) : null,
                'RUL (min)': pred.rul_predit,
                'Tendance (C/min)': pred.tendance
            });
        } else {
            data.push({
                'Date/Heure': now,
                'Pompe': 'Pompe ' + p,
                'Niveau IA': 'Pas de donnees',
                'Score Anomalie (%)': null,
                'Delta_T Predit (C)': null,
                'Health Predit': null,
                'RUL (min)': null,
                'Tendance (C/min)': null
            });
        }
    }

    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Predictions IA');

    const filename = 'predictions_ia_' + new Date().toISOString().slice(0, 10) + '.xlsx';
    XLSX.writeFile(wb, filename);
}

function exporterAlertesExcel() {
    if (alertes.length === 0) {
        alert('Aucune alerte enregistree.');
        return;
    }

    const data = alertes.map(function(a) {
        return {
            'Heure': a.time,
            'Pompe': 'Pompe ' + a.pompeId,
            'Niveau': a.niveau.toUpperCase(),
            'Message': a.message
        };
    });

    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Alertes');

    const filename = 'alertes_' + new Date().toISOString().slice(0, 10) + '.xlsx';
    XLSX.writeFile(wb, filename);
}

function exporterRapportComplet() {
    const wb = XLSX.utils.book_new();
    const now = new Date().toLocaleString('fr-FR');

    // Onglet 1 : Resume
    const resume = [];
    for (let p = 1; p <= 5; p++) {
        const key = 'pompe_' + p;
        const lastIdx = historique.temps[key].length - 1;
        const pred = mlData[key];

        resume.push({
            'Pompe': 'Pompe ' + p,
            'T_moteur (C)': lastIdx >= 0 ? historique.temps[key][lastIdx] : null,
            'Delta_T (C)': lastIdx >= 0 ? historique.deltaT[key][lastIdx] : null,
            'Health_Score': lastIdx >= 0 ? historique.health[key][lastIdx] : null,
            'Pente (C/min)': lastIdx >= 0 ? historique.pente[key][lastIdx] : null,
            'Niveau IA': pred ? (pred.niveau_ml || 'N/A') : 'N/A',
            'Score Anomalie (%)': pred ? Math.round((pred.score_anomalie || 0) * 100) : null,
            'RUL (min)': pred ? pred.rul_predit : null,
            'Export': now
        });
    }
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(resume), 'Resume');

    // Onglet 2 : Historique par pompe
    for (let p = 1; p <= 5; p++) {
        const key = 'pompe_' + p;
        const pompeData = [];
        for (let idx = 0; idx < historique.labels.length; idx++) {
            pompeData.push({
                'Heure': historique.labels[idx],
                'T_moteur (C)': historique.temps[key][idx],
                'Delta_T (C)': historique.deltaT[key][idx],
                'Health_Score': historique.health[key][idx],
                'Pente (C/min)': historique.pente[key][idx]
            });
        }
        if (pompeData.length > 0) {
            XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(pompeData), 'Pompe_' + p);
        }
    }

    // Onglet : Predictions IA
    const predData = [];
    for (let p = 1; p <= 5; p++) {
        const key = 'pompe_' + p;
        const pred = mlData[key];
        if (pred) {
            predData.push({
                'Pompe': 'Pompe ' + p,
                'Niveau': pred.niveau_ml || 'N/A',
                'Score Anomalie (%)': Math.round((pred.score_anomalie || 0) * 100),
                'Delta_T Predit (C)': pred.delta_t_predit,
                'Health Predit': pred.health_predit ? Math.round(pred.health_predit) : null,
                'RUL (min)': pred.rul_predit,
                'Tendance (C/min)': pred.tendance
            });
        }
    }
    if (predData.length > 0) {
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(predData), 'Predictions_IA');
    }

    // Onglet : Alertes
    if (alertes.length > 0) {
        const alerteData = alertes.map(function(a) {
            return {
                'Heure': a.time,
                'Pompe': 'Pompe ' + a.pompeId,
                'Niveau': a.niveau.toUpperCase(),
                'Message': a.message
            };
        });
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(alerteData), 'Alertes');
    }

    const filename = 'rapport_complet_' + new Date().toISOString().slice(0, 10) + '.xlsx';
    XLSX.writeFile(wb, filename);
}

// ============================================================
// CONNEXION STATUS
// ============================================================
function setConnectionStatus(status, text) {
    const el = document.getElementById('connectionStatus');
    el.className = 'connection-status ' + status;
    el.querySelector('.text').textContent = text;
}
