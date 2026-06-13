# FreqBridge

**Autonomous Multi-Agent Energy Arbitrage Engine for Japan's Split Grid**

FreqBridge is a decentralized multi-agent system that eliminates the *decision-latency* bottleneck around Japan's fixed HVDC converter capacity between the eastern (50 Hz) and western (60 Hz) grids. Each microgrid operates as an autonomous agent — monitoring generation vs. demand, calculating break-even prices, executing trades through a double auction, hedging against weather volatility, and prioritizing grid survival over profit when blackout probability crosses a threshold.

---

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Setup

```bash
# Clone the repo
git clone <repo-url>
cd freqbridge

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt


### Run

```bash
# Run validation spike (Phase 1)
python scripts/run_validation_spike.py

# Run auction scenario tests (Phase 3)
python scripts/run_auction_scenarios.py

# Run full 24h simulation (Phase 5)
python scripts/run_full_sim.py

# Launch API Backend
python -m uvicorn src.backend.api:app --host 0.0.0.0 --port 8000

# Launch Frontend UI (in a new terminal)
cd frontend
python -m http.server 3000
```

### Tests

```bash
python -m pytest tests/ -v
```

---

## Architecture

```
src/
├── physics/          # Frequency ODE, weather generator
├── grid/             # Converter model, network topology
├── agents/           # Microgrid agents, hedging logic
├── market/           # Double auction engine, PID baseline
├── sim/              # Unified simulation loop
├── backend/          # FastAPI backend server
└── frontend/         # Vanilla HTML/CSS/JS dashboard
```

See [docs/architecture.md](docs/architecture.md) for detailed system design.

---

## Demo Scenes

1. **Normal State** — 5 microgrids live, all green, converter idle, prices flat
2. **Inject Crisis** — Cloud cover event triggers east-side deficit, auction clears, converter routes power
3. **Near Blackout Hedge** — Wind death predicted, west agents autonomously switch to survival mode
4. **Comparison** — FreqBridge recovers in ~12s vs PID baseline at ~47s

---

## Key Parameters

| Parameter | Value | Note |
|-----------|-------|------|
| Converter capacity | 1200 MW | Fixed physical constraint (1.2GW) |
| Transmission loss | 2% | Applied to cross-region trades |
| Hedge trigger | 70% P(blackout) | Demo-tuned threshold for SURVIVAL mode |
| Tick duration | 5m grid time | Configurable in settings.toml |

---

## License

MIT
