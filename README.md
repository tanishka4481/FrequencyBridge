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

# Copy config template
cp config/settings.example.toml config/settings.toml
```

### Run

```bash
# Run validation spike (Phase 1)
python scripts/run_validation_spike.py

# Run auction scenario tests (Phase 3)
python scripts/run_auction_scenarios.py

# Run full 24h simulation (Phase 5)
python scripts/run_full_sim.py

# Launch dashboard (Phase 6)
streamlit run src/dashboard/app.py
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
└── dashboard/        # Streamlit visualization
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
| Converter capacity | 300 MW | Fixed physical constraint |
| Transmission loss | 2% | Applied to cross-region trades |
| Hedge trigger | 65% P(blackout) | Demo-tuned, not LOLE-derived |
| Emergency threshold | 73% P(blackout) | Demo-tuned |
| Tick duration | 30s grid time | Configurable in settings.toml |

---

## License

MIT
