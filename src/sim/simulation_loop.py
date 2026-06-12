"""
Full System Simulation Loop for FreqBridge.

This module ties together the Physics ODE, Weather Generator, Microgrid Agents,
HVDC Converter, and the Double Auction Engine into a unified temporal loop.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
import numpy as np

from src.physics.frequency_model import FrequencyModel, TwoAreaParams
from src.physics.weather import WeatherGenerator, WeatherParams
from src.grid.converter import ConverterAgent, ConverterParams
from src.agents.microgrid_agent import MicroGridAgent, AgentParams
from src.market.auction_engine import AuctionEngine, Bid, Ask


@dataclass
class SimulationConfig:
    """Configuration for the overall simulation."""
    tick_length_minutes: float = 5.0
    total_ticks: int = 288  # 24 hours at 5-min ticks
    
    # "market" or "pid"
    controller_type: str = "market"
    
    # Economics
    price_ceiling: float = 100.0


class FreqBridgeSimulation:
    """Orchestrates the entire FreqBridge ecosystem."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.current_tick = 0
        self.history: List[Dict[str, Any]] = []

        # 1. Initialize ODE Physics
        self.freq_model = FrequencyModel()
        
        # 2. Initialize Weather
        # East: slightly more wind, less solar volatility. West: high solar volatility.
        self.weather_gen_east = WeatherGenerator(
            solar_params=WeatherParams(mean_reversion=0.1, long_term_mean=0.3, volatility=0.05),
            wind_params=WeatherParams(mean_reversion=0.05, long_term_mean=0.4, volatility=0.08)
        )
        self.weather_gen_west = WeatherGenerator(
            solar_params=WeatherParams(mean_reversion=0.08, long_term_mean=0.4, volatility=0.09),
            wind_params=WeatherParams(mean_reversion=0.1, long_term_mean=0.2, volatility=0.04)
        )
        
        # 3. Initialize Grid / Converter
        self.converter = ConverterAgent(ConverterParams(
            capacity_mw=300.0,
            loss_rate=0.02,
            ramp_rate_mw_per_tick=50.0
        ))
        
        # 4. Initialize Market
        self.auction_engine = AuctionEngine(price_ceiling=self.config.price_ceiling)
        
        # 5. Initialize Agents
        self.agents: List[MicroGridAgent] = []
        self._setup_default_agents()

    def _setup_default_agents(self):
        """Setup a baseline mix of East and West microgrids."""
        # East Agents
        self.agents.append(MicroGridAgent(AgentParams(
            id="East_City", region="east", max_generation_mw=100.0, base_demand_mw=80.0, 
            battery_capacity_mwh=50.0, max_charge_rate_mw=20.0, generation_cost_mwh=25.0
        )))
        self.agents.append(MicroGridAgent(AgentParams(
            id="East_Industrial", region="east", max_generation_mw=50.0, base_demand_mw=70.0, 
            battery_capacity_mwh=10.0, max_charge_rate_mw=5.0, generation_cost_mwh=30.0
        )))
        
        # West Agents
        self.agents.append(MicroGridAgent(AgentParams(
            id="West_SolarFarm", region="west", max_generation_mw=200.0, base_demand_mw=20.0, 
            battery_capacity_mwh=100.0, max_charge_rate_mw=50.0, generation_cost_mwh=10.0
        )))
        self.agents.append(MicroGridAgent(AgentParams(
            id="West_Residential", region="west", max_generation_mw=20.0, base_demand_mw=60.0, 
            battery_capacity_mwh=5.0, max_charge_rate_mw=2.0, generation_cost_mwh=40.0
        )))

    def step(self):
        """Execute one full tick of the simulation."""
        dt_mins = self.config.tick_length_minutes
        
        # 1. Update Weather
        w_east = self.weather_gen_east.step(dt_mins)
        w_west = self.weather_gen_west.step(dt_mins)
        
        # Combine wind/solar into a single CF for simplicity, or just use solar for this demo
        cf_east = (w_east.solar_cf + w_east.wind_cf) / 2.0
        cf_west = (w_west.solar_cf + w_west.wind_cf) / 2.0
        
        # 2. Update Agents and Collect Bids/Asks
        bids = []
        asks = []
        
        for agent in self.agents:
            # Inject regional weather CF
            agent_cf = cf_east if agent.params.region == "east" else cf_west
            agent.update_state(agent_cf, dt_mins / 60.0)
            
            # Estimate current price (we'll just use a trailing average or default for now)
            estimated_price = 30.0 
            
            bid = agent.generate_bid(estimated_price, self.config.price_ceiling)
            if bid:
                bids.append(Bid(**bid))
                
            ask = agent.generate_ask(estimated_price)
            if ask:
                asks.append(Ask(**ask))
                
        # 3. Run Auction or PID
        cap_e2w = self.converter.get_available_capacity("east_to_west")
        cap_w2e = self.converter.get_available_capacity("west_to_east")
        
        if self.config.controller_type == "market":
            result = self.auction_engine.clear_market(
                bids=bids, 
                asks=asks, 
                converter_available_east_to_west=cap_e2w,
                converter_available_west_to_east=cap_w2e,
                converter_loss_rate=self.converter.params.loss_rate
            )
            net_flow_request = result.converter_flow_mw
            trades_count = len(result.trades)
            volume_cleared_mw = result.total_volume_cleared_mw
            price_east = result.clearing_price_east
            price_west = result.clearing_price_west
        else:
            # PID Baseline mode
            from src.market.pid_baseline import PIDController
            if not hasattr(self, 'pid'):
                self.pid = PIDController()
                
            # Need current frequency to drive PID
            if hasattr(self, 'ode_state'):
                f_e = self.ode_state.freq_hz("east")
                f_w = self.ode_state.freq_hz("west")
            else:
                f_e, f_w = 50.0, 60.0
                
            net_flow_request = self.pid.compute_flow_command(f_e, f_w, dt_mins * 60.0)
            trades_count = 0
            volume_cleared_mw = abs(net_flow_request)
            price_east = None
            price_west = None
            
        # 4. Update Converter State
        # Determine net requested physical flow

        
        if net_flow_request > 0:
            # East to West flow
            actual_flow = self.converter.can_transfer(net_flow_request, "east_to_west")
            self.converter.execute_transfer(actual_flow, "east_to_west")
        elif net_flow_request < 0:
            # West to East flow
            actual_flow = self.converter.can_transfer(abs(net_flow_request), "west_to_east")
            self.converter.execute_transfer(actual_flow, "west_to_east")
        else:
            actual_flow = 0.0
            
        # 5. Apply Physics (ODE)
        # Convert the actual HVDC flow into per-unit power for the swing equation
        # Assume base MVA of 1000 for per-unit conversion
        base_mva = 1000.0
        
        # Convert to PU. Positive means East is sending to West (East loses power, West gains)
        # In our ODE: positive `converter_power_pu` means power moving East -> West
        pu_flow = (self.converter.current_transfer_mw) / base_mva
        
        # Determine net grid imbalances (Total Generation - Total Demand - Trades)
        # For a simplified ODE run, we just inject the converter flow as a disturbance
        # to see the micro-frequency effects of the trade execution.
        # A more complex model would track exactly which agent failed to buy power,
        # creating a local physical deficit (load shedding).
        
        # Run the ODE for a short burst (e.g. 10 seconds of physical time) 
        # to settle the new flow state.
        if not hasattr(self, 'ode_state'):
            from src.physics.frequency_model import SystemState
            self.ode_state = SystemState()
            
        from src.physics.frequency_model import Disturbance
        disturbance = Disturbance(east_pu=0.0, west_pu=0.0)

        self.ode_state = self.freq_model.simulate_step(
            state=self.ode_state,
            disturbance=disturbance,
            dt=10.0,
            converter_power_pu=pu_flow
        )
        
        # Record final settled frequencies for this tick
        east_freq = self.ode_state.freq_hz("east")
        west_freq = self.ode_state.freq_hz("west")
        
        # 6. Log state
        state = {
            "tick": self.current_tick,
            "cf_east": cf_east,
            "cf_west": cf_west,
            "trades_count": trades_count,
            "volume_cleared_mw": volume_cleared_mw,
            "hvdc_flow_mw": self.converter.current_transfer_mw,
            "price_east": price_east,
            "price_west": price_west,
            "freq_east": east_freq,
            "freq_west": west_freq
        }
        self.history.append(state)
        self.current_tick += 1

    def run(self):
        """Run the simulation for the configured number of ticks."""
        for _ in range(self.config.total_ticks):
            self.step()
