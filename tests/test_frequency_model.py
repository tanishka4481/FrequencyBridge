"""
Tests for the Two-Area Swing Equation Frequency Model.

These tests validate that the ODE produces physically reasonable behavior:
- Frequency dips after a disturbance
- Frequency recovers toward nominal
- No numerical blow-up
- Governor response improves recovery
- Coupling between areas works correctly
- Edge cases (zero disturbance, large disturbance) are handled
"""

import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.physics.frequency_model import (
    FrequencyModel,
    SystemState,
    Disturbance,
    TwoAreaParams,
    AreaParams,
    SimulationResult,
)


class TestFrequencyModelBasic:
    """Basic sanity checks for the frequency model."""

    def setup_method(self):
        """Set up default model and state for each test."""
        self.model = FrequencyModel()
        self.state = SystemState()

    def test_zero_disturbance_stays_at_nominal(self):
        """No disturbance should produce no deviation."""
        disturbance = Disturbance(east_pu=0.0, west_pu=0.0)
        result = self.model.simulate(self.state, disturbance, duration=10.0)

        assert np.allclose(result.delta_f_east, 0.0, atol=1e-10), \
            "East frequency should stay at nominal with no disturbance"
        assert np.allclose(result.delta_f_west, 0.0, atol=1e-10), \
            "West frequency should stay at nominal with no disturbance"

    def test_step_disturbance_causes_dip(self):
        """A load increase should cause frequency to dip."""
        disturbance = Disturbance(east_pu=-0.10)  # 10% load increase
        result = self.model.simulate(self.state, disturbance, duration=30.0)

        min_east = np.min(result.delta_f_east)
        assert min_east < -0.001, \
            f"East frequency should dip after load increase (min Δf = {min_east})"

    def test_frequency_recovers(self):
        """Frequency should settle toward a steady state within 60s.

        With a sustained disturbance and governor droop, the system settles
        to a steady-state offset (not back to zero — that requires AGC/secondary
        control). The test verifies that oscillations are damped and the system
        reaches a stable equilibrium.
        """
        disturbance = Disturbance(east_pu=-0.10)
        result = self.model.simulate(self.state, disturbance, duration=60.0, dt=0.05)

        # Oscillations should be damped: variance in second half < first half
        midpoint = len(result.delta_f_east) // 2
        var_first_half = np.var(result.delta_f_east[:midpoint])
        var_second_half = np.var(result.delta_f_east[midpoint:])

        assert var_second_half < var_first_half, \
            f"Oscillations should damp (var first half: {var_first_half}, second: {var_second_half})"

        # Final deviation should be bounded (droop steady-state, not blow-up)
        final_dev = abs(result.delta_f_east[-1])
        assert final_dev < 0.01, \
            f"Steady-state deviation should be small (actual: {final_dev} pu)"

    def test_deviation_within_bounds(self):
        """Max deviation should be < 2 Hz for a 0.1 pu disturbance."""
        disturbance = Disturbance(east_pu=-0.10)
        result = self.model.simulate(self.state, disturbance, duration=60.0)

        max_dev_hz = result.max_deviation_east_hz()
        assert max_dev_hz < 2.0, \
            f"Max deviation should be < 2 Hz (actual: {max_dev_hz:.4f} Hz)"

    def test_no_numerical_blowup(self):
        """All values should remain finite over 60s simulation."""
        disturbance = Disturbance(east_pu=-0.10)
        result = self.model.simulate(self.state, disturbance, duration=60.0)

        assert np.all(np.isfinite(result.delta_f_east)), "East Δf contains non-finite values"
        assert np.all(np.isfinite(result.delta_f_west)), "West Δf contains non-finite values"
        assert np.all(np.isfinite(result.delta_angle)), "Δδ contains non-finite values"


class TestCoupling:
    """Tests for inter-area coupling behavior."""

    def setup_method(self):
        self.model = FrequencyModel()
        self.state = SystemState()

    def test_east_disturbance_affects_west(self):
        """East disturbance should propagate to west via tie-line."""
        disturbance = Disturbance(east_pu=-0.10, west_pu=0.0)
        result = self.model.simulate(self.state, disturbance, duration=30.0)

        max_dev_west = np.max(np.abs(result.delta_f_west))
        assert max_dev_west > 1e-4, \
            f"West should respond to east disturbance (max |Δf_west| = {max_dev_west})"

    def test_coupling_direction(self):
        """East load increase should initially cause west frequency to also drop."""
        disturbance = Disturbance(east_pu=-0.10, west_pu=0.0)
        result = self.model.simulate(self.state, disturbance, duration=5.0, dt=0.01)

        # West should dip too (power flows east via tie-line)
        min_west = np.min(result.delta_f_west)
        assert min_west < 0, \
            "West frequency should also dip when east has load increase"

    def test_rotor_angle_changes(self):
        """Asymmetric disturbance should cause rotor angle difference."""
        disturbance = Disturbance(east_pu=-0.10, west_pu=0.0)
        result = self.model.simulate(self.state, disturbance, duration=10.0)

        max_angle = np.max(np.abs(result.delta_angle))
        assert max_angle > 1e-4, \
            "Rotor angle difference should change with asymmetric disturbance"


class TestGovernorResponse:
    """Tests for governor (primary frequency control) behavior."""

    def test_governor_improves_recovery(self):
        """System with governor should recover better than without."""
        # With governor
        model_gov = FrequencyModel()
        result_gov = model_gov.simulate(
            SystemState(), Disturbance(east_pu=-0.10), duration=60.0
        )

        # Without governor
        params_nogov = TwoAreaParams(
            east=AreaParams(name="east", nominal_freq_hz=50.0, inertia_h=5.0,
                            damping_d=1.0, governor_enabled=False),
            west=AreaParams(name="west", nominal_freq_hz=60.0, inertia_h=6.0,
                            damping_d=1.2, governor_enabled=False),
        )
        model_nogov = FrequencyModel(params_nogov)
        result_nogov = model_nogov.simulate(
            SystemState(), Disturbance(east_pu=-0.10), duration=60.0
        )

        final_gov = abs(result_gov.delta_f_east[-1])
        final_nogov = abs(result_nogov.delta_f_east[-1])

        assert final_gov < final_nogov, \
            f"Governor should reduce steady-state error (gov: {final_gov}, no-gov: {final_nogov})"


class TestConverterPower:
    """Tests for HVDC converter power injection."""

    def setup_method(self):
        self.model = FrequencyModel()
        self.state = SystemState()

    def test_converter_helps_east(self):
        """Positive converter power (east→west flow) should help west deficit."""
        # West has deficit
        disturbance = Disturbance(east_pu=0.0, west_pu=-0.10)

        # Without converter
        result_no_conv = self.model.simulate(
            self.state, disturbance, duration=30.0, converter_power_pu=0.0
        )

        # With converter helping west
        result_conv = self.model.simulate(
            self.state, disturbance, duration=30.0, converter_power_pu=0.05
        )

        # West should have smaller deviation with converter help
        max_west_no_conv = np.max(np.abs(result_no_conv.delta_f_west))
        max_west_conv = np.max(np.abs(result_conv.delta_f_west))

        assert max_west_conv < max_west_no_conv, \
            "Converter injection should reduce west deviation"


class TestSimulateStep:
    """Tests for the single-step interface used by the simulation loop."""

    def test_step_returns_valid_state(self):
        """simulate_step should return a valid SystemState."""
        model = FrequencyModel()
        state = SystemState()
        disturbance = Disturbance(east_pu=-0.05)

        new_state = model.simulate_step(state, disturbance, dt=30.0)

        assert isinstance(new_state, SystemState)
        assert np.isfinite(new_state.delta_f_east)
        assert np.isfinite(new_state.delta_f_west)
        assert np.isfinite(new_state.delta_angle)

    def test_step_advances_time(self):
        """simulate_step should advance the time by dt."""
        model = FrequencyModel()
        state = SystemState(time=100.0)

        new_state = model.simulate_step(state, Disturbance(), dt=30.0)
        assert new_state.time == pytest.approx(130.0, abs=0.1)

    def test_sequential_steps_match_continuous(self):
        """Multiple sequential steps should approximate a continuous simulation."""
        model = FrequencyModel()
        disturbance = Disturbance(east_pu=-0.05)

        # Continuous simulation: 10s
        result_cont = model.simulate(SystemState(), disturbance, duration=10.0, dt=0.1)

        # Sequential steps: 10 x 1s
        state = SystemState()
        for _ in range(10):
            state = model.simulate_step(state, disturbance, dt=1.0)

        # Should be in the same ballpark (not exact due to step granularity)
        assert abs(state.delta_f_east - result_cont.delta_f_east[-1]) < 0.01, \
            "Sequential steps should approximate continuous simulation"


class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_large_disturbance(self):
        """Large disturbance should not crash the solver."""
        model = FrequencyModel()
        disturbance = Disturbance(east_pu=-0.50)  # 50% load increase

        result = model.simulate(SystemState(), disturbance, duration=30.0)
        assert np.all(np.isfinite(result.delta_f_east))

    def test_positive_disturbance(self):
        """Excess generation should cause frequency to rise."""
        model = FrequencyModel()
        disturbance = Disturbance(east_pu=0.10)  # 10% excess generation

        result = model.simulate(SystemState(), disturbance, duration=30.0)
        max_east = np.max(result.delta_f_east)
        assert max_east > 0.001, "Excess generation should raise frequency"

    def test_freq_hz_conversion(self):
        """SystemState.freq_hz should correctly convert to actual Hz."""
        state = SystemState(delta_f_east=0.01, delta_f_west=-0.005)
        assert state.freq_hz("east") == pytest.approx(50.5, abs=0.01)
        assert state.freq_hz("west") == pytest.approx(59.7, abs=0.01)

    def test_custom_parameters(self):
        """Model should work with custom parameters."""
        params = TwoAreaParams(
            east=AreaParams(name="east", nominal_freq_hz=50.0, inertia_h=3.0, damping_d=0.5),
            west=AreaParams(name="west", nominal_freq_hz=60.0, inertia_h=4.0, damping_d=0.8),
            sync_coeff_t12=0.3,
        )
        model = FrequencyModel(params)
        result = model.simulate(SystemState(), Disturbance(east_pu=-0.05), duration=30.0)

        assert np.all(np.isfinite(result.delta_f_east))
        assert result.max_deviation_east_hz() > 0  # Should have some deviation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
