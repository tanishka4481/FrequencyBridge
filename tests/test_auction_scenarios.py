"""
Tests for Double Auction Engine.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.auction_engine import AuctionEngine, Bid, Ask


class TestAuctionEngine:

    def setup_method(self):
        self.engine = AuctionEngine()

    def test_simple_matching(self):
        """Bids and asks in same region."""
        bids = [Bid("B1", "east", 50.0, 30.0)]
        asks = [Ask("A1", "east", 100.0, 10.0)]
        
        result = self.engine.clear_market(bids, asks, 300, 300, 0.0)
        
        assert len(result.trades) == 1
        assert result.total_volume_cleared_mw == 50.0
        assert result.trades[0].clearing_price == 20.0  # (30 + 10) / 2
        assert result.converter_flow_mw == 0.0

    def test_no_match_price_too_high(self):
        """Bids are too low to meet ask prices."""
        bids = [Bid("B1", "east", 50.0, 10.0)]
        asks = [Ask("A1", "east", 50.0, 30.0)]
        
        result = self.engine.clear_market(bids, asks, 300, 300, 0.0)
        assert len(result.trades) == 0

    def test_cross_region_loss_math(self):
        """Seller must generate more to cover 2% loss."""
        bids = [Bid("EastBuyer", "east", 100.0, 50.0)]
        asks = [Ask("WestSeller", "west", 100.0, 10.0)]
        
        # Loss rate = 0.02
        # West has 100MW to sell. It can deliver 98MW to East.
        # Effective ask price = 10 / 0.98 = 10.204
        # Clearing price = (50 + 10.204) / 2 = 30.102
        
        result = self.engine.clear_market(bids, asks, 300, 300, 0.02)
        
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.volume_mw == 98.0
        assert abs(t.clearing_price - 30.102) < 0.01
        assert t.converter_used is True
        
        # Converter flow is West to East, meaning negative.
        # Flow size is the generated amount (100)
        assert result.converter_flow_mw == -100.0

    def test_converter_bottleneck(self):
        """Trade volume is capped by converter remaining capacity."""
        bids = [Bid("WestBuyer", "west", 500.0, 50.0)]
        asks = [Ask("EastSeller", "east", 500.0, 10.0)]
        
        # Converter only has 100 MW capacity East->West
        result = self.engine.clear_market(bids, asks, 100.0, 100.0, 0.02)
        
        # 100MW flows East->West. 2% lost. 98MW delivered.
        assert result.total_volume_cleared_mw == 98.0
        assert result.converter_flow_mw == 100.0

    def test_multi_bid_ask_priority(self):
        """Engine should match highest bids with lowest asks first."""
        bids = [
            Bid("B_Low", "east", 50.0, 20.0),
            Bid("B_High", "east", 50.0, 40.0)
        ]
        asks = [
            Ask("A_High", "east", 50.0, 30.0),
            Ask("A_Low", "east", 50.0, 10.0)
        ]
        
        result = self.engine.clear_market(bids, asks, 300, 300, 0.0)
        
        assert len(result.trades) == 1
        
        # First trade should be B_High matching A_Low
        assert result.trades[0].buyer_id == "B_High"
        assert result.trades[0].seller_id == "A_Low"
        assert result.trades[0].clearing_price == 25.0  # (40 + 10) / 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
