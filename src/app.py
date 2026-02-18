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
from database import get_uncategorized_apps, update_app_category, get_all_categories

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

# Year Filter
years = sorted(df['year'].unique().tolist(), reverse=True)
selected_year = st.sidebar.selectbox("Select Year", years, index=0)

# Device Filter
available_devices = ["All"] + sorted(df['device_name'].unique().tolist())
selected_device = st.sidebar.selectbox("Device", available_devices, index=0)

# --- Category Manager in Sidebar ---
st.sidebar.markdown("---")
with st.sidebar.expander("📂 Manage Categories"):
    # Mode Selection
    mode = st.radio("Mode", ["Categorize New", "Edit Existing"], horizontal=True)
    
    CATEGORIES = [
        "Social", "Productivity", "Study", "Entertainment", "Development", 
        "Utilities", "Information & Reading", "Creativity", "Other"
    ]
    
    app_to_edit = None
    default_cat_index = 0
    default_alias_val = ""

    if mode == "Categorize New":
        uncategorized = get_uncategorized_apps()
        if uncategorized:
            st.write(f"**{len(uncategorized)}** apps to categorize.")
            app_to_edit = st.selectbox("Select App", uncategorized)
            default_alias_val = app_to_edit
        else:
            st.success("🎉 All apps categorized!")
            
    else: # Edit Existing
        all_cats = get_all_categories()
        if all_cats:
            sorted_apps = sorted(all_cats.keys())
            app_to_edit = st.selectbox("Select App to Edit", sorted_apps)
            
            if app_to_edit:
                current_data = all_cats[app_to_edit]
                current_cat = current_data['category']
                current_alias = current_data['alias']
                
                # Update default values
                if current_cat in CATEGORIES:
                    default_cat_index = CATEGORIES.index(current_cat)
                default_alias_val = current_alias if current_alias else app_to_edit
        else:
            st.info("No categories found.")

    # Form (only if an app is selected)
    if app_to_edit:
        new_category = st.selectbox("Category", CATEGORIES, index=default_cat_index)
        new_alias = st.text_input("Alias", value=default_alias_val, help="Merge apps by giving them the same alias (e.g. 'YouTube')")
        
        if st.button("Save"):
            alias_val = new_alias if new_alias and new_alias != app_to_edit else None
            update_app_category(app_to_edit, new_category, alias_val)
            st.success(f"Saved: {app_to_edit} -> {new_category}")
            st.cache_data.clear() # Reload data
            st.rerun()

    st.markdown("---")
    if st.checkbox("Show All Mappings"):
        st.json(get_all_categories(), expanded=False)

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

st.subheader("Hourly Activity Patterns")
hourly_breakdown = st.radio("View by:", ["Device", "Category"], horizontal=True, key="hourly_breakdown")
fig_hourly = viz.plot_hourly_activity(year=selected_year, device=selected_device, breakdown=hourly_breakdown)
if fig_hourly:
    st.plotly_chart(fig_hourly, use_container_width=True)
else:
    st.info("No data available for this selection.")

st.subheader("Weekly Screen Time Activity")
weekly_breakdown = st.radio("View by:", ["Device", "Category"], horizontal=True, key="weekly_breakdown")
fig_weekly = viz.plot_weekly_activity(year=selected_year, device=selected_device, breakdown=weekly_breakdown)
if fig_weekly:
    st.plotly_chart(fig_weekly, use_container_width=True)
else:
    st.info("No data available for this selection.")

st.subheader("Daily Activity Calendar")
fig_calendar = viz.plot_daily_calendar(year=selected_year, device=selected_device)
if fig_calendar:
    st.plotly_chart(fig_calendar, use_container_width=True)
else:
    st.info("No data available for this selection.")

st.subheader("Usage Trends")
st.markdown("Long-term usage trend with 30-day moving average.")
fig_trend = viz.plot_usage_trend(year=selected_year, device=selected_device, window=30)
if fig_trend:
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("No data available for this selection.")
