"""
HVDC Converter Agent Model.

This module models the physical HVDC converters that connect Japan's
eastern (50Hz) and western (60Hz) grids.

The converter is the central bottleneck in the FreqBridge architecture:
- It has a fixed physical capacity limit (e.g., 300 MW).
- It incurs transmission losses (e.g., 2%).
- It has a ramp rate limit (how fast the power flow can change).
"""

from dataclasses import dataclass


@dataclass
class ConverterParams:
    """Parameters for the HVDC converter."""
    capacity_mw: float       # Maximum transfer capacity
    loss_rate: float         # Percentage lost in transmission (0.0 to 1.0)
    ramp_rate_mw_per_tick: float  # Max change in power transfer per simulation tick


class ConverterAgent:
    """
    Models the HVDC link between the two grid regions.
    
    This agent enforces physical constraints on trades cleared by the market.
    """

    def __init__(self, params: ConverterParams):
        self.params = params
        self.current_transfer_mw = 0.0  # Positive = East to West, Negative = West to East
    
    def can_transfer(self, requested_amount_mw: float, direction: str) -> float:
        """
        Check how much of the requested amount can physically be transferred.
        
        Args:
            requested_amount_mw: Amount requested to transfer (always positive)
            direction: 'east_to_west' or 'west_to_east'
            
        Returns:
            The allowable transfer amount in MW (bounded by capacity and ramp rates)
        """
        if requested_amount_mw < 0:
            raise ValueError("Requested transfer amount must be positive.")
            
        target_transfer = requested_amount_mw if direction == "east_to_west" else -requested_amount_mw
        
        # Check capacity constraint
        if target_transfer > self.params.capacity_mw:
            target_transfer = self.params.capacity_mw
        elif target_transfer < -self.params.capacity_mw:
            target_transfer = -self.params.capacity_mw
            
        # Check ramp rate constraint
        delta = target_transfer - self.current_transfer_mw
        max_delta = self.params.ramp_rate_mw_per_tick
        
        if delta > max_delta:
            target_transfer = self.current_transfer_mw + max_delta
        elif delta < -max_delta:
            target_transfer = self.current_transfer_mw - max_delta
            
        # Return the absolute allowed amount
        return abs(target_transfer if direction == "east_to_west" else -target_transfer)

    def execute_transfer(self, target_amount_mw: float, direction: str) -> float:
        """
        Execute a power transfer, updating the converter's state and returning net delivered power.
        
        Args:
            target_amount_mw: Target amount to transfer (must be previously validated by can_transfer)
            direction: 'east_to_west' or 'west_to_east'
            
        Returns:
            Net power delivered to the receiving side (after losses applied)
        """
        if target_amount_mw < 0:
            raise ValueError("Target transfer amount must be positive.")
            
        self.current_transfer_mw = target_amount_mw if direction == "east_to_west" else -target_amount_mw
        
        # Apply losses (e.g., sending 100 MW with 2% loss delivers 98 MW)
        net_delivered = target_amount_mw * (1.0 - self.params.loss_rate)
        return net_delivered

    def get_available_capacity(self, direction: str) -> float:
        """Get remaining capacity in the given direction before hitting hard limits."""
        if direction == "east_to_west":
            return self.params.capacity_mw - self.current_transfer_mw
        elif direction == "west_to_east":
            return self.params.capacity_mw + self.current_transfer_mw
        else:
            raise ValueError(f"Unknown direction: {direction}")
