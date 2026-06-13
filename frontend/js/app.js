const API_BASE = "http://localhost:8000";

// API Actions
async function postAction(endpoint) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, { method: "POST" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        console.log(`Action ${endpoint} successful`);
    } catch (e) {
        console.error(`Failed to execute ${endpoint}:`, e);
    }
}

document.getElementById('btn-start').addEventListener('click', () => postAction('/start'));
document.getElementById('btn-pause').addEventListener('click', () => postAction('/pause'));
document.getElementById('btn-reset').addEventListener('click', () => postAction('/reset'));
document.getElementById('btn-cloud-shock').addEventListener('click', () => postAction('/inject/cloud'));
document.getElementById('btn-wind-collapse').addEventListener('click', () => postAction('/inject/wind'));
document.getElementById('btn-pid-mode').addEventListener('click', () => postAction('/switch/pid'));

// Format numbers
function fmtNum(val, decimals = 2) {
    return parseFloat(val).toFixed(decimals);
}

// UI Updating
let previousLogLen = 0;

simStream.subscribe((state) => {
    // 1. KPI Strip
    const eastFreq = document.getElementById('kpi-east-freq');
    const westFreq = document.getElementById('kpi-west-freq');
    const riskBox = document.getElementById('kpi-blackout-risk');

    eastFreq.textContent = `${fmtNum(state.kpis.east_freq)} Hz`;
    westFreq.textContent = `${fmtNum(state.kpis.west_freq)} Hz`;
    document.getElementById('kpi-converter-util').textContent = `${fmtNum(state.kpis.converter_utilization * 100, 1)}%`;
    document.getElementById('kpi-energy-traded').textContent = `${fmtNum(state.kpis.energy_traded_mwh, 1)}`;

    const riskPct = state.kpis.blackout_risk * 100;
    riskBox.textContent = `${fmtNum(riskPct, 0)}%`;

    // Risk Box Styling
    const riskContainer = riskBox.closest('.kpi-box');
    if (riskPct > 50) {
        riskContainer.style.borderColor = 'var(--color-danger)';
        riskBox.style.color = 'var(--color-danger)';
    } else if (riskPct > 10) {
        riskContainer.style.borderColor = 'var(--color-warning)';
        riskBox.style.color = 'var(--color-warning)';
    } else {
        riskContainer.style.borderColor = 'var(--color-success)';
        riskBox.style.color = 'var(--color-success)';
    }

    // Frequency color warnings
    eastFreq.style.color = Math.abs(state.kpis.east_freq - 50) > 0.1 ? 'var(--color-danger)' : 'var(--color-info)';
    westFreq.style.color = Math.abs(state.kpis.west_freq - 60) > 0.1 ? 'var(--color-danger)' : 'var(--color-info)';

    // 2. Terminals logs
    const logsContainer = document.getElementById('logs-container');
    const logs = state.logs;
    if (logs && logs.length > previousLogLen) {
        // Append new logs
        for (let i = previousLogLen; i < logs.length; i++) {
            const row = document.createElement('div');
            row.className = 'log-entry';

            const txt = logs[i];
            if (txt.includes('[Auction]')) row.classList.add('auction');
            else if (txt.includes('[Converter]')) row.classList.add('converter');
            else if (txt.includes('[Error]') || txt.includes('[Freq')) row.classList.add('warning');
            else row.classList.add('system');

            row.textContent = `> ${txt}`;
            logsContainer.appendChild(row);
        }
        logsContainer.scrollTop = logsContainer.scrollHeight;
        previousLogLen = logs.length;
    } else if (logs && logs.length < previousLogLen) {
        // Must have reset
        logsContainer.innerHTML = '';
        previousLogLen = 0;
    }
});
