import os
import pandas as pd

def process_local_jepx():
    # The file the user downloaded
    input_path = r"W:\Zuup\spot_summary_2023.csv"
    
    print(f"Reading local JEPX data from {input_path}...")
    
    # Read the file. JEPX provides this in Shift-JIS
    df = pd.read_csv(input_path, encoding='shift_jis')
    
    # Let's pick a summer day with high solar for the duck curve demo
    # The date format in the file is 'YYYY/MM/DD'
    target_date = "2023/08/15"
    
    # Filter for the target date
    day_df = df[df.iloc[:, 0] == target_date].copy()
    
    # If not found, just grab the first 48 rows of whatever the first day is
    if day_df.empty:
        print(f"Could not find {target_date}, using the very first day in the file.")
        day_df = df.head(48).copy()
    else:
        print(f"Found exactly {len(day_df)} records for {target_date}.")
        
    # Column 5 (0-indexed) is System Price (Yen/kWh)
    # The columns are: Date, Period, ... , System Price
    sys_price_col = day_df.columns[5]
    
    output_df = pd.DataFrame({
        "period": range(1, 49),
        "time": [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in (0, 30)],
        "system_price_jpy_kwh": day_df[sys_price_col].values
    })
    
    # Convert to USD/MWh (Roughly * 7.0 for the simulation scale)
    output_df["price_usd_mwh"] = output_df["system_price_jpy_kwh"].astype(float) * 7.0
    
    # Clip to avoid exact 0.0 or negative numbers throwing off the market solver
    output_df["price_usd_mwh"] = output_df["price_usd_mwh"].clip(lower=0.1)
    
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    
    output_path = os.path.join(data_dir, "jepx_prices_sample.csv")
    output_df.to_csv(output_path, index=False)
    
    print(f"Successfully processed and saved real JEPX profile to: {output_path}")

if __name__ == "__main__":
    process_local_jepx()
