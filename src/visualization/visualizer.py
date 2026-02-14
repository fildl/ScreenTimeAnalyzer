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
    
    DEVICE_COLORS = ['#26547c', '#ef476f', '#ffd166']
    
    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 600

    def __init__(self, data: pd.DataFrame):
        self.data = data

    def plot_weekly_activity(self, year: int = None, device: str = None):
        """
        Stacked Bar chart of average daily usage hours per week, split by Device.
        Stats are aggregated by Week and Device.
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

        # Aggregate duration per week and device, counting unique days
        aggregated = df.groupby(['week', 'device_name']).agg({
            'duration_seconds': 'sum',
            'date': 'nunique'
        }).reset_index()
        
        # Calculate Average Daily Hours for that week
        # Avoid division by zero by ensuring at least 1 day count (though nunique shouldn't be 0 if data exists)
        aggregated['days_count'] = aggregated['date'].clip(lower=1)
        aggregated['avg_daily_hours'] = (aggregated['duration_seconds'] / 3600) / aggregated['days_count']
        
        # Format for tooltip
        aggregated['formatted_time'] = aggregated.apply(
            lambda x: f"{x['avg_daily_hours']:.1f}h/day ({int(x['duration_seconds'] // 3600)}h total)", 
            axis=1
        )
        
        fig = px.bar(
            aggregated, 
            x='week', 
            y='avg_daily_hours',
            color='device_name',
            title=None,
            labels={'avg_daily_hours': 'Avg Daily Hours', 'week': 'Week', 'device_name': 'Device'},
            custom_data=['formatted_time', 'device_name'],
            color_discrete_sequence=self.DEVICE_COLORS
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
                title='Average Daily Hours'
            )
        )
        
        fig.update_traces(
            marker_line_width=0,
            hovertemplate="<br><b>%{customdata[1]}</b><br><b>Usage</b>: %{customdata[0]}<extra></extra>",
            hoverlabel=dict(bgcolor="black")
        )
        
        return fig

    def plot_daily_calendar(self, year: int = None, device: str = None):
        """
        3x4 Month Grid Scatter plot showing daily usage intensity.
        """
        import calendar
        from plotly.subplots import make_subplots
        import plotly.graph_objects as go
        
        df = self.data.copy()
        
        if year:
            df = df[df['year'] == year]
            
        if device and device != "All":
            df = df[df['device_name'] == device]

        if df.empty:
            return None
        
        # Aggregate daily usage
        daily = df.groupby('date')['duration_seconds'].sum().reset_index()
        daily['hours'] = daily['duration_seconds'] / 3600
        daily['date'] = pd.to_datetime(daily['date'])
        
        # Max usage for color normalization
        max_usage = daily['hours'].max() if not daily.empty else 1
        
        # Prepare subplots
        fig = make_subplots(
            rows=3, cols=4, 
            subplot_titles=[calendar.month_name[i] for i in range(1, 13)],
            vertical_spacing=0.08,
            horizontal_spacing=0.03
        )

        for month in range(1, 13):
            row = (month - 1) // 4 + 1
            col = (month - 1) % 4 + 1
            
            _, num_days = calendar.monthrange(year, month)
            dates = pd.date_range(start=f"{year}-{month:02d}-01", end=f"{year}-{month:02d}-{num_days}")
            
            month_df = pd.DataFrame({'date': dates})
            month_df = month_df.merge(daily[['date', 'hours']], on='date', how='left').fillna({'hours': 0})
            
            # Coordinates
            month_df['day_of_week'] = month_df['date'].dt.dayofweek
            
            # Weekly row calculation
            first_day_weekday = month_df.iloc[0]['date'].dayofweek
            month_df['day_idx'] = month_df['date'].dt.day - 1
            month_df['week_of_month'] = (month_df['day_idx'] + first_day_weekday) // 7
            
            month_df['hover_text'] = month_df.apply(
                lambda x: f"<b>{x['date'].strftime('%d %b')}</b><br>{x['hours']:.1f}h" if x['hours'] > 0 else f"<b>{x['date'].strftime('%d %b')}</b><br>No Data",
                axis=1
            )
            
            # Active vs Inactive
            active_df = month_df[month_df['hours'] > 0].copy()
            inactive_df = month_df[month_df['hours'] == 0].copy()
            
            # Inactive Trace
            fig.add_trace(
                go.Scatter(
                    x=inactive_df['day_of_week'],
                    y=5 - inactive_df['week_of_month'],
                    mode='markers',
                    marker=dict(size=10, color='#262730'),
                    hoverinfo='skip',
                    showlegend=False
                ),
                row=row, col=col
            )
            
            # Active Trace
            if not active_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=active_df['day_of_week'],
                        y=5 - active_df['week_of_month'],
                        mode='markers',
                        marker=dict(
                            size=10,
                            color=active_df['hours'],
                            colorscale='Viridis',
                            cmin=0,
                            cmax=max_usage,
                            showscale=(month == 12),
                            colorbar=dict(title="Hours", x=1.02, len=0.7) if month==12 else None
                        ),
                        text=active_df['hover_text'],
                        hoverinfo='text',
                        showlegend=False
                    ),
                    row=row, col=col
                )
                
            fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 6.5], row=row, col=col)
            fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 6.5], row=row, col=col)

        fig.update_layout(
            title=None,
            paper_bgcolor=self.THEME_COLORS['paper'],
            plot_bgcolor=self.THEME_COLORS['background'],
            font_color=self.THEME_COLORS['text'],
            width=self.PLOT_WIDTH,
            height=800,
            margin=dict(t=80, l=20, r=20, b=20)
        )
        
        return fig

    def plot_hourly_activity(self, year: int = None, device: str = None):
        """
        Bar chart showing average daily minutes per hour of the day (0-23).
        """
        df = self.data.copy()
        
        if year:
            df = df[df['year'] == year]
            
        if device and device != "All":
            df = df[df['device_name'] == device]

        if df.empty:
            return None
        
        # Calculate total days in the period to compute average
        # We use the actual data range or the full year? 
        # Using actual data range (min to max date) is safer.
        min_date = df['date'].min()
        max_date = df['date'].max()
        days_count = (max_date - min_date).days + 1
        days_count = max(days_count, 1) # Avoid division by zero

        # Aggregate duration per hour and device
        hourly = df.groupby(['hour', 'device_name'])['duration_seconds'].sum().reset_index()
        
        # Convert to Average Minutes per Day
        hourly['avg_minutes'] = (hourly['duration_seconds'] / 60) / days_count
        
        # Create Bar Plot
        fig = px.bar(
            hourly, 
            x='hour', 
            y='avg_minutes',
            color='device_name',
            title=None,
            labels={'avg_minutes': 'Avg Daily Minutes', 'hour': 'Hour of Day', 'device_name': 'Device'},
            custom_data=['device_name'],
            color_discrete_sequence=self.DEVICE_COLORS
        )
        
        fig.update_layout(
            paper_bgcolor=self.THEME_COLORS['paper'],
            plot_bgcolor=self.THEME_COLORS['background'],
            font_color=self.THEME_COLORS['text'],
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x",
            width=self.PLOT_WIDTH,
            height=500,
            margin=dict(t=50, l=50, r=50, b=50),
            xaxis=dict(
                tickmode='linear',
                tick0=0,
                dtick=1,
                range=[-0.5, 23.5],
                title="Hour",
                showgrid=False
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor=self.THEME_COLORS['grid'],
                title='Average Minutes / Day'
            )
        )
        
        fig.update_traces(
            marker_line_width=0,
            hovertemplate="<br><b>%{customdata[0]}</b><br><b>Avg</b>: %{y:.1f} min/day<extra></extra>",
            hoverlabel=dict(bgcolor="black")
        )
        
        return fig

