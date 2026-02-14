import sys
import os
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.visualization.data_loader import load_usage_data
from src.visualization.visualizer import Visualizer

def test_visualization():
    print("Testing Data Loader...")
    df = load_usage_data()
    if df.empty:
        print("WARNING: No data found in database. Cannot test visualization.")
        return
    
    print(f"Data Loaded: {len(df)} rows.")
    print(df.head())
    
    print("\nTesting Visualizer...")
    viz = Visualizer(df)
    
    try:
        fig = viz.plot_weekly_activity()
        if fig:
            print("Weekly Activity Chart generated successfully.")
            # print(fig) # Too verbose
        else:
            print("Weekly Activity Chart returned None (maybe empty filtered data?).")
    except Exception as e:
        print(f"ERROR generating chart: {e}")
        raise e

if __name__ == "__main__":
    test_visualization()
