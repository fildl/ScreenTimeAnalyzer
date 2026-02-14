import plotly.express as px
import pandas as pd

class Visualizer:
    """
    Handles generation of interactive Plotly charts for Screen Time data.
    """
    
    # Theme Configuration
    THEME_COLORS = {
        'background': '#0e1117', # Streamlit dark default
        'paper': '#0e1117',
        'text': '#fafafa',
        'grid': '#333333',
    }
    
    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 600

    def __init__(self, data: pd.DataFrame):
        self.data = data

    def plot_weekly_activity(self, year: int = None, device: str = None):
        """
        Stacked Bar chart of total usage hours per week, split by App.
        Stats are aggregated by Week and App.
        """
        df = self.data.copy()
        
        # Filter by year
        if year:
            df = df[df['year'] == year]
            
        # Filter by device
        if device and device != "All":
            df = df[df['device_name'] == device]
        
        if df.empty:
            return None
            
        title = 'Weekly Screen Time Activity'

        # Aggregate duration per week and device
        aggregated = df.groupby(['week', 'device_name']).agg({
            'duration_seconds': 'sum'
        }).reset_index()
        
        aggregated['hours'] = aggregated['duration_seconds'] / 3600
        
        # Format for tooltip
        aggregated['formatted_time'] = aggregated.apply(
            lambda x: f"{int(x['duration_seconds'] // 3600)}h {int((x['duration_seconds'] % 3600) // 60)}m", 
            axis=1
        )
        
        fig = px.bar(
            aggregated, 
            x='week', 
            y='hours',
            color='device_name',
            title=title,
            labels={'hours': 'Hours', 'week': 'Week', 'device_name': 'Device'},
            custom_data=['formatted_time', 'device_name']
        )
        
        # Styling
        fig.update_layout(
            paper_bgcolor=self.THEME_COLORS['paper'],
            plot_bgcolor=self.THEME_COLORS['background'],
            font_color=self.THEME_COLORS['text'],
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            hovermode="x",
            width=self.PLOT_WIDTH,
            height=self.PLOT_HEIGHT,
            margin=dict(t=80, l=50, r=50, b=50),
            xaxis=dict(
                showgrid=False,
                title=None,
                tickformat="%d %b %Y"
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor=self.THEME_COLORS['grid'],
                title='Usage Time (hours)'
            )
        )
        
        fig.update_traces(
            marker_line_width=0,
            hovertemplate="<br><b>%{customdata[1]}</b><br><b>Time</b>: %{customdata[0]}<extra></extra>",
            hoverlabel=dict(bgcolor="black")
        )
        
        return fig
