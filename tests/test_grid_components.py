"""
Tests for Grid Components (Converter and Topology).
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.grid.converter import ConverterAgent, ConverterParams
from src.grid.topology import GridTopology


class TestConverterAgent:
    """Tests for the HVDC Converter Agent."""

    def setup_method(self):
        self.params = ConverterParams(
            capacity_mw=300.0,
            loss_rate=0.02,  # 2%
            ramp_rate_mw_per_tick=50.0
        )
        self.converter = ConverterAgent(self.params)

    def test_can_transfer_within_limits(self):
        """Standard transfer within capacity and ramp limits."""
        # Current is 0. Request 40 MW. Ramp is 50, Cap is 300.
        allowed = self.converter.can_transfer(40.0, "east_to_west")
        assert allowed == 40.0

    def test_ramp_rate_limit(self):
        """Transfer should be limited by ramp rate."""
        # Request 100 MW, but ramp rate is 50.
        allowed = self.converter.can_transfer(100.0, "east_to_west")
        assert allowed == 50.0

    def test_capacity_limit(self):
        """Transfer should be limited by total capacity."""
        # First ramp up to 250 MW
        self.converter.current_transfer_mw = 280.0
        
        # Request an additional 50 MW (total 330)
        allowed = self.converter.can_transfer(330.0, "east_to_west")
        assert allowed == 300.0  # Capped at capacity

    def test_directionality(self):
        """Ramping from East-to-West to West-to-East."""
        self.converter.current_transfer_mw = 20.0  # Currently 20 MW East->West
        
        # Request 40 MW West->East (target is -40 MW)
        # Delta is -40 - 20 = -60 MW. Max delta is 50 MW.
        # Target becomes 20 - 50 = -30 MW.
        allowed = self.converter.can_transfer(40.0, "west_to_east")
        assert allowed == 30.0  # 30 MW West->East is allowed

    def test_execute_transfer_applies_losses(self):
        """Transfer execution should apply the loss rate."""
        delivered = self.converter.execute_transfer(100.0, "east_to_west")
        
        # 100 MW * (1 - 0.02) = 98 MW
        assert delivered == 98.0
        assert self.converter.current_transfer_mw == 100.0
        
        # Test the other direction
        delivered_west = self.converter.execute_transfer(50.0, "west_to_east")
        assert delivered_west == 49.0
        assert self.converter.current_transfer_mw == -50.0

    def test_get_available_capacity(self):
        """Available capacity should calculate correctly based on current flow."""
        self.converter.current_transfer_mw = 100.0  # East->West
        
        # East->West room: 300 - 100 = 200
        assert self.converter.get_available_capacity("east_to_west") == 200.0
        
        # West->East room: 300 + 100 = 400 (can swing 100 back to 0, then 300 more)
        assert self.converter.get_available_capacity("west_to_east") == 400.0


class TestGridTopology:
    """Tests for the Grid Topology NetworkX graph."""

    def setup_method(self):
        self.topology = GridTopology()

    def test_nodes_initialized(self):
        """Graph should have east and west nodes."""
        assert "east" in self.topology.graph.nodes
        assert "west" in self.topology.graph.nodes
        assert self.topology.graph.nodes["east"]["frequency"] == 50.0

    def test_edges_initialized(self):
        """Graph should have bidirectional HVDC edges."""
        assert self.topology.graph.has_edge("east", "west")
        assert self.topology.graph.has_edge("west", "east")
        assert self.topology.graph.edges["east", "west"]["link_type"] == "hvdc"

    def test_update_state(self):
        """State updates should apply to nodes and edges."""
        self.topology.update_node_state("east", {"load_mw": 5000.0})
        assert self.topology.graph.nodes["east"]["load_mw"] == 5000.0
        
        self.topology.update_edge_state("east", "west", {"current_flow": 150.0})
        assert self.topology.graph.edges["east", "west"]["current_flow"] == 150.0

    def test_get_path(self):
        """Should find simple path between east and west."""
        path = self.topology.get_path("east", "west")
        assert path == ["east", "west"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
