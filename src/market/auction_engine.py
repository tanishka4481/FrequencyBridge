"""
Double Auction Engine.

Resolves bids (offers to buy) and asks (offers to sell) between microgrid agents.
The auction engine accounts for the physical constraints of the grid, specifically
the 2% transmission loss and capacity limits when routing power across the HVDC
converter between the East and West regions.

This file currently contains the skeleton types and data structures.
Resolution logic will be implemented in Phase 3b.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Bid:
    """An offer to BUY power."""
    agent_id: str
    region: str          # "east" or "west"
    volume_mw: float     # How much power is needed
    price: float         # Maximum price willing to pay


@dataclass
class Ask:
    """An offer to SELL power."""
    agent_id: str
    region: str          # "east" or "west"
    volume_mw: float     # How much power is available
    price: float         # Minimum price willing to accept


@dataclass
class Trade:
    """A cleared transaction between a buyer and a seller."""
    buyer_id: str
    seller_id: str
    buyer_region: str
    seller_region: str
    volume_mw: float         # Volume delivered to the buyer
    clearing_price: float    # The settled market price
    converter_used: bool     # True if the trade crossed the east/west boundary


@dataclass
class AuctionResult:
    """Results of a single auction round."""
    trades: List[Trade]
    clearing_price_east: Optional[float]
    clearing_price_west: Optional[float]
    total_volume_cleared_mw: float
    converter_flow_mw: float  # Positive = East to West, Negative = West to East


class AuctionEngine:
    """
    Matches bids and asks via a double auction mechanism.
    
    Handles split-grid complexities:
    If a trade crosses regions, the buyer must pay for the 2% converter loss,
    and the trade must fit within the converter's remaining capacity.
    """

    def __init__(self, price_floor: float = 5.0, price_ceiling: float = 50.0):
        self.price_floor = price_floor
        self.price_ceiling = price_ceiling

    def clear_market(
        self, 
        bids: List[Bid], 
        asks: List[Ask], 
        converter_available_east_to_west: float,
        converter_available_west_to_east: float,
        converter_loss_rate: float
    ) -> AuctionResult:
        """
        Resolve the double auction matching Bids and Asks.
        """
        # Sort bids descending (highest willing to pay first)
        sorted_bids = sorted(bids, key=lambda b: b.price, reverse=True)
        # Sort asks ascending (cheapest power first)
        sorted_asks = sorted(asks, key=lambda a: a.price)
        
        trades = []
        total_cleared = 0.0
        
        # Track remaining capacities
        rem_e2w = converter_available_east_to_west
        rem_w2e = converter_available_west_to_east
        
        # We will iterate through bids and try to match with the best available asks
        for bid in sorted_bids:
            bid_vol_remaining = bid.volume_mw
            
            # Since an ask might be partially filled, we need a way to track ask remaining volumes.
            # We'll just modify the ask objects in the sorted list directly for this simulation round.
            for ask in sorted_asks:
                if bid_vol_remaining <= 1e-6:
                    break
                    
                if ask.volume_mw <= 1e-6:
                    continue
                    
                is_cross_region = bid.region != ask.region
                
                # Calculate effective price. If cross-region, the buyer pays for transmission losses.
                # If seller offers at P, and 2% is lost, the buyer effectively pays P / (1 - loss) per delivered MW.
                effective_ask_price = ask.price
                if is_cross_region:
                    effective_ask_price = ask.price / (1.0 - converter_loss_rate)
                    
                # Can they agree on a price?
                if bid.price < effective_ask_price:
                    continue  # This ask is too expensive for this bid
                    
                # Determine transaction volume
                # Buyer wants `bid_vol_remaining`. Seller has `ask.volume_mw`.
                # If cross region, to deliver V to buyer, seller must supply V / (1 - loss).
                if is_cross_region:
                    max_seller_can_deliver = ask.volume_mw * (1.0 - converter_loss_rate)
                    trade_vol_buyer_receives = min(bid_vol_remaining, max_seller_can_deliver)
                    
                    # Check converter capacity constraints
                    if bid.region == "east" and ask.region == "west":
                        # Power flows West -> East
                        trade_vol_buyer_receives = min(trade_vol_buyer_receives, rem_w2e * (1.0 - converter_loss_rate))
                    else:
                        # Power flows East -> West
                        trade_vol_buyer_receives = min(trade_vol_buyer_receives, rem_e2w * (1.0 - converter_loss_rate))
                        
                    if trade_vol_buyer_receives <= 1e-6:
                        continue  # Converter is full, cannot execute cross-region trade
                        
                    vol_seller_provides = trade_vol_buyer_receives / (1.0 - converter_loss_rate)
                    
                    # Deduct from converter
                    if bid.region == "east":
                        rem_w2e -= vol_seller_provides
                    else:
                        rem_e2w -= vol_seller_provides
                        
                else:
                    trade_vol_buyer_receives = min(bid_vol_remaining, ask.volume_mw)
                    vol_seller_provides = trade_vol_buyer_receives
                    
                # Execution price (split the difference between bid and effective ask)
                clearing_price = (bid.price + effective_ask_price) / 2.0
                
                # Execute trade
                trades.append(Trade(
                    buyer_id=bid.agent_id,
                    seller_id=ask.agent_id,
                    buyer_region=bid.region,
                    seller_region=ask.region,
                    volume_mw=trade_vol_buyer_receives,
                    clearing_price=clearing_price,
                    converter_used=is_cross_region
                ))
                
                total_cleared += trade_vol_buyer_receives
                bid_vol_remaining -= trade_vol_buyer_receives
                ask.volume_mw -= vol_seller_provides

        # Calculate marginal clearing prices per region
        # If no trades, use None. Otherwise, use the last trade involving that region.
        cp_east = None
        cp_west = None
        
        east_trades = [t for t in trades if t.buyer_region == "east" or t.seller_region == "east"]
        if east_trades:
            cp_east = east_trades[-1].clearing_price
            
        west_trades = [t for t in trades if t.buyer_region == "west" or t.seller_region == "west"]
        if west_trades:
            cp_west = west_trades[-1].clearing_price
            
        # Calculate net converter flow (Positive = East to West, Negative = West to East)
        net_flow = 0.0
        for t in trades:
            if t.converter_used:
                if t.seller_region == "east":
                    # East to West
                    net_flow += (t.volume_mw / (1.0 - converter_loss_rate))
                else:
                    # West to East
                    net_flow -= (t.volume_mw / (1.0 - converter_loss_rate))

        return AuctionResult(
            trades=trades,
            clearing_price_east=cp_east,
            clearing_price_west=cp_west,
            total_volume_cleared_mw=total_cleared,
            converter_flow_mw=net_flow
        )
