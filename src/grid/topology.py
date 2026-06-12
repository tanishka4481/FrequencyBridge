"""
Grid Topology Model.

This module provides a NetworkX graph representation of the Japan split grid.
While FreqBridge currently treats the east and west grids as single copper-plate
nodes connected by one HVDC link, using NetworkX allows for future expansion
(e.g., intra-grid transmission constraints, multiple HVDC links).
"""

import networkx as nx
from typing import Dict, Any


class GridTopology:
    """
    Manages the NetworkX graph of the power grid.
    
    Nodes:
        - "east" (50Hz region)
        - "west" (60Hz region)
        
    Edges:
        - ("east", "west"): The HVDC tie-line
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self._initialize_graph()

    def _initialize_graph(self):
        """Set up the default two-area Japan topology."""
        self.graph.add_node("east", region="east", frequency=50.0)
        self.graph.add_node("west", region="west", frequency=60.0)
        
        # Add bi-directional tie-line
        self.graph.add_edge("east", "west", link_type="hvdc")
        self.graph.add_edge("west", "east", link_type="hvdc")

    def update_node_state(self, node_id: str, attributes: Dict[str, Any]):
        """Update properties of a node (e.g., current load, generation)."""
        if node_id not in self.graph.nodes:
            raise ValueError(f"Node {node_id} not found in grid topology.")
            
        for key, value in attributes.items():
            self.graph.nodes[node_id][key] = value

    def update_edge_state(self, u: str, v: str, attributes: Dict[str, Any]):
        """Update properties of an edge (e.g., current MW flow)."""
        if not self.graph.has_edge(u, v):
            raise ValueError(f"Edge ({u}, {v}) not found in grid topology.")
            
        for key, value in attributes.items():
            self.graph.edges[u, v][key] = value

    def get_path(self, source: str, target: str) -> list:
        """Find the shortest path between two nodes."""
        try:
            return nx.shortest_path(self.graph, source=source, target=target)
        except nx.NetworkXNoPath:
            return []
