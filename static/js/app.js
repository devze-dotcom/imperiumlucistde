/**
 * Imperium Lucis - Dashboard de Telemetria Ultrassônica (HC-SR04)
 * Gerencia a comunicação assíncrona com a API Flask e atualiza os elementos visuais.
 */

// Estado da Aplicação
const appState = {
    isPaused: false,
    pollIntervalMs: 1000,
    pollTimerId: null,
    chartInstance: null,
    lastEpochSeen: null
};

// Inicialização após o DOM carregar
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initChart();
    initControls();
    startPolling();
});

/* ==========================================================================
   Relógio do Sistema
   ========================================================================== */
function initClock() {
    const clockEl = document.getElementById('systemClock');
    function updateClock() {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString('pt-BR');
    }
    updateClock();
    setInterval(updateClock, 1000);
}

/* ==========================================================================
   Inicialização do Gráfico (Chart.js)
   ========================================================================== */
function initChart() {
    const ctx = document.getElementById('telemetryChart').getContext('2d');

    // Gradiente para a área sob a curva
    const gradient = ctx.createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, 'rgba(6, 182, 212, 0.4)');
    gradient.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

    appState.chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Distância (cm)',
                data: [],
                borderColor: '#06b6d4',
                backgroundColor: gradient,
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointRadius: 3,
                pointHoverRadius: 6,
                pointBackgroundColor: '#06b6d4',
                pointBorderColor: '#fff',
                pointBorderWidth: 1.5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 300
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 10,
                    callbacks: {
                        label: (item) => ` ${item.parsed.y.toFixed(1)} cm`
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 11
                        },
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 8
                    }
                },
                y: {
                    beginAtZero: true,
                    suggestedMax: 100,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 11
                        },
                        callback: (value) => `${value} cm`
                    }
                }
            }
        }
    });
}

/* ==========================================================================
   Controles do Dashboard
   ========================================================================== */
function initControls() {
    const btnPause = document.getElementById('btnPause');
    btnPause.addEventListener('click', () => {
        appState.isPaused = !appState.isPaused;
        if (appState.isPaused) {
            btnPause.textContent = 'Retomar';
            btnPause.classList.add('active');
        } else {
            btnPause.textContent = 'Pausar';
            btnPause.classList.remove('active');
            fetchTelemetry();
        }
    });
}

/* ==========================================================================
   Comunicação com a API (Polling)
   ========================================================================== */
function startPolling() {
    fetchTelemetry();
    appState.pollTimerId = setInterval(() => {
        if (!appState.isPaused) {
            fetchTelemetry();
        }
    }, appState.pollIntervalMs);
}

async function fetchTelemetry() {
    try {
        const response = await fetch('/api/sensor', {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        updateUI(data);
    } catch (err) {
        console.warn('Falha na comunicação com API:', err);
        setOfflineState();
    }
}

/* ==========================================================================
   Atualização dos Componentes Visuais
   ========================================================================== */
function updateUI(data) {
    const { online, atual, estatisticas, historico, segundos_desde_ultimo } = data;

    // 1. Atualizar Status de Conexão no Header
    const statusContainer = document.getElementById('connectionStatus');
    const statusLabel = statusContainer.querySelector('.status-label');

    if (online) {
        statusContainer.className = 'status-indicator status-online';
        statusLabel.textContent = 'Arduino Conectado';
    } else if (atual.distancia !== null) {
        statusContainer.className = 'status-indicator status-waiting';
        const atraso = segundos_desde_ultimo ? `há ${Math.round(segundos_desde_ultimo)}s` : '';
        statusLabel.textContent = `Sem novas leituras ${atraso}`;
    } else {
        statusContainer.className = 'status-indicator status-waiting';
        statusLabel.textContent = 'Aguardando dados...';
    }

    // 2. Atualizar Sensor e Distância Atual
    const distanceNumberEl = document.getElementById('currentDistance');
    const sensorIdLabel = document.getElementById('sensorIdLabel');
    const lastUpdated = document.getElementById('lastUpdated');

    if (atual.distancia !== null) {
        distanceNumberEl.textContent = Number(atual.distancia).toFixed(1);
        sensorIdLabel.textContent = `Sensor: ${atual.sensorId || 'sensor_porta'}`;
        lastUpdated.textContent = atual.timestamp || '--:--:--';
        updateProximityMeter(atual.distancia);
    } else {
        distanceNumberEl.textContent = '--';
        sensorIdLabel.textContent = 'Sensor: --';
        lastUpdated.textContent = '--';
    }

    // 3. Atualizar Cards de Estatísticas
    document.getElementById('statMin').textContent = estatisticas.min !== null ? estatisticas.min.toFixed(1) : '--';
    document.getElementById('statAvg').textContent = estatisticas.media > 0 ? estatisticas.media.toFixed(1) : '--';
    document.getElementById('statMax').textContent = estatisticas.max !== null ? estatisticas.max.toFixed(1) : '--';
    document.getElementById('statTotal').textContent = estatisticas.total || 0;

    // 4. Atualizar Gráfico e Tabela com o Histórico
    if (historico && historico.length > 0) {
        updateChart(historico);
        updateTable(historico);
    }
}

function updateProximityMeter(distancia) {
    const meterFill = document.getElementById('meterFill');
    const statePill = document.getElementById('proximityState');

    // Mapeia 0cm a 150cm para 0% a 100% de largura
    const percent = Math.min(Math.max((distancia / 150) * 100, 4), 100);
    meterFill.style.width = `${percent}%`;

    if (distancia < 20.0) {
        meterFill.style.backgroundColor = 'var(--color-danger)';
        statePill.className = 'proximity-state-pill state-critical';
        statePill.innerHTML = `⚠️ Alerta Crítico &bull; Objeto muito próximo (&lt; 20 cm)`;
    } else if (distancia <= 60.0) {
        meterFill.style.backgroundColor = 'var(--color-warning)';
        statePill.className = 'proximity-state-pill state-warning';
        statePill.innerHTML = `⚡ Atenção &bull; Proximidade média (${distancia.toFixed(1)} cm)`;
    } else {
        meterFill.style.backgroundColor = 'var(--color-success)';
        statePill.className = 'proximity-state-pill state-safe';
        statePill.innerHTML = `✅ Área Livre &bull; Distância segura (${distancia.toFixed(1)} cm)`;
    }
}

function updateChart(historico) {
    if (!appState.chartInstance) return;

    // Exibe até os últimos 25 pontos no gráfico para manter clareza visual
    const ultimosPontos = historico.slice(-25);

    const labels = ultimosPontos.map(p => p.timestamp);
    const data = ultimosPontos.map(p => p.distancia);

    appState.chartInstance.data.labels = labels;
    appState.chartInstance.data.datasets[0].data = data;
    appState.chartInstance.update();
}

function updateTable(historico) {
    const tbody = document.getElementById('telemetryTableBody');
    if (!tbody) return;

    // Exibe as últimas 10 leituras em ordem decrescente (mais recente no topo)
    const ultimasLeituras = [...historico].reverse().slice(0, 10);

    let html = '';
    for (const item of ultimasLeituras) {
        let statusBadge = '';
        if (item.distancia < 20.0) {
            statusBadge = '<span class="badge-status critical">Crítico (&lt;20cm)</span>';
        } else if (item.distancia <= 60.0) {
            statusBadge = '<span class="badge-status warning">Atenção (20-60cm)</span>';
        } else {
            statusBadge = '<span class="badge-status safe">Livre (&gt;60cm)</span>';
        }

        html += `
            <tr>
                <td>${item.timestamp}</td>
                <td><code>${item.sensorId || 'sensor_porta'}</code></td>
                <td><strong>${Number(item.distancia).toFixed(2)} cm</strong></td>
                <td>${statusBadge}</td>
            </tr>
        `;
    }

    tbody.innerHTML = html;
}

function setOfflineState() {
    const statusContainer = document.getElementById('connectionStatus');
    const statusLabel = statusContainer.querySelector('.status-label');
    statusContainer.className = 'status-indicator status-offline';
    statusLabel.textContent = 'API Inacessível';
}
