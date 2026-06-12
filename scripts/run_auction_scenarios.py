"""
Auction Scenario Runner.

Runs hardcoded edge cases to manually verify the double auction engine 
before integrating it into the full ODE simulation loop.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.auction_engine import AuctionEngine, Bid, Ask


def run_scenario_1_simple_match():
    """Scenario 1: Simple intra-region match."""
    print("=" * 60)
    print("SCENARIO 1: Simple intra-region match (East only)")
    print("=" * 60)
    
    engine = AuctionEngine()
    
    bids = [Bid(agent_id="B1", region="east", volume_mw=50.0, price=30.0)]
    asks = [Ask(agent_id="S1", region="east", volume_mw=100.0, price=10.0)]
    
    result = engine.clear_market(
        bids=bids, asks=asks, 
        converter_available_east_to_west=0, 
        converter_available_west_to_east=0, 
        converter_loss_rate=0.0
    )
    
    print(f"Total cleared: {result.total_volume_cleared_mw} MW")
    for t in result.trades:
        print(f"Trade: {t.buyer_id} buys {t.volume_mw}MW from {t.seller_id} at ${t.clearing_price}")


def run_scenario_2_cross_region_loss():
    """Scenario 2: Cross-region match where loss rate impacts price and volume."""
    print("\n" + "=" * 60)
    print("SCENARIO 2: Cross-region match with 2% loss")
    print("=" * 60)
    
    engine = AuctionEngine()
    
    bids = [Bid(agent_id="EastBuyer", region="east", volume_mw=100.0, price=50.0)]
    asks = [Ask(agent_id="WestSeller", region="west", volume_mw=100.0, price=20.0)]
    
    # West seller has 100MW. With 2% loss, they can only deliver 98MW to East.
    # Effective price for East buyer is 20 / 0.98 = $20.41
    
    result = engine.clear_market(
        bids=bids, asks=asks, 
        converter_available_east_to_west=300.0, 
        converter_available_west_to_east=300.0, 
        converter_loss_rate=0.02
    )
    
    print(f"Total delivered: {result.total_volume_cleared_mw} MW")
    print(f"Converter flow: {result.converter_flow_mw} MW (Negative means West->East)")
    for t in result.trades:
        print(f"Trade: {t.buyer_id} buys {t.volume_mw}MW from {t.seller_id} at ${t.clearing_price:.2f}")


def run_scenario_3_converter_bottleneck():
    """Scenario 3: Cross-region match bounded by converter capacity."""
    print("\n" + "=" * 60)
    print("SCENARIO 3: Converter capacity bottleneck")
    print("=" * 60)
    
    engine = AuctionEngine()
    
    bids = [Bid(agent_id="WestBuyer", region="west", volume_mw=500.0, price=40.0)]
    asks = [Ask(agent_id="EastSeller", region="east", volume_mw=500.0, price=10.0)]
    
    # Even though supply and demand are 500MW, converter is capped at 150MW.
    
    result = engine.clear_market(
        bids=bids, asks=asks, 
        converter_available_east_to_west=150.0, 
        converter_available_west_to_east=150.0, 
        converter_loss_rate=0.02
    )
    
    print(f"Total delivered: {result.total_volume_cleared_mw} MW")
    print(f"Converter flow: {result.converter_flow_mw} MW (Should be 150)")
    for t in result.trades:
        print(f"Trade: {t.buyer_id} buys {t.volume_mw:.2f}MW from {t.seller_id} at ${t.clearing_price:.2f}")


if __name__ == "__main__":
    run_scenario_1_simple_match()
    run_scenario_2_cross_region_loss()
    run_scenario_3_converter_bottleneck()
