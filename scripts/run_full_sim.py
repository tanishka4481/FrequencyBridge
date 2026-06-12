"""
Script to run the full FreqBridge simulation and visualize the results.
"""

import sys
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sim.simulation_loop import FreqBridgeSimulation, SimulationConfig


def main():
    print("Initializing FreqBridge Simulations...")
    
    # 1. Run Market Simulation
    market_config = SimulationConfig(tick_length_minutes=5.0, total_ticks=288, controller_type="market")
    market_sim = FreqBridgeSimulation(market_config)
    print("Running MARKET simulation for 288 ticks...")
    market_sim.run()
    df_market = pd.DataFrame(market_sim.history)
    df_market['scenario'] = 'Market'
    
    # 2. Run PID Simulation
    pid_config = SimulationConfig(tick_length_minutes=5.0, total_ticks=288, controller_type="pid")
    pid_sim = FreqBridgeSimulation(pid_config)
    print("Running PID BASELINE simulation for 288 ticks...")
    pid_sim.run()
    df_pid = pd.DataFrame(pid_sim.history)
    df_pid['scenario'] = 'PID'
    
    print("Simulations complete. Processing comparison results...")
    
    # Create an interactive Plotly dashboard of the run
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(
            "Weather Capacity Factors", 
            "Market Prices ($/MWh)", 
            "HVDC Converter Flow (MW) [Market vs PID]",
            "Grid Frequencies (Hz) [Market vs PID]"
        )
    )
    
    # 1. Weather (Shared)
    fig.add_trace(go.Scatter(x=df_market["tick"], y=df_market["cf_east"], name="East Weather CF", line=dict(color='orange')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_market["tick"], y=df_market["cf_west"], name="West Weather CF", line=dict(color='yellow')), row=1, col=1)
    
    # 2. Prices (Market only)
    fig.add_trace(go.Scatter(x=df_market["tick"], y=df_market["price_east"], name="East Price (Market)"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_market["tick"], y=df_market["price_west"], name="West Price (Market)"), row=2, col=1)
    
    # 3. Converter Flow (Comparison)
    fig.add_trace(go.Scatter(x=df_market["tick"], y=df_market["hvdc_flow_mw"], name="Flow Market (E->W)", 
                             fill='tozeroy', line=dict(color='blue')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_pid["tick"], y=df_pid["hvdc_flow_mw"], name="Flow PID (E->W)", 
                             line=dict(color='red', dash='dash')), row=3, col=1)
                             
    # 4. Frequencies (Comparison)
    fig.add_trace(go.Scatter(x=df_market["tick"], y=df_market["freq_east"], name="East Freq Market"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df_pid["tick"], y=df_pid["freq_east"], name="East Freq PID", line=dict(dash='dot')), row=4, col=1)
    
    fig.add_trace(go.Scatter(x=df_market["tick"], y=df_market["freq_west"], name="West Freq Market"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df_pid["tick"], y=df_pid["freq_west"], name="West Freq PID", line=dict(dash='dot')), row=4, col=1)
    
    fig.update_layout(
        title_text="FreqBridge 24-Hour Simulation Results",
        height=900,
        showlegend=True,
        template="plotly_dark"
    )
    
    # Save to data directory
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "simulation_results.html")
    fig.write_html(output_path)
    
    print(f"Results saved to: {os.path.abspath(output_path)}")
    print("Open this HTML file in your browser to view the interactive plots.")


if __name__ == "__main__":
    main()
