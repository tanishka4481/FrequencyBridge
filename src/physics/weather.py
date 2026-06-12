"""
Ornstein-Uhlenbeck Weather Generator for FreqBridge.

This module provides a stochastic weather model using the Ornstein-Uhlenbeck (OU)
process. An OU process is a mean-reverting random walk, which perfectly models
solar and wind generation factors: they have volatility but revert to a long-term
mean capacity factor.

The generator also supports injecting discrete weather shocks (e.g., sudden
cloud cover or wind death) and provides a look-ahead forecast.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class WeatherParams:
    """Parameters for the Ornstein-Uhlenbeck process."""
    mean_reversion: float  # theta: speed of mean reversion
    long_term_mean: float  # mu: long term average capacity factor (0 to 1)
    volatility: float      # sigma: volatility magnitude


@dataclass
class WeatherState:
    """Current state of weather factors (0.0 to 1.0 capacity factors)."""
    solar_cf: float
    wind_cf: float
    time: float = 0.0


class WeatherGenerator:
    """
    Generates stochastic solar and wind capacity factors.
    
    Uses the discrete Euler-Maruyama method to step the OU process:
    X_{t+dt} = X_t + theta * (mu - X_t) * dt + sigma * sqrt(dt) * Z
    where Z is a standard normal random variable.
    """

    def __init__(
        self,
        solar_params: WeatherParams,
        wind_params: WeatherParams,
        initial_state: Optional[WeatherState] = None
    ):
        self.solar_params = solar_params
        self.wind_params = wind_params
        
        self.state = initial_state or WeatherState(
            solar_cf=solar_params.long_term_mean,
            wind_cf=wind_params.long_term_mean
        )
        
        # Track applied shocks
        self.solar_shock: float = 0.0
        self.wind_shock: float = 0.0

    def step(self, dt_minutes: float) -> WeatherState:
        """Advance the weather model by dt minutes."""
        
        # Step solar
        p_s = self.solar_params
        drift_s = p_s.mean_reversion * (p_s.long_term_mean - self.state.solar_cf) * dt_minutes
        diffusion_s = p_s.volatility * np.sqrt(dt_minutes) * np.random.normal()
        new_solar = self.state.solar_cf + drift_s + diffusion_s + self.solar_shock
        
        # Step wind
        p_w = self.wind_params
        drift_w = p_w.mean_reversion * (p_w.long_term_mean - self.state.wind_cf) * dt_minutes
        diffusion_w = p_w.volatility * np.sqrt(dt_minutes) * np.random.normal()
        new_wind = self.state.wind_cf + drift_w + diffusion_w + self.wind_shock

        # Clear discrete shocks after they are applied (reversion handles the rest)
        self.solar_shock = 0.0
        self.wind_shock = 0.0

        # Clip bounds to physical capacity factor [0, 1]
        new_solar = float(np.clip(new_solar, 0.0, 1.0))
        new_wind = float(np.clip(new_wind, 0.0, 1.0))

        self.state = WeatherState(
            solar_cf=new_solar,
            wind_cf=new_wind,
            time=self.state.time + dt_minutes
        )
        
        return self.state

    def inject_shock(self, solar_shock: float = 0.0, wind_shock: float = 0.0):
        """Inject a sudden discrete shock to be applied on the next step.
        
        Example: -0.8 solar shock simulates sudden heavy cloud cover.
        """
        self.solar_shock = solar_shock
        self.wind_shock = wind_shock

    def generate_forecast(self, horizon_minutes: float, dt_minutes: float) -> List[WeatherState]:
        """Generate a deterministic expected forecast (no noise).
        
        Uses the expected value of the OU process:
        E[X_t] = X_0 * e^(-theta * t) + mu * (1 - e^(-theta * t))
        """
        steps = int(horizon_minutes / dt_minutes)
        forecast = []
        
        current_time = self.state.time
        solar_0 = self.state.solar_cf
        wind_0 = self.state.wind_cf
        
        for i in range(1, steps + 1):
            t = i * dt_minutes
            
            # Expected value formula for OU process
            exp_solar = (solar_0 * np.exp(-self.solar_params.mean_reversion * t) + 
                         self.solar_params.long_term_mean * (1 - np.exp(-self.solar_params.mean_reversion * t)))
            
            exp_wind = (wind_0 * np.exp(-self.wind_params.mean_reversion * t) + 
                        self.wind_params.long_term_mean * (1 - np.exp(-self.wind_params.mean_reversion * t)))
            
            forecast.append(WeatherState(
                solar_cf=float(np.clip(exp_solar, 0.0, 1.0)),
                wind_cf=float(np.clip(exp_wind, 0.0, 1.0)),
                time=current_time + t
            ))
            
        return forecast
