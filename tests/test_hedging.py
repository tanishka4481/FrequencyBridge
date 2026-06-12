"""
Tests for Hedging and Blackout Defense Logic.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.hedging import BlackoutPredictor, HedgingConstants


class TestBlackoutPredictor:

    def setup_method(self):
        self.predictor = BlackoutPredictor(lookahead_ticks=5)

    def test_zero_probability_when_surplus(self):
        """If generation always exceeds demand, prob is 0."""
        gen = [100.0] * 5
        dem = [50.0] * 5
        soc = 0.5
        
        prob = self.predictor.calculate_probability(gen, dem, soc)
        assert prob == 0.0

    def test_high_probability_when_deficit_and_low_soc(self):
        """If generation is always below demand and SOC is 0, prob is high."""
        gen = [20.0] * 5
        dem = [100.0] * 5
        soc = 0.0
        
        prob = self.predictor.calculate_probability(gen, dem, soc)
        # Base prob = 1.0 (5/5 steps in deficit)
        # SOC factor = 1.0
        # Final prob = 1.0 * (0.5 + 0.5*1.0) = 1.0
        assert prob == 1.0

    def test_mode_switching_thresholds(self):
        """Check mode selection against constants."""
        # Below hedge threshold
        mode, buf = self.predictor.determine_mode(HedgingConstants.HEDGE_THRESHOLD_PROB - 0.01)
        assert mode == "profit"
        assert buf == 0.0
        
        # Above hedge, below emergency
        mode, buf = self.predictor.determine_mode(HedgingConstants.HEDGE_THRESHOLD_PROB + 0.01)
        assert mode == "survival"
        assert buf == HedgingConstants.BASE_BUFFER_MWH
        
        # Above emergency
        mode, buf = self.predictor.determine_mode(HedgingConstants.EMERGENCY_THRESHOLD_PROB + 0.01)
        assert mode == "survival"
        assert buf == HedgingConstants.EMERGENCY_BUFFER_MWH


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
