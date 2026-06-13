"""
MicroGrid Agent Model.

This module defines the autonomous MicroGridAgent. Each microgrid:
- Resides in either the East (50Hz) or West (60Hz) region.
- Monitors its own generation (influenced by weather) vs. demand.
- Manages a local battery storage system.
- Calculates its energy surplus or deficit.
- Generates market bids (to buy) or asks (to sell) based on its current state.
- Switches between 'profit' mode and 'survival' mode based on blackout risk.
"""

from dataclasses import dataclass
from typing import Optional, List

from src.agents.hedging import BlackoutPredictor


@dataclass
class AgentParams:
    """Static parameters for a MicroGridAgent."""
    id: str
    region: str                # "east" or "west"
    max_generation_mw: float   # Max possible generation under perfect weather
    base_demand_mw: float      # Baseline demand
    battery_capacity_mwh: float# Maximum battery storage capacity
    max_charge_rate_mw: float  # Max rate battery can charge/discharge
    
    # Economics
    generation_cost_mwh: float # Cost to generate 1 MWh locally


class MicroGridAgent:
    """
    Autonomous microgrid agent that manages local energy and trades on the market.
    """

    def __init__(self, params: AgentParams):
        self.params = params
        self.predictor = BlackoutPredictor(lookahead_ticks=12)
        
        # Dynamic State
        self.current_generation_mw = 0.0
        self.current_demand_mw = params.base_demand_mw
        self.battery_energy_mwh = params.battery_capacity_mwh * 0.5  # Start at 50% SOC
        
        # Operating Mode
        self.mode = "profit"       # "profit" or "survival"
        self.hedge_buffer_mwh = 0.0 # Energy reserved when in survival mode
        self.ticks_since_mode_switch = 0
        self.mode_cooldown_ticks = 3 # Lock mode for at least 3 ticks (15 mins) to prevent hardware chatter

    @property
    def battery_soc(self) -> float:
        """State of Charge (0.0 to 1.0)."""
        if self.params.battery_capacity_mwh == 0:
            return 0.0
        return self.battery_energy_mwh / self.params.battery_capacity_mwh

    def update_state(self, weather_cf: float, dt_hours: float):
        """
        Update generation based on weather, and step the battery state.
        
        Args:
            weather_cf: Current weather capacity factor (0.0 to 1.0)
            dt_hours: Time elapsed in hours since last update
        """
        # Generation is strictly tied to weather in this model
        self.current_generation_mw = self.params.max_generation_mw * weather_cf
        
        # In a real system, demand might also be stochastic, but we keep it static for the baseline
        # self.current_demand_mw = ...

    def evaluate_risk(self, forecast_cf: List[float]):
        """
        Evaluate future blackout probability and switch modes if necessary.
        
        Args:
            forecast_cf: List of expected capacity factors for upcoming ticks
        """
        expected_gen = [self.params.max_generation_mw * cf for cf in forecast_cf]
        expected_dem = [self.current_demand_mw] * len(forecast_cf)
        
        prob = self.predictor.calculate_probability(expected_gen, expected_dem, self.battery_soc)
        
        new_mode, required_buffer = self.predictor.determine_mode(prob)
        
        self.ticks_since_mode_switch += 1
        current_mode_str = "survival" if self.mode == "survival" else "profit"
        
        if new_mode != current_mode_str:
            if self.ticks_since_mode_switch >= self.mode_cooldown_ticks:
                self.set_survival_mode(new_mode == "survival", required_buffer)
                self.ticks_since_mode_switch = 0

    def calculate_surplus(self) -> float:
        """
        Calculate current energy surplus or deficit.
        
        Returns:
            Positive MW if in surplus (generation > demand).
            Negative MW if in deficit (generation < demand).
        """
        return self.current_generation_mw - self.current_demand_mw

    def generate_ask(self, current_price_estimate: float) -> Optional[dict]:
        """
        Generate an offer to SELL power (Ask) if in surplus.
        
        Args:
            current_price_estimate: Estimate of current market price
            
        Returns:
            Dictionary with ask details or None if unable/unwilling to sell.
        """
        surplus_mw = self.calculate_surplus()
        
        if surplus_mw <= 0:
            return None  # No surplus to sell
            
        # If in survival mode, we might hoard energy instead of selling
        if self.mode == "survival" and self.battery_energy_mwh < self.hedge_buffer_mwh:
            return None
            
        # We can sell our current generation surplus.
        # Break-even price is our generation cost. We try to sell slightly above it.
        offer_price = max(self.params.generation_cost_mwh * 1.1, current_price_estimate * 0.9)
        
        return {
            "agent_id": self.params.id,
            "region": self.params.region,
            "volume_mw": surplus_mw,
            "price": offer_price
        }

    def generate_bid(self, current_price_estimate: float, price_ceiling: float) -> Optional[dict]:
        """
        Generate an offer to BUY power (Bid) if in deficit.
        
        Args:
            current_price_estimate: Estimate of current market price
            price_ceiling: Maximum allowed market price
            
        Returns:
            Dictionary with bid details or None if not in deficit.
        """
        surplus_mw = self.calculate_surplus()
        
        if surplus_mw >= 0:
            return None  # No deficit, no need to buy
            
        deficit_mw = -surplus_mw
        
        # We are willing to pay up to the price ceiling to avoid a local blackout
        bid_price = min(price_ceiling, current_price_estimate * 1.2)
        
        # In survival mode, we bid aggressively to fill the hedge buffer
        if self.mode == "survival":
            bid_price = price_ceiling
            
        return {
            "agent_id": self.params.id,
            "region": self.params.region,
            "volume_mw": deficit_mw,
            "price": bid_price
        }

    def set_survival_mode(self, active: bool, buffer_requirement_mwh: float = 0.0):
        """Toggle survival mode based on blackout risk."""
        if active:
            self.mode = "survival"
            self.hedge_buffer_mwh = min(buffer_requirement_mwh, self.params.battery_capacity_mwh)
        else:
            self.mode = "profit"
            self.hedge_buffer_mwh = 0.0
