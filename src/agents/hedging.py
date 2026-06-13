"""
Hedging and Blackout Defense Logic.

Calculates the blackout probability using a rolling window of 
generation and demand forecasts. It defines thresholds that trigger 
microgrid agents to switch into "survival mode" and hoard energy 
to preserve grid stability.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class HedgingConstants:
    """Centralized constants for hedging thresholds."""
    # Probability threshold to enter hedge mode (stop aggressive selling, hold base buffer)
    HEDGE_THRESHOLD_PROB: float = 0.70
    
    # Probability threshold to enter emergency reserve (start aggressive buying, max buffer)
    EMERGENCY_THRESHOLD_PROB: float = 0.75
    
    # Standard buffer required when in standard hedge mode (MWh)
    BASE_BUFFER_MWH: float = 15.0
    
    # Maximum buffer required when in emergency reserve mode (MWh)
    EMERGENCY_BUFFER_MWH: float = 30.0


class BlackoutPredictor:
    """Calculates rolling-window blackout probability."""
    
    def __init__(self, lookahead_ticks: int = 12):
        self.lookahead_ticks = lookahead_ticks
        
    def calculate_probability(self, 
                            expected_generation_mw: List[float], 
                            expected_demand_mw: List[float],
                            current_battery_soc: float) -> float:
        """
        Calculate the probability of a blackout in the lookahead window.
        
        Args:
            expected_generation_mw: Forecasted generation for upcoming ticks
            expected_demand_mw: Forecasted demand for upcoming ticks
            current_battery_soc: Current state of charge (0.0 to 1.0)
            
        Returns:
            Probability of blackout (0.0 to 1.0)
        """
        if not expected_generation_mw or not expected_demand_mw:
            return 0.0
            
        # Ensure we don't look past available forecast
        steps = min(len(expected_generation_mw), len(expected_demand_mw), self.lookahead_ticks)
        if steps == 0:
            return 0.0
            
        deficit_steps = 0
        cumulative_deficit = 0.0
        cumulative_demand = 0.0
        
        for i in range(steps):
            net = expected_generation_mw[i] - expected_demand_mw[i]
            cumulative_demand += expected_demand_mw[i]
            if net < 0:
                deficit_steps += 1
                cumulative_deficit += abs(net)
                
        # Calculate base risk based on severity of deficit relative to total demand
        base_prob = cumulative_deficit / cumulative_demand if cumulative_demand > 0 else 0.0
        
        # SOC acts as a mitigant. If SOC is 1.0, prob drops. If SOC is 0.0, prob rises.
        soc_factor = 1.0 - current_battery_soc
        
        final_prob = base_prob * (0.5 + 0.5 * soc_factor)
        
        return min(max(final_prob, 0.0), 1.0)

    def determine_mode(self, blackout_prob: float) -> tuple[str, float]:
        """
        Determine operating mode and required buffer size based on probability.
        
        Returns:
            (mode_name, required_buffer_mwh)
        """
        if blackout_prob >= HedgingConstants.EMERGENCY_THRESHOLD_PROB:
            return "survival", HedgingConstants.EMERGENCY_BUFFER_MWH
        elif blackout_prob >= HedgingConstants.HEDGE_THRESHOLD_PROB:
            return "survival", HedgingConstants.BASE_BUFFER_MWH
        else:
            return "profit", 0.0
