let wifiRadarChart = null;
let lastHumanAnnouncement = 0;
let radarAlertActive = false;

function _safeSpeak(text) {
    if (!window.speechSynthesis || !text || text.trim().length === 0) {
        return;
    }

    const now = Date.now();
    if (now - lastHumanAnnouncement < 9000) {
        return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'es-ES';
    utterance.rate = 1.0;
    utterance.pitch = 0.95;
    utterance.volume = 0.9;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    lastHumanAnnouncement = now;
}

function _normalizeSignal(dbmValue) {
    return Math.round(Math.max(0, Math.min(100, 100 + dbmValue)));
}

function _buildRadarPayload(data) {
    return [
        _normalizeSignal(data.nodes.ALPHA),
        _normalizeSignal(data.nodes.BETA),
        _normalizeSignal(data.nodes.GAMMA),
        _normalizeSignal(data.nodes.DELTA),
        Math.round(data.perturbation_index),
        Math.round(data.link_quality)
    ];
}

function _applyRadarThreatStyle(data) {
    if (!wifiRadarChart || !wifiRadarChart.data || !wifiRadarChart.data.datasets) return;

    const perturbation = data.perturbation_index || 0;
    const isHighThreat = perturbation > 55;
    const dataset = wifiRadarChart.data.datasets[0];

    if (isHighThreat && !radarAlertActive) {
        radarAlertActive = true;
        dataset.fill = true;
        dataset.backgroundColor = 'rgba(255, 51, 102, 0.25)';
        dataset.borderColor = 'rgba(255, 51, 102, 1)';
        dataset.pointBackgroundColor = 'rgba(255, 51, 102, 1)';
        dataset.pointBorderColor = '#ff3366';
        document.getElementById('tacticalChart').style.animation = 'pulse-radar 0.8s ease-in-out infinite';
        wifiRadarChart.update('active');
    } else if (!isHighThreat && radarAlertActive) {
        radarAlertActive = false;
        dataset.fill = true;
        dataset.backgroundColor = 'rgba(0, 212, 255, 0.14)';
        dataset.borderColor = 'rgba(0, 212, 255, 0.95)';
        dataset.pointBackgroundColor = 'rgba(124, 92, 252, 0.95)';
        dataset.pointBorderColor = '#7c5cfc';
        document.getElementById('tacticalChart').style.animation = 'none';
        wifiRadarChart.update('active');
    }
}

function createWiFiRadarChart() {
    const canvas = document.getElementById('tacticalChart');
    if (!canvas) {
        return;
    }

    const ctx = canvas.getContext('2d');
    if (wifiRadarChart) {
        wifiRadarChart.destroy();
    }

    const style = document.createElement('style');
    style.textContent = `
        @keyframes pulse-radar {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
    `;
    document.head.appendChild(style);

    wifiRadarChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['ALPHA', 'BETA', 'GAMMA', 'DELTA', 'PERTURB', 'LINK'],
            datasets: [{
                label: 'CSI Signal Map',
                data: [0, 0, 0, 0, 0, 0],
                fill: true,
                backgroundColor: 'rgba(0, 212, 255, 0.14)',
                borderColor: 'rgba(0, 212, 255, 0.95)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(124, 92, 252, 0.95)',
                pointBorderColor: '#7c5cfc',
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(90, 106, 138, 0.18)', circular: true },
                    angleLines: { color: 'rgba(90, 106, 138, 0.18)' },
                    pointLabels: { color: '#9ba3c4', font: { family: 'JetBrains Mono', size: 9 } },
                    ticks: { color: '#7a89a2', backdropColor: 'transparent', stepSize: 20, font: { size: 8 } }
                }
            }
        }
    });
}

function updateWiFiMetrics(data) {
    const mThreat = document.getElementById('mThreat');
    const mVolume = document.getElementById('mVolume');
    const mAnomalies = document.getElementById('mAnomalies');
    if (mThreat) {
        mThreat.textContent = `${Math.round(data.perturbation_index)}%`;
        mThreat.style.color = data.perturbation_index > 65 ? 'var(--red)' : data.perturbation_index > 40 ? 'var(--yellow)' : 'var(--green)';
    }
    if (mVolume) {
        mVolume.textContent = `${data.carrier_freq.toFixed(3)} GHz`;
    }
    if (mAnomalies) {
        mAnomalies.textContent = `${data.active_channels.length} chans`;
    }
}

function updateWiFiRadarChart(data) {
    if (!wifiRadarChart) {
        createWiFiRadarChart();
    }
    if (!wifiRadarChart) {
        return;
    }

    const payload = _buildRadarPayload(data);
    wifiRadarChart.data.datasets[0].data = payload;
    _applyRadarThreatStyle(data);
    updateWiFiMetrics(data);
}

function announceHumanPresence(data) {
    if (!data || !data.is_human) {
        return;
    }

    const message = `AURA alerta. Presencia humana detectada en el radar CSI. Perturbación ${Math.round(data.perturbation_index)} por ciento, calidad de enlace ${Math.round(data.link_quality)}.`;
    _safeSpeak(message);
}

window.addEventListener('DOMContentLoaded', function () {
    createWiFiRadarChart();
});
