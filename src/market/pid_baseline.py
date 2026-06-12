"""
PID Baseline Controller.

A traditional "dumb" PID controller that commands HVDC converter flow
based strictly on the frequency deviation between the East and West grids,
ignoring economic bids, microgrid battery states, and weather forecasts.
Used as a baseline to compare against the FreqBridge market-driven approach.
"""

from typing import Tuple


class PIDController:
    """
    Standard Proportional-Integral-Derivative controller for frequency balancing.
    """
    
    def __init__(self, kp: float = 1000.0, ki: float = 50.0, kd: float = 10.0, 
                 deadband_hz: float = 0.05):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        
        # Controller state
        self.integral_error = 0.0
        self.prev_error = 0.0
        
        # If the frequency difference is less than this, do not intervene
        self.deadband_hz = deadband_hz

    def compute_flow_command(self, freq_east_hz: float, freq_west_hz: float, dt_seconds: float) -> float:
        """
        Compute desired MW flow from East to West.
        
        Args:
            freq_east_hz: Current frequency of East grid (target 50.0)
            freq_west_hz: Current frequency of West grid (target 60.0)
            dt_seconds: Time elapsed since last control step
            
        Returns:
            MW flow command. Positive = East to West. Negative = West to East.
        """
        # We look at the relative deviation from nominal
        # Positive dev means the grid has too much power. Negative means too little.
        dev_east = freq_east_hz - 50.0
        dev_west = freq_west_hz - 60.0
        
        # If East is too high and West is too low, we want power to flow East -> West
        # So error = dev_east - dev_west.
        error = dev_east - dev_west
        
        if abs(error) < self.deadband_hz:
            # Within acceptable limits, decay integral slowly and command 0
            self.integral_error *= 0.9
            return 0.0
            
        # P term
        p_out = self.kp * error
        
        # I term
        self.integral_error += error * dt_seconds
        # Anti-windup cap
        self.integral_error = max(min(self.integral_error, 10.0), -10.0)
        i_out = self.ki * self.integral_error
        
        # D term
        derivative = (error - self.prev_error) / dt_seconds if dt_seconds > 0 else 0.0
        d_out = self.kd * derivative
        
        self.prev_error = error
        
        # Total MW command
        command_mw = p_out + i_out + d_out
        
        return command_mw
