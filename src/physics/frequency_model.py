"""
Two-Area Swing Equation Model for Japan's 50Hz/60Hz Split Grid.

Implements the linearized swing equation for a two-area power system connected
by an HVDC tie-line (the HVDC converters between east/west Japan). This models
how frequency deviations propagate and recover after disturbances.

Physics Background:
    Each area's frequency dynamics follow the swing equation:
        2H * d(Δf)/dt = Pm - Pe - D*Δf
    where:
        H  = inertia constant (seconds) — stored kinetic energy / rated power
        Δf = frequency deviation from nominal (per unit)
        Pm = mechanical power input (per unit)
        Pe = electrical power output / load (per unit)
        D  = damping coefficient (pu power / pu frequency)

    For a two-area system, the areas are coupled through a tie-line:
        P_tie = T12 * (δ1 - δ2)
    where T12 is the synchronizing power coefficient and δ is the rotor angle.

    Since dδ/dt = 2π * f_nominal * Δf, we track rotor angle differences
    to capture inter-area oscillations.

Reference Parameters (from config/settings.example.toml):
    East (50Hz): H=5.0s, D=1.0
    West (60Hz): H=6.0s, D=1.2
    Tie-line: T12=0.5

Author: FreqBridge Team
"""

import numpy as np
from scipy.integrate import solve_ivp
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AreaParams:
    """Parameters for one area of the two-area system."""
    name: str
    nominal_freq_hz: float  # 50.0 for east, 60.0 for west
    inertia_h: float        # Inertia constant H (seconds)
    damping_d: float        # Damping coefficient D (pu)
    # Governor droop response (primary frequency control)
    governor_r: float = 0.05  # Droop setting (5% typical)
    governor_enabled: bool = True


@dataclass
class TwoAreaParams:
    """Parameters for the complete two-area system."""
    east: AreaParams = field(default_factory=lambda: AreaParams(
        name="east", nominal_freq_hz=50.0, inertia_h=5.0, damping_d=1.0
    ))
    west: AreaParams = field(default_factory=lambda: AreaParams(
        name="west", nominal_freq_hz=60.0, inertia_h=6.0, damping_d=1.2
    ))
    sync_coeff_t12: float = 0.5  # Synchronizing power coefficient


@dataclass
class SystemState:
    """State of the two-area system at a given time.

    State vector: [Δf_east, Δf_west, Δδ]
        Δf_east: frequency deviation in east area (per unit)
        Δf_west: frequency deviation in west area (per unit)
        Δδ:      rotor angle difference δ_east - δ_west (radians)
    """
    delta_f_east: float = 0.0   # Frequency deviation east (pu)
    delta_f_west: float = 0.0   # Frequency deviation west (pu)
    delta_angle: float = 0.0    # Rotor angle difference (rad)
    time: float = 0.0           # Current simulation time (s)

    def to_array(self) -> np.ndarray:
        """Convert to state vector for ODE solver."""
        return np.array([self.delta_f_east, self.delta_f_west, self.delta_angle])

    @classmethod
    def from_array(cls, y: np.ndarray, time: float = 0.0) -> "SystemState":
        """Create from ODE solver output."""
        return cls(
            delta_f_east=float(y[0]),
            delta_f_west=float(y[1]),
            delta_angle=float(y[2]),
            time=time,
        )

    def freq_hz(self, area: str) -> float:
        """Get actual frequency in Hz for a given area."""
        if area == "east":
            return 50.0 * (1.0 + self.delta_f_east)
        elif area == "west":
            return 60.0 * (1.0 + self.delta_f_west)
        else:
            raise ValueError(f"Unknown area: {area}. Use 'east' or 'west'.")


@dataclass
class Disturbance:
    """A power disturbance applied to the system.

    Positive values = excess generation (frequency rises)
    Negative values = excess load / generation loss (frequency drops)
    """
    east_pu: float = 0.0  # Disturbance in east area (per unit)
    west_pu: float = 0.0  # Disturbance in west area (per unit)


class FrequencyModel:
    """Two-area swing equation ODE solver.

    Models the coupled frequency dynamics of Japan's east (50Hz) and west (60Hz)
    grids connected through HVDC converters. The converter is modeled as a
    controllable tie-line with optional power injection.

    Usage:
        model = FrequencyModel()
        state = SystemState()
        disturbance = Disturbance(east_pu=-0.1)  # 10% load increase in east
        result = model.simulate(state, disturbance, duration=60.0)
        # result.states[-1] is the final state
    """

    def __init__(self, params: Optional[TwoAreaParams] = None):
        self.params = params or TwoAreaParams()

    def _derivatives(self, t: float, y: np.ndarray,
                     disturbance: Disturbance,
                     converter_power_pu: float = 0.0) -> np.ndarray:
        """Compute state derivatives for the two-area swing equation.

        Args:
            t: Current time (s)
            y: State vector [Δf_east, Δf_west, Δδ]
            disturbance: External power disturbance
            converter_power_pu: Power injected by HVDC converter (pu)
                Positive = power flowing east→west

        Returns:
            dy/dt: State derivatives
        """
        delta_f_east, delta_f_west, delta_angle = y
        p = self.params

        # Tie-line power flow based on angle difference
        p_tie = p.sync_coeff_t12 * np.sin(delta_angle)

        # Governor response (primary frequency control)
        gov_east = 0.0
        gov_west = 0.0
        if p.east.governor_enabled:
            gov_east = -delta_f_east / p.east.governor_r
        if p.west.governor_enabled:
            gov_west = -delta_f_west / p.west.governor_r

        # East area: 2H * dΔf/dt = ΔPm - ΔPe - D*Δf - P_tie - P_converter
        # ΔPm includes governor response and disturbance
        d_delta_f_east = (
            disturbance.east_pu
            + gov_east
            - p.east.damping_d * delta_f_east
            - p_tie
            - converter_power_pu
        ) / (2.0 * p.east.inertia_h)

        # West area: 2H * dΔf/dt = ΔPm - ΔPe - D*Δf + P_tie + P_converter
        # West receives tie-line power and converter power
        d_delta_f_west = (
            disturbance.west_pu
            + gov_west
            - p.west.damping_d * delta_f_west
            + p_tie
            + converter_power_pu
        ) / (2.0 * p.west.inertia_h)

        # Rotor angle difference: dΔδ/dt = 2π * f_base * (Δf_east - Δf_west)
        # Using average base frequency for the coupling
        f_base_avg = (p.east.nominal_freq_hz + p.west.nominal_freq_hz) / 2.0
        d_delta_angle = 2.0 * np.pi * f_base_avg * (delta_f_east - delta_f_west)

        return np.array([d_delta_f_east, d_delta_f_west, d_delta_angle])

    def simulate(
        self,
        initial_state: SystemState,
        disturbance: Disturbance,
        duration: float,
        dt: float = 0.1,
        converter_power_pu: float = 0.0,
        method: str = "RK45",
    ) -> "SimulationResult":
        """Simulate the two-area system over a time period.

        Args:
            initial_state: Starting system state
            disturbance: Power disturbance (constant over the duration)
            duration: Simulation duration in seconds
            dt: Output time step for results (seconds)
            converter_power_pu: HVDC converter power injection (pu)
            method: ODE solver method (default RK45)

        Returns:
            SimulationResult with time series of states
        """
        y0 = initial_state.to_array()
        t_start = initial_state.time
        t_end = t_start + duration
        t_eval = np.arange(t_start, t_end + dt, dt)

        sol = solve_ivp(
            fun=lambda t, y: self._derivatives(t, y, disturbance, converter_power_pu),
            t_span=(t_start, t_end),
            y0=y0,
            method=method,
            t_eval=t_eval,
            rtol=1e-8,
            atol=1e-10,
        )

        if not sol.success:
            raise RuntimeError(f"ODE solver failed: {sol.message}")

        states = [
            SystemState.from_array(sol.y[:, i], sol.t[i])
            for i in range(len(sol.t))
        ]

        return SimulationResult(
            times=sol.t,
            states=states,
            delta_f_east=sol.y[0],
            delta_f_west=sol.y[1],
            delta_angle=sol.y[2],
            params=self.params,
        )

    def simulate_step(
        self,
        state: SystemState,
        disturbance: Disturbance,
        dt: float = 30.0,
        converter_power_pu: float = 0.0,
    ) -> SystemState:
        """Advance the system by one time step.

        This is the interface used by the simulation loop — single-step
        advancement rather than full trajectory simulation.

        Args:
            state: Current system state
            disturbance: Power disturbance for this step
            dt: Time step duration (seconds)
            converter_power_pu: HVDC converter power injection (pu)

        Returns:
            New system state after dt seconds
        """
        result = self.simulate(
            initial_state=state,
            disturbance=disturbance,
            duration=dt,
            dt=dt,
            converter_power_pu=converter_power_pu,
        )
        return result.states[-1]


@dataclass
class SimulationResult:
    """Result container for a frequency simulation run."""
    times: np.ndarray           # Time points (s)
    states: list                # List of SystemState objects
    delta_f_east: np.ndarray    # East frequency deviation time series (pu)
    delta_f_west: np.ndarray    # West frequency deviation time series (pu)
    delta_angle: np.ndarray     # Rotor angle difference time series (rad)
    params: TwoAreaParams       # Parameters used

    def freq_east_hz(self) -> np.ndarray:
        """East frequency in Hz over time."""
        return self.params.east.nominal_freq_hz * (1.0 + self.delta_f_east)

    def freq_west_hz(self) -> np.ndarray:
        """West frequency in Hz over time."""
        return self.params.west.nominal_freq_hz * (1.0 + self.delta_f_west)

    def max_deviation_east_hz(self) -> float:
        """Maximum frequency deviation in east area (Hz)."""
        return float(np.max(np.abs(self.delta_f_east))) * self.params.east.nominal_freq_hz

    def max_deviation_west_hz(self) -> float:
        """Maximum frequency deviation in west area (Hz)."""
        return float(np.max(np.abs(self.delta_f_west))) * self.params.west.nominal_freq_hz

    def recovery_time(self, area: str, threshold_pu: float = 0.001) -> Optional[float]:
        """Time for frequency to settle within threshold of nominal.

        Args:
            area: 'east' or 'west'
            threshold_pu: Settling threshold in per-unit (default 0.1%)

        Returns:
            Recovery time in seconds, or None if not settled
        """
        if area == "east":
            deviations = np.abs(self.delta_f_east)
        elif area == "west":
            deviations = np.abs(self.delta_f_west)
        else:
            raise ValueError(f"Unknown area: {area}")

        # Find last time deviation exceeds threshold
        above_threshold = np.where(deviations > threshold_pu)[0]
        if len(above_threshold) == 0:
            return 0.0  # Never deviated
        last_above = above_threshold[-1]
        if last_above >= len(self.times) - 1:
            return None  # Never settled
        return float(self.times[last_above] - self.times[0])
