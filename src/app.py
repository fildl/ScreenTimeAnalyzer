import streamlit as st
import pandas as pd
import datetime

# Add src to path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from visualization.data_loader import load_usage_data
from visualization.visualizer import Visualizer
from main import ingest_files

# --- Config ---
st.set_page_config(
    page_title="Screen Time Analyzer",
    page_icon="📱",
    layout="wide"
)

# --- Auto Ingestion on Startup ---
if "data_ingested" not in st.session_state:
    with st.spinner("Checking and importing new data..."):
        try:
            ingest_files()
            st.cache_data.clear() # Clear cache to ensure fresh data load
        except Exception as e:
            st.error(f"Error during auto-ingestion: {e}")
    st.session_state["data_ingested"] = True

# --- Load Data ---
@st.cache_data
def get_data():
    return load_usage_data()

# --- Sidebar ---
st.sidebar.title("Screen Time Analyzer")

if st.sidebar.button("🔄 Update Data"):
    with st.sidebar.status("Ingesting new files...", expanded=True) as status:
        try:
            ingest_files()
            st.cache_data.clear()
            status.update(label="Data updated!", state="complete", expanded=False)
            st.rerun()
        except Exception as e:
            status.update(label="Error updating data", state="error")
            st.error(f"Error: {e}")

st.sidebar.markdown("---")

try:
    df = get_data()
    if df.empty:
        st.warning("No data found in database. Please run ingestion first.")
        st.stop()
        
    viz = Visualizer(df)
    
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# --- Sidebar ---
st.sidebar.title("Screen Time Analyzer")
st.sidebar.markdown("---")

# Year Filter
years = sorted(df['year'].unique().tolist(), reverse=True)
selected_year = st.sidebar.selectbox("Select Year", years, index=0)

# Device Filter
available_devices = ["All"] + sorted(df['device_name'].unique().tolist())
selected_device = st.sidebar.selectbox("Device", available_devices, index=0)

# --- Main Dashboard ---
st.title("📱 Screen Time Dashboard")

# Display current filters
filter_summary = f"**Year:** {selected_year}"
if selected_device != "All":
    filter_summary += f" • **Device:** {selected_device}"
    
st.markdown(f"Displaying data for: {filter_summary}")

# KPI Row
filtered_df = df[df['year'] == selected_year]
if selected_device != "All":
    filtered_df = filtered_df[filtered_df['device_name'] == selected_device]

total_hours = filtered_df['duration_seconds'].sum() / 3600
if not filtered_df.empty:
    days_span = (filtered_df['date'].max() - filtered_df['date'].min()).days + 1
    daily_avg_hours = (filtered_df['duration_seconds'].sum() / 3600) / max(days_span, 1)
else:
    daily_avg_hours = 0

top_app = filtered_df.groupby('app_name')['duration_seconds'].sum().idxmax() if not filtered_df.empty else "N/A"

col1, col2, col3 = st.columns(3)
col1.metric("Total Hours", f"{total_hours:.1f}h")
col2.metric("Daily Average", f"{daily_avg_hours:.1f}h")
col3.metric("Top App", top_app)

st.markdown("---")

# --- Visualizations ---

st.subheader("Weekly Activity")
fig_weekly = viz.plot_weekly_activity(year=selected_year, device=selected_device)
if fig_weekly:
    st.plotly_chart(fig_weekly, use_container_width=True)
else:
    st.info("No data available for this selection.")
