"""
Runner for the FreqBridge simulation.
Wraps the sequential FreqBridgeSimulation in an async loop for real-time frontend consumption.
"""

import asyncio
import time
from typing import Dict, Any, List

from src.sim.simulation_loop import FreqBridgeSimulation, SimulationConfig


class SimulationRunner:
    def __init__(self):
        self.sim = self._create_sim()
        self.is_running = False
        self.dt_seconds = 1.0  # Speed of simulation: 1 real second = 1 tick (5 mins simulation)
        self.task = None
        self.logs: List[str] = []
        
    def _create_sim(self) -> FreqBridgeSimulation:
        config = SimulationConfig(
            controller_type="market",
            total_ticks=9999999  # run forever until reset
        )
        return FreqBridgeSimulation(config)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self._loop())

    def pause(self):
        self.is_running = False
        if self.task is not None:
            self.task.cancel()
            self.task = None

    def reset(self):
        self.pause()
        self.sim = self._create_sim()
        self.logs.clear()
        self.add_log("[System] Simulation reset.")

    def inject_cloud_shock(self):
        self.sim.weather_gen_east.inject_shock(solar_shock=-0.8)
        self.sim.weather_gen_west.inject_shock(solar_shock=-0.8)
        self.add_log("[Weather] Cloud shock injected! Solar CF dropping.")

    def inject_wind_collapse(self):
        self.sim.weather_gen_east.inject_shock(wind_shock=-0.8)
        self.sim.weather_gen_west.inject_shock(wind_shock=-0.8)
        self.add_log("[Weather] Wind collapse injected! Wind CF dropping.")

    def switch_pid(self):
        self.sim.config.controller_type = "pid"
        self.add_log("[System] Switched to PID Baseline control mode.")

    def add_log(self, msg: str):
        self.logs.append(msg)
        if len(self.logs) > 100:
            self.logs.pop(0)

    async def _loop(self):
        while self.is_running:
            # Execute step
            try:
                self.sim.step()
                self._generate_step_logs()
            except Exception as e:
                self.add_log(f"[Error] Simulation Step Error: {e}")
                self.is_running = False
                break
                
            await asyncio.sleep(self.dt_seconds)

    def _generate_step_logs(self):
        if len(self.sim.history) == 0:
            return
        last_state = self.sim.history[-1]
        
        # Log market
        if last_state["trades_count"] > 0:
            self.add_log(f"[Auction] Matched {last_state['trades_count']} trades. Vol: {last_state['volume_cleared_mw']:.1f}MW")
            
        # Log flow
        flow = last_state["hvdc_flow_mw"]
        if abs(flow) > 10:
            direction = "East->West" if flow > 0 else "West->East"
            self.add_log(f"[Converter] Transfer {direction} at {abs(flow):.1f}MW")

        # Log frequency deviation
        f_east = last_state["freq_east"]
        f_west = last_state["freq_west"]
        if abs(f_east - 50.0) > 0.05:
            self.add_log(f"[Freq East] Warning: {f_east:.2f}Hz")
        if abs(f_west - 60.0) > 0.05:
            self.add_log(f"[Freq West] Warning: {f_west:.2f}Hz")

    def get_frontend_state(self) -> Dict[str, Any]:
        """Provides the aggregated state required by the frontend dashboard."""
        
        if len(self.sim.history) == 0:
            last = {
                "freq_east": 50.0, "freq_west": 60.0,
                "cf_east": 0.4, "cf_west": 0.4,
                "price_east": 30.0, "price_west": 30.0,
                "hvdc_flow_mw": 0.0,
                "trades_count": 0, "volume_cleared_mw": 0.0
            }
        else:
            last = self.sim.history[-1]

        # Extract agent states for topology visualization
        agents_data = []
        for a in self.sim.agents:
            # We determine pseudo-status (Green/Yellow/Red/Purple)
            # if generation < demand -> deficit
            gen = a.state.current_generation_mw if hasattr(a, 'state') and hasattr(a.state, 'current_generation_mw') else a.params.max_generation_mw * 0.4
            dem = a.state.current_demand_mw if hasattr(a, 'state') and hasattr(a.state, 'current_demand_mw') else a.params.base_demand_mw
            
            # Simple heuristic
            status = "Green"
            if gen < dem:
                status = "Red"
            elif gen < dem * 1.2:
                status = "Yellow"
                
            # If agent has a hedge flag (pseudo logic)
            if hasattr(a, 'risk_state') and getattr(a.risk_state, 'blackout_probability', 0) > 0.3:
                status = "Purple"

            agents_data.append({
                "id": a.params.id,
                "region": a.params.region,
                "generation_mw": gen,
                "demand_mw": dem,
                "status": status,
                "battery_mwh": a.state.battery_stored_mwh if hasattr(a, 'state') and hasattr(a.state, 'battery_stored_mwh') else 0.0,
            })

        # Calculate metrics over history
        history = self.sim.history
        total_energy_traded_mwh = sum(h.get("volume_cleared_mw", 0) * (self.sim.config.tick_length_minutes/60) for h in history)
        max_flow = self.sim.converter.params.capacity_mw
        utilization = abs(last["hvdc_flow_mw"]) / max_flow if max_flow > 0 else 0

        # Pseudo blackout risk (aggregate)
        red_agents = sum(1 for a in agents_data if a["status"] == "Red")
        blackout_risk = min(1.0, red_agents / len(agents_data)) if agents_data else 0.0
        
        # Recovery Time (estimate based on freq deviation threshold)
        recovery_time = 0.0
        
        return {
            "tick": self.sim.current_tick,
            "running": self.is_running,
            "mode": self.sim.config.controller_type,
            "kpis": {
                "east_freq": last["freq_east"],
                "west_freq": last["freq_west"],
                "converter_utilization": utilization,
                "energy_traded_mwh": total_energy_traded_mwh,
                "blackout_risk": blackout_risk,
                "recovery_time": recovery_time
            },
            "weather": {
                "solar_cf_east": last["cf_east"],  # Simple approximation
                "solar_cf_west": last["cf_west"],
                "wind_cf_east": last["cf_east"] * 0.9, # Assuming wind follows somewhat
                "wind_cf_west": last["cf_west"] * 0.9,
            },
            "market": {
                "price_east": last["price_east"] or 0.0,
                "price_west": last["price_west"] or 0.0,
            },
            "topology": {
                "converter": {
                    "flow_mw": last["hvdc_flow_mw"],
                    "utilization": utilization
                },
                "nodes": agents_data
            },
            "logs": self.logs[-20:], # Only send last 20 logs
            "history": {
                "freq_east": [h["freq_east"] for h in self.sim.history[-60:]],
                "freq_west": [h["freq_west"] for h in self.sim.history[-60:]],
                "price_east": [(h["price_east"] or 0.0) for h in self.sim.history[-60:]],
                "price_west": [(h["price_west"] or 0.0) for h in self.sim.history[-60:]],
                "hvdc_flow": [h["hvdc_flow_mw"] for h in self.sim.history[-60:]],
                "time": [h["tick"] for h in self.sim.history[-60:]]
            }
        }
