Chart.defaults.color = '#9ca3af';
Chart.defaults.font.family = "'Inter', sans-serif";

const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    elements: { point: { radius: 0 }, line: { borderWidth: 2, tension: 0.2 } },
    plugins: { legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } } },
    scales: {
        x: { display: false },
        y: {
            grid: { color: 'rgba(255,255,255,0.05)' },
            border: { display: false }
        }
    }
};

// 1. Weather Chart
const ctxWeather = document.getElementById('weather-chart').getContext('2d');
const weatherChart = new Chart(ctxWeather, {
    type: 'line',
    data: {
        labels: [], datasets: [
            { label: 'Solar CF', borderColor: '#F59E0B', data: [] },
            { label: 'Wind CF', borderColor: '#38BDF8', data: [] }
        ]
    },
    options: { ...commonOptions, plugins: { legend: { position: 'bottom' } }, scales: { y: { min: 0, max: 1, ...commonOptions.scales.y, ticks: { callback: function(val) { return (val * 100).toFixed(0) + '%'; } } } } }
});

// 2. Frequency Chart
const ctxFreq = document.getElementById('freq-chart').getContext('2d');
const freqChart = new Chart(ctxFreq, {
    type: 'line',
    data: {
        labels: [], datasets: [
            { label: 'East (50Hz)', borderColor: '#8B5CF6', data: [] },
            { label: 'West (60Hz)', borderColor: '#22C55E', data: [] }
        ]
    },
    options: { ...commonOptions, scales: { x: commonOptions.scales.x, y: { ...commonOptions.scales.y, ticks: { callback: function(val) { return val.toFixed(3) + ' Hz'; } } } } }
});

// 3. Converter Flow
const ctxConverter = document.getElementById('converter-chart').getContext('2d');
const converterChart = new Chart(ctxConverter, {
    type: 'bar',
    data: {
        labels: [], datasets: [
            { label: 'Flow MW (Pos=E->W, Neg=W->E)', backgroundColor: '#38BDF8', data: [] }
        ]
    },
    options: { ...commonOptions, scales: { x: commonOptions.scales.x, y: { ...commonOptions.scales.y, ticks: { callback: function(val) { return val.toFixed(1) + ' MW'; } } } } }
});

// 4. Market Pricing
const ctxMarket = document.getElementById('market-chart').getContext('2d');
const marketChart = new Chart(ctxMarket, {
    type: 'line',
    data: {
        labels: [], datasets: [
            { label: 'Price East ($)', borderColor: '#8B5CF6', data: [], type: 'line' },
            { label: 'Price West ($)', borderColor: '#22C55E', data: [], type: 'line' }
        ]
    },
    options: { ...commonOptions, scales: { x: commonOptions.scales.x, y: { ...commonOptions.scales.y, ticks: { callback: function(val) { return '$' + val.toFixed(2); } } } } }
});

// UPDATE LOGIC
simStream.subscribe((state) => {
    if (!state.history || !state.history.time) return;

    const h = state.history;

    // Freq Update (Zero center visually by subtracting nominal)
    freqChart.data.labels = h.time;
    freqChart.data.datasets[0].data = h.freq_east.map(f => f - 50.0);
    freqChart.data.datasets[1].data = h.freq_west.map(f => f - 60.0);
    freqChart.update();

    // Flow Update
    converterChart.data.labels = h.time;
    converterChart.data.datasets[0].data = h.hvdc_flow;
    converterChart.update();

    // Pricing Update
    marketChart.data.labels = h.time;
    marketChart.data.datasets[0].data = h.price_east;
    marketChart.data.datasets[1].data = h.price_west;
    marketChart.update();

    // Weather Update (We'll just map history to current state as a proxy if no history available)
    if (weatherChart.data.labels.length > 50) {
        weatherChart.data.labels.shift();
        weatherChart.data.datasets[0].data.shift();
        weatherChart.data.datasets[1].data.shift();
    }
    weatherChart.data.labels.push(state.tick);
    // Rough estimate since history doesn't pack raw CF easily 
    const curEastCf = state.weather.solar_cf_east;
    const curWindCf = state.weather.wind_cf_east;
    weatherChart.data.datasets[0].data.push(curEastCf);
    weatherChart.data.datasets[1].data.push(curWindCf);
    weatherChart.update();
});
