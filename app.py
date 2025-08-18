import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client
import os
from typing import Optional
import asyncio
import sys
import base64
from pathlib import Path

# Python 3.13 compatibility fix
if sys.version_info >= (3, 13):
    import asyncio
    if not asyncio._get_running_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

# COMPETITION DATES CONFIGURATION
COMPETITION_START = datetime(2025, 8, 11).date()  # Monday, August 11, 2025
COMPETITION_END = datetime(2025, 10, 5).date()    # Sunday, October 5, 2025
COMPETITION_WEEKS = 8  # 8 full weeks of competition

def get_competition_week_dates():
    """Get all competition week date ranges"""
    weeks = []
    current_monday = COMPETITION_START
    
    for week_num in range(1, COMPETITION_WEEKS + 1):
        sunday = current_monday + timedelta(days=6)
        # Make sure we don't go past competition end
        if sunday > COMPETITION_END:
            sunday = COMPETITION_END
        
        weeks.append({
            'week': week_num,
            'start': current_monday,
            'end': sunday,
            'label': f"Week {week_num} ({current_monday.strftime('%m/%d')} - {sunday.strftime('%m/%d')})"
        })
        
        current_monday += timedelta(days=7)
        if current_monday > COMPETITION_END:
            break
    
    return weeks

def get_current_competition_week():
    """Determine which competition week we're currently in"""
    today = datetime.now().date()
    
    if today < COMPETITION_START:
        return 0, "Pre-Competition"
    elif today > COMPETITION_END:
        return COMPETITION_WEEKS + 1, "Post-Competition"
    
    days_since_start = (today - COMPETITION_START).days
    current_week = (days_since_start // 7) + 1
    
    if current_week > COMPETITION_WEEKS:
        return COMPETITION_WEEKS + 1, "Post-Competition"
    
    return current_week, f"Week {current_week}"

def get_current_competition_week_dates():
    """Get the current competition week's Monday and Sunday dates"""
    today = datetime.now().date()
    
    if today < COMPETITION_START or today > COMPETITION_END:
        # If outside competition, return calendar week for compatibility
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday
    
    # Find which competition week we're in
    days_since_start = (today - COMPETITION_START).days
    current_week_num = (days_since_start // 7)
    
    # Calculate the Monday and Sunday of current competition week
    monday = COMPETITION_START + timedelta(days=current_week_num * 7)
    sunday = monday + timedelta(days=6)
    
    # Don't go past competition end
    if sunday > COMPETITION_END:
        sunday = COMPETITION_END
        
    return monday, sunday

def calculate_weekly_athlete_performance(hr_zones_df: pd.DataFrame, activities_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate weekly performance for each athlete across all competition weeks"""
    if hr_zones_df.empty:
        return pd.DataFrame()
    
    competition_weeks = get_competition_week_dates()
    weekly_data = []
    
    # Add date column to dataframes
    hr_zones_df['date'] = pd.to_datetime(hr_zones_df['start_date']).dt.date
    activities_df['date'] = pd.to_datetime(activities_df['start_date']).dt.date
    
    for week_info in competition_weeks:
        week_start = week_info['start']
        week_end = week_info['end']
        week_num = week_info['week']
        
        # Filter HR zones data for this week
        week_hr_data = hr_zones_df[
            (hr_zones_df['date'] >= week_start) & 
            (hr_zones_df['date'] <= week_end)
        ]
        
        # Filter activities data for this week
        week_activities = activities_df[
            (activities_df['date'] >= week_start) & 
            (activities_df['date'] <= week_end)
        ]
        
        if not week_hr_data.empty:
            # Calculate points for this week
            week_points = calculate_hr_zone_points(week_hr_data)
            
            for athlete in week_points.index:
                # Get cycling miles for this athlete this week
                athlete_activities = week_activities[
                    (week_activities['athlete_name'] == athlete) &
                    (week_activities['sport_type'].isin(['Ride', 'VirtualRide', 'Peloton', 'Bike']))
                ]
                cycling_miles = athlete_activities['distance'].sum() / 1609.344 if not athlete_activities.empty else 0
                
                # Get total activities for this athlete this week
                total_activities = len(week_activities[week_activities['athlete_name'] == athlete])
                
                weekly_data.append({
                    'Week': f"Week {week_num}",
                    'Week_Number': week_num,
                    'Athlete': athlete,
                    'Points': int(week_points.loc[athlete, 'zone_points']),
                    'Cycling_Miles': round(cycling_miles, 1),
                    'Activities': total_activities,
                    'Date_Range': week_info['label']
                })
    
    if weekly_data:
        weekly_df = pd.DataFrame(weekly_data)
        return weekly_df
    else:
        return pd.DataFrame()

# Page config with cycling theme
st.set_page_config(
    page_title="Bourbon Chasers Gran Fondo Competition",
    page_icon="🚴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper functions for image loading
def load_image_as_base64(image_path):
    """Convert image to base64 string for embedding in HTML/CSS"""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return None

# Load images at app start
assets_dir = Path(__file__).parent / "assets"
logo_b64 = load_image_as_base64(assets_dir / "logo.png")
sidebar_logo_b64 = load_image_as_base64(assets_dir / "sidebar-logo.png")

# Custom CSS for modern, cycling-themed styling + MOBILE RESPONSIVE
st.markdown("""
<style>
    /* Main app styling */
    .stApp {
        background: linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 100%);
    }
    
    /* Headers with cycling accent color */
    h1, h2, h3 {
        color: #00d4ff !important;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    /* NEW: Competition Status Banner */
    .competition-status {
        background: linear-gradient(135deg, rgba(255, 215, 0, 0.2) 0%, rgba(0, 212, 255, 0.2) 100%);
        border: 2px solid rgba(255, 215, 0, 0.5);
        border-radius: 15px;
        padding: 20px;
        margin: 20px 0;
        text-align: center;
        box-shadow: 0 10px 30px rgba(255, 215, 0, 0.3);
    }
    
    .competition-title {
        color: #ffd700;
        font-size: 1.8rem;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 10px;
        text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
    }
    
    .competition-dates {
        color: white;
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 10px;
    }
    
    .competition-week {
        color: #00d4ff;
        font-size: 1.1rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* NEW: Weekly Performance Table Styles */
    .weekly-performance-section {
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        border-radius: 20px;
        padding: 30px;
        margin: 30px 0;
        border: 2px solid rgba(0, 212, 255, 0.3);
        box-shadow: 0 15px 40px rgba(0, 212, 255, 0.2);
    }
    
    .weekly-performance-title {
        color: #00d4ff;
        font-size: 2.2rem;
        font-weight: 900;
        text-align: center;
        margin-bottom: 30px;
        text-transform: uppercase;
        letter-spacing: 3px;
        text-shadow: 0 0 30px rgba(0, 212, 255, 0.5);
    }
    
    /* NEW: Competition progress */
    .progress-bar {
        background: #2a2a2a;
        border-radius: 10px;
        height: 20px;
        margin: 15px 0;
        overflow: hidden;
    }
    
    .progress-fill {
        background: linear-gradient(90deg, #ffd700 0%, #00d4ff 100%);
        height: 100%;
        border-radius: 10px;
        transition: width 0.5s ease;
    }
    
    /* Metrics styling */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #00d4ff20;
        box-shadow: 0 4px 6px rgba(0, 212, 255, 0.1);
    }
    
    [data-testid="metric-container"] label {
        color: #00d4ff !important;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.8rem;
        letter-spacing: 1px;
    }
    
    [data-testid="metric-container"] [data-testid="metric-value"] {
        color: white !important;
        font-size: 1.8rem;
        font-weight: 700;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        background: linear-gradient(90deg, #1e1e1e 0%, #2a2a2a 100%);
        border-radius: 10px;
        padding: 5px;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #808080;
        font-weight: 600;
        background: transparent;
        border-radius: 8px;
        padding: 10px 20px;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
        color: white !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a1a 0%, #0f0f0f 100%);
        border-right: 1px solid #00d4ff30;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #00a8d4 0%, #007799 100%);
        box-shadow: 0 6px 12px rgba(0, 212, 255, 0.3);
        transform: translateY(-2px);
    }
    
    /* Dataframe styling */
    [data-testid="stDataFrame"] {
        background: #1e1e1e;
        border-radius: 10px;
        padding: 10px;
    }
    
    /* Select box styling */
    .stSelectbox > div > div {
        background: #2a2a2a;
        border: 1px solid #00d4ff30;
        border-radius: 8px;
    }
    
    /* Info boxes */
    .stAlert {
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        border: 1px solid #00d4ff30;
        border-radius: 10px;
    }
    
    /* KPI Card styling */
    .kpi-card {
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #00d4ff30;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .kpi-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0, 212, 255, 0.2);
        border-color: #00d4ff60;
    }
    
    .kpi-value {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 10px 0;
    }
    
    .kpi-label {
        color: #00d4ff;
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .kpi-sublabel {
        color: #808080;
        font-size: 0.8rem;
        margin-top: 5px;
    }
    
    /* Epic Leaderboard Styling - Completely Isolated */
    .epic-leaderboard {
        text-align: left !important;
        background: radial-gradient(ellipse at top, rgba(0, 212, 255, 0.1) 0%, rgba(0, 0, 0, 0.8) 70%);
        padding: 30px;
        border-radius: 20px;
        border: 2px solid rgba(0, 212, 255, 0.3);
        margin: 20px 0;
        box-shadow: 0 20px 60px rgba(0, 212, 255, 0.2);
        position: relative;
        overflow: hidden;
    }
    
    .epic-leaderboard::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: conic-gradient(from 0deg, transparent, rgba(0, 212, 255, 0.1), transparent, rgba(0, 212, 255, 0.1));
        animation: rotate 20s linear infinite;
        z-index: -1;
    }
    
    @keyframes rotate {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Leaderboard title with epic styling */
    .epic-title {
        text-align: center !important;
        font-size: 3rem !important;
        font-weight: 900 !important;
        background: linear-gradient(135deg, #ffd700 0%, #ff8c00 30%, #00d4ff 70%, #ffffff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 50px rgba(255, 215, 0, 0.5);
        margin-bottom: 10px !important;
        text-transform: uppercase;
        letter-spacing: 3px;
        position: relative;
    }
    
    .epic-subtitle {
        text-align: center !important;
        color: rgba(255, 255, 255, 0.8);
        font-size: 1.2rem;
        margin-bottom: 40px !important;
        font-style: italic;
        letter-spacing: 1px;
    }
    
    /* Full rankings section */
    .full-rankings {
        background: linear-gradient(135deg, rgba(0, 0, 0, 0.6) 0%, rgba(30, 30, 30, 0.8) 100%);
        border-radius: 20px;
        padding: 30px;
        margin-top: 40px;
        border: 1px solid rgba(0, 212, 255, 0.3);
        backdrop-filter: blur(10px);
    }
    
    .rankings-title {
        color: #00d4ff;
        font-size: 2rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 30px;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* Enhanced ranking cards */
    .epic-ranking-card {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(30, 30, 30, 0.9) 100%);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 15px;
        padding: 20px;
        margin: 15px 0;
        display: flex;
        align-items: center;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .epic-ranking-card::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        height: 100%;
        width: 5px;
        background: linear-gradient(180deg, #ffd700 0%, #00d4ff 50%, #ff6b6b 100%);
        transform: scaleY(0);
        transition: all 0.3s ease;
    }
    
    .epic-ranking-card:hover {
        transform: translateX(10px);
        box-shadow: 0 15px 40px rgba(0, 212, 255, 0.3);
        border-color: rgba(0, 212, 255, 0.8);
    }
    
    .epic-ranking-card:hover::before {
        transform: scaleY(1);
    }
    
    .rank-position {
        font-size: 2rem;
        font-weight: 900;
        color: #00d4ff;
        min-width: 60px;
        text-align: center;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
    }
    
    .athlete-details {
        flex-grow: 1;
        margin-left: 20px;
    }
    
    .athlete-name-full {
        color: white;
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 5px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .athlete-stats {
        display: flex;
        gap: 30px;
        align-items: center;
    }
    
    .stat-item {
        text-align: center;
    }
    
    .stat-value {
        color: #00d4ff;
        font-size: 1.4rem;
        font-weight: 700;
        display: block;
    }
    
    .stat-label {
        color: rgba(255, 255, 255, 0.7);
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
           
    /* Competition stats */
    .competition-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
        margin: 30px 0;
    }
    
    .stat-card {
        background: linear-gradient(135deg, rgba(255, 215, 0, 0.1) 0%, rgba(0, 212, 255, 0.1) 100%);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .stat-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(0, 212, 255, 0.2);
    }
    
    .stat-card-value {
        font-size: 2.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #ffd700 0%, #00d4ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
    }
    
    .stat-card-label {
        color: rgba(255, 255, 255, 0.8);
        font-size: 1rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    
    /* Force center alignment for all column content */
    .stColumn {
        text-align: center !important;
    }
    
    .stColumn > div {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100%;
        text-align: center !important;
    }
    
    /* Center and style metric containers */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        padding: 20px;
        border-radius: 15px;
        border: 2px solid #00d4ff30;
        box-shadow: 0 8px 32px rgba(0, 212, 255, 0.15);
        text-align: center !important;
        transition: all 0.3s ease;
        margin: 0 auto 15px auto;
        width: 90%;
        max-width: 320px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    
    [data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 40px rgba(0, 212, 255, 0.25);
        border-color: #00d4ff60;
        background: linear-gradient(135deg, #2a2a2a 0%, #353535 100%);
    }
    
    /* Force all metric container children to center */
    [data-testid="metric-container"] > div {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        text-align: center !important;
    }
    
    /* Force center alignment for all text elements in metrics */
    [data-testid="metric-container"] * {
        text-align: center !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    
    /* Style the metric label - force absolute centering */
    [data-testid="metric-container"] > div > label,
    [data-testid="metric-container"] label,
    [data-testid="stMetricLabel"] {
        color: #00d4ff !important;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.85rem !important;
        letter-spacing: 2px;
        text-align: center !important;
        width: 100% !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        margin: 0 auto 10px auto !important;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
    }
    
    /* Force metric label data element to center */
    [data-testid="stMetricLabel"] > div {
        text-align: center !important;
        width: 100% !important;
        display: flex !important;
        justify-content: center !important;
    }
    
    /* Target the specific label div */
    div[data-testid="metric-container"] div[data-testid="stMetricLabel"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        text-align: center !important;
    }
    
    /* Style the metric value */
    [data-testid="metric-container"] [data-testid="metric-value"] {
        color: white !important;
        font-size: 2.8rem !important;
        font-weight: 800;
        text-align: center !important;
        line-height: 1;
        background: linear-gradient(135deg, #ffffff 0%, #00d4ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 30px rgba(0, 212, 255, 0.5);
        display: block !important;
        width: 100% !important;
        margin: 0 auto !important;
    }
    
    /* Style the delta */
    [data-testid="metric-container"] [data-testid="metric-delta-negative"],
    [data-testid="metric-container"] [data-testid="metric-delta-positive"],
    [data-testid="metric-container"] [data-testid="metric-delta"] {
        color: #808080 !important;
        font-size: 0.9rem !important;
        text-align: center !important;
        margin: 8px auto 0 auto !important;
        font-style: italic;
        display: block !important;
        width: 100% !important;
    }
    
    /* Force all text elements in metric container to center */
    [data-testid="metric-container"] p,
    [data-testid="metric-container"] span,
    [data-testid="metric-container"] div {
        text-align: center !important;
        width: 100% !important;
    }
    
    /* Target metric labels specifically */
    p[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        margin: 0 auto !important;
    }
    
    /* Center any child elements of metric labels */
    [data-testid="stMetricLabel"] * {
        text-align: center !important;
        margin: 0 auto !important;
    }
    
    /* Remove delta arrow icon - comprehensive targeting */
    [data-testid="metric-container"] svg,
    [data-testid="metric-container"] [data-testid="metric-delta-negative"] svg,
    [data-testid="metric-container"] [data-testid="metric-delta-positive"] svg,
    [data-testid="metric-container"] [data-testid="metric-delta"] svg,
    [data-testid="stMetricDelta"] svg,
    [data-testid="metric-container"] path,
    [data-testid="metric-container"] [data-testid*="delta"] path {
        display: none !important;
        visibility: hidden !important;
        width: 0 !important;
        height: 0 !important;
    }
    
    /* Hide arrow containers */
    [data-testid="metric-container"] [data-testid*="delta"] > div:first-child,
    [data-testid="metric-container"] [data-testid*="delta"] > svg,
    [data-testid="stMetricDeltaIcon-Up"],
    [data-testid="stMetricDeltaIcon-Down"],
    div[data-testid^="stMetricDeltaIcon"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* Remove any arrow Unicode characters */
    [data-testid="metric-container"] [data-testid*="delta"]:before,
    [data-testid="metric-container"] [data-testid*="delta"]:after {
        content: '' !important;
    }
    
    /* Athlete card container */
    .athlete-card {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.05) 0%, rgba(0, 153, 204, 0.05) 100%);
        border-radius: 20px;
        padding: 25px 10px 30px 10px;
        margin: 0 auto 20px auto;
        border: 1px solid rgba(0, 212, 255, 0.2);
        backdrop-filter: blur(10px);
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 90%;
        max-width: 350px;
        text-align: center !important;
    }
    
    /* Add glow effect to athlete names */
    .athlete-name {
        color: white;
        font-size: 1.8rem;
        font-weight: 700;
        text-align: center !important;
        margin-bottom: 25px;
        margin-top: 0;
        text-transform: uppercase;
        letter-spacing: 3px;
        text-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
        position: relative;
        padding-bottom: 15px;
        width: 100%;
    }
    
    .athlete-name:after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 100px;
        height: 3px;
        background: linear-gradient(90deg, transparent, #00d4ff, transparent);
        border-radius: 2px;
    }
    
    /* Team totals section styling */
    .team-totals-header {
        color: #00d4ff;
        font-size: 1.8rem;
        font-weight: 700;
        text-align: center !important;
        margin: 40px 0 25px 0;
        text-transform: uppercase;
        letter-spacing: 3px;
        text-shadow: 0 0 30px rgba(0, 212, 255, 0.5);
    }
    
    /* Add pulse animation for emphasis */
    @keyframes pulse {
        0% {
            box-shadow: 0 8px 32px rgba(0, 212, 255, 0.15);
        }
        50% {
            box-shadow: 0 8px 40px rgba(0, 212, 255, 0.3);
        }
        100% {
            box-shadow: 0 8px 32px rgba(0, 212, 255, 0.15);
        }
    }
    
    [data-testid="metric-container"] {
        animation: pulse 3s infinite;
    }
    
    /* Global filter section styling */
    .global-filter {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(0, 153, 204, 0.1) 100%);
        border-radius: 20px;
        padding: 25px;
        margin: 20px 0 30px 0;
        border: 2px solid rgba(0, 212, 255, 0.3);
        box-shadow: 0 10px 40px rgba(0, 212, 255, 0.2);
    }
    
    .filter-title {
        color: #00d4ff;
        font-size: 1.8rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 20px;
        text-transform: uppercase;
        letter-spacing: 3px;
        text-shadow: 0 0 30px rgba(0, 212, 255, 0.5);
    }
    
    /* Enhanced tab content styling */
    .tab-content {
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        border-radius: 15px;
        padding: 25px;
        margin-top: 20px;
        border: 1px solid #00d4ff30;
    }
    
    .tab-title {
        color: #00d4ff;
        font-size: 2rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 25px;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* Athlete info banner */
    .athlete-banner {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.2) 0%, rgba(0, 153, 204, 0.2) 100%);
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 25px;
        border: 1px solid rgba(0, 212, 255, 0.4);
        text-align: center;
    }
    
    .athlete-name-banner {
        color: white;
        font-size: 1.5rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 2px;
        text-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
    }
    
    /* Performance summary cards */
    .summary-card {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(30, 30, 30, 0.9) 100%);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 15px;
        padding: 20px;
        margin: 15px 0;
        transition: all 0.3s ease;
    }
    
    .summary-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 40px rgba(0, 212, 255, 0.3);
        border-color: rgba(0, 212, 255, 0.8);
    }

    /* ==================== MOBILE RESPONSIVE STYLES ==================== */
    
    /* Mobile devices */
    @media screen and (max-width: 768px) {
        
        /* Main layout fixes */
        .stApp {
            padding: 0 !important;
            margin: 0 !important;
        }
        
        .main .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            max-width: 100% !important;
        }
        
        /* Header and logo mobile fixes */
        .stApp img {
            max-width: 100% !important;
            height: auto !important;
        }
        
        h1 {
            font-size: 1.8rem !important;
            line-height: 1.2 !important;
            text-align: center !important;
            margin-bottom: 0.5rem !important;
            word-break: break-word !important;
            hyphens: auto !important;
        }
        
        h2 {
            font-size: 1.4rem !important;
            line-height: 1.3 !important;
            text-align: center !important;
            margin-bottom: 0.5rem !important;
            word-break: break-word !important;
        }
        
        h3 {
            font-size: 1.2rem !important;
            line-height: 1.3 !important;
            text-align: center !important;
            margin-bottom: 0.5rem !important;
            word-break: break-word !important;
        }
        
        /* Competition status banner mobile */
        .competition-status {
            margin: 10px 5px !important;
            padding: 15px !important;
            border-radius: 10px !important;
        }
        
        .competition-title {
            font-size: 1.2rem !important;
            letter-spacing: 1px !important;
            line-height: 1.3 !important;
            word-break: break-word !important;
            hyphens: auto !important;
        }
        
        .competition-dates {
            font-size: 0.9rem !important;
            line-height: 1.3 !important;
            margin-bottom: 8px !important;
            word-break: break-word !important;
        }
        
        .competition-week {
            font-size: 0.8rem !important;
            line-height: 1.3 !important;
            word-break: break-word !important;
        }
        
        /* Epic leaderboard mobile fixes */
        .epic-leaderboard {
            margin: 10px 5px !important;
            padding: 15px !important;
            border-radius: 15px !important;
        }
        
        .epic-title {
            font-size: 1.5rem !important;
            letter-spacing: 1px !important;
            line-height: 1.2 !important;
            word-break: break-word !important;
            hyphens: auto !important;
        }
        
        .epic-subtitle {
            font-size: 0.9rem !important;
            margin-bottom: 20px !important;
            line-height: 1.3 !important;
        }
        
        /* Ranking cards mobile */
        .epic-ranking-card {
            flex-direction: column !important;
            text-align: center !important;
            padding: 15px !important;
            margin: 10px 0 !important;
        }
        
        .rank-position {
            font-size: 1.5rem !important;
            margin-bottom: 10px !important;
            min-width: auto !important;
        }
        
        .athlete-details {
            margin-left: 0 !important;
            width: 100% !important;
        }
        
        .athlete-name-full {
            font-size: 1.1rem !important;
            letter-spacing: 0.5px !important;
            margin-bottom: 10px !important;
            word-break: break-word !important;
        }
        
        .athlete-stats {
            flex-direction: column !important;
            gap: 10px !important;
            align-items: center !important;
        }
        
        .stat-item {
            margin: 5px 0 !important;
        }
        
        .stat-value {
            font-size: 1.2rem !important;
        }
        
        .stat-label {
            font-size: 0.75rem !important;
        }
        
        /* Competition stats grid mobile */
        .competition-stats {
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 10px !important;
            margin: 20px 0 !important;
        }
        
        .stat-card {
            padding: 15px !important;
            border-radius: 10px !important;
        }
        
        .stat-card-value {
            font-size: 1.8rem !important;
            margin-bottom: 8px !important;
        }
        
        .stat-card-label {
            font-size: 0.8rem !important;
            letter-spacing: 0.5px !important;
            line-height: 1.3 !important;
            word-break: break-word !important;
        }
        
        /* Weekly performance section mobile */
        .weekly-performance-section {
            margin: 20px 5px !important;
            padding: 15px !important;
            border-radius: 15px !important;
        }
        
        .weekly-performance-title {
            font-size: 1.4rem !important;
            letter-spacing: 1px !important;
            margin-bottom: 20px !important;
            line-height: 1.3 !important;
            word-break: break-word !important;
        }
        
        /* Streamlit component mobile fixes */
        .stColumn {
            min-width: 100% !important;
            width: 100% !important;
            padding: 0 5px !important;
            margin-bottom: 15px !important;
        }
        
        [data-testid="metric-container"] {
            margin: 10px auto !important;
            padding: 15px !important;
            width: 95% !important;
            max-width: none !important;
            border-radius: 10px !important;
        }
        
        [data-testid="metric-container"] label {
            font-size: 0.75rem !important;
            letter-spacing: 1px !important;
            line-height: 1.3 !important;
            word-break: break-word !important;
        }
        
        [data-testid="metric-container"] [data-testid="metric-value"] {
            font-size: 2rem !important;
            line-height: 1.1 !important;
        }
        
        /* Fix dataframes for mobile */
        [data-testid="stDataFrame"] {
            font-size: 0.8rem !important;
            padding: 5px !important;
            border-radius: 8px !important;
        }
        
        [data-testid="stDataFrame"] > div {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
        }
        
        /* Fix selectboxes for mobile */
        .stSelectbox > div > div {
            font-size: 0.9rem !important;
            padding: 8px !important;
        }
        
        /* Fix tabs for mobile */
        .stTabs [data-baseweb="tab-list"] {
            padding: 3px !important;
            border-radius: 8px !important;
        }
        
        .stTabs [data-baseweb="tab"] {
            font-size: 0.85rem !important;
            padding: 8px 12px !important;
            border-radius: 6px !important;
        }
        
        /* Fix buttons for mobile */
        .stButton > button {
            font-size: 0.85rem !important;
            padding: 8px 16px !important;
            border-radius: 6px !important;
            letter-spacing: 0.5px !important;
            width: 100% !important;
        }
        
        /* Athlete cards mobile */
        .athlete-card {
            width: 95% !important;
            max-width: none !important;
            margin: 10px auto !important;
            padding: 15px 10px 20px 10px !important;
            border-radius: 15px !important;
        }
        
        .athlete-name {
            font-size: 1.3rem !important;
            letter-spacing: 1px !important;
            line-height: 1.3 !important;
            margin-bottom: 15px !important;
            word-break: break-word !important;
        }
        
        /* Filter sections mobile */
        .global-filter {
            margin: 15px 5px !important;
            padding: 15px !important;
            border-radius: 15px !important;
        }
        
        .filter-title {
            font-size: 1.3rem !important;
            letter-spacing: 1px !important;
            line-height: 1.3 !important;
            margin-bottom: 15px !important;
            word-break: break-word !important;
        }
        
        .athlete-banner {
            margin: 15px 5px !important;
            padding: 15px !important;
            border-radius: 12px !important;
        }
        
        .athlete-name-banner {
            font-size: 1.2rem !important;
            letter-spacing: 1px !important;
            line-height: 1.3 !important;
            word-break: break-word !important;
        }
        
        /* Tab content mobile */
        .tab-content {
            margin: 15px 5px !important;
            padding: 15px !important;
            border-radius: 12px !important;
        }
        
        .tab-title {
            font-size: 1.4rem !important;
            letter-spacing: 1px !important;
            margin-bottom: 20px !important;
            line-height: 1.3 !important;
            word-break: break-word !important;
        }
        
        /* Summary cards mobile */
        .summary-card {
            margin: 10px 5px !important;
            padding: 15px !important;
            border-radius: 12px !important;
        }
        
        .summary-card h4 {
            font-size: 1.1rem !important;
            margin-bottom: 15px !important;
            line-height: 1.3 !important;
            word-break: break-word !important;
        }
        
        /* Sidebar mobile */
        section[data-testid="stSidebar"] {
            width: 280px !important;
        }
        
        section[data-testid="stSidebar"] .stMarkdown {
            font-size: 0.85rem !important;
        }
        
        section[data-testid="stSidebar"] .stButton > button {
            font-size: 0.8rem !important;
            padding: 6px 12px !important;
            width: 100% !important;
        }
        
        /* General text improvements */
        p {
            font-size: 0.9rem !important;
            line-height: 1.4 !important;
            word-break: break-word !important;
        }
        
        .stMarkdown {
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
            hyphens: auto !important;
        }
        
        /* Spacing improvements */
        .element-container {
            margin-bottom: 0.5rem !important;
        }
        
        .row-widget {
            margin-bottom: 0.5rem !important;
        }
        
        /* Progress bar mobile */
        .progress-bar {
            height: 15px !important;
            margin: 10px 0 !important;
            border-radius: 8px !important;
        }
        
        .progress-fill {
            border-radius: 8px !important;
        }
    }
    
    /* Small mobile devices (phones in portrait) */
    @media screen and (max-width: 480px) {
        
        .epic-title {
            font-size: 1.2rem !important;
            letter-spacing: 0.5px !important;
        }
        
        .competition-title {
            font-size: 1rem !important;
            letter-spacing: 0.5px !important;
        }
        
        .competition-stats {
            grid-template-columns: 1fr !important;
            gap: 8px !important;
        }
        
        .stat-card-value {
            font-size: 1.5rem !important;
        }
        
        .stat-card-label {
            font-size: 0.75rem !important;
        }
        
        h1 {
            font-size: 1.5rem !important;
        }
        
        h2 {
            font-size: 1.2rem !important;
        }
        
        h3 {
            font-size: 1.1rem !important;
        }
        
        .athlete-name {
            font-size: 1.1rem !important;
            letter-spacing: 0.5px !important;
        }
        
        [data-testid="metric-container"] [data-testid="metric-value"] {
            font-size: 1.8rem !important;
        }
        
        [data-testid="metric-container"] label {
            font-size: 0.7rem !important;
        }
        
        .stColumn {
            width: 100% !important;
            margin-bottom: 20px !important;
        }
    }
    
    /* Tablet landscape fixes */
    @media screen and (min-width: 769px) and (max-width: 1024px) {
        
        .epic-title {
            font-size: 2.2rem !important;
        }
        
        .competition-stats {
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 15px !important;
        }
        
        .epic-ranking-card {
            flex-direction: row !important;
            text-align: left !important;
        }
        
        .athlete-stats {
            flex-direction: row !important;
            gap: 20px !important;
        }
        
        .rank-position {
            font-size: 1.8rem !important;
            min-width: 50px !important;
        }
    }
    
    /* Accessibility improvements */
    @media (hover: none) and (pointer: coarse) {
        
        button, 
        .stButton > button,
        .stSelectbox,
        .stDateInput {
            min-height: 44px !important;
            min-width: 44px !important;
        }
        
        .epic-ranking-card:active,
        .stat-card:active,
        .summary-card:active {
            transform: scale(0.98) !important;
            transition: transform 0.1s ease !important;
        }
    }
    
    /* Force responsiveness */
    * {
        box-sizing: border-box !important;
    }
    
    img {
        max-width: 100% !important;
        height: auto !important;
    }
    
    table {
        width: 100% !important;
        table-layout: fixed !important;
    }
    
    .main {
        overflow-x: hidden !important;
    }
    
    .stApp * {
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
    
</style>
""", unsafe_allow_html=True)

# Initialize Supabase client
@st.cache_resource
def init_supabase() -> Client:
    """Initialize Supabase client with credentials"""
    url = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
    key = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))
    
    if not url or not key:
        st.error("⚠️ Please set SUPABASE_URL and SUPABASE_KEY in secrets or environment variables")
        st.stop()
    
    return create_client(url, key)

# Data fetching functions
@st.cache_data(ttl=60)  # Cache for 1 minute
def fetch_athletes(_supabase: Client) -> pd.DataFrame:
    """Fetch all athletes from database"""
    response = _supabase.table('athletes').select("*").execute()
    return pd.DataFrame(response.data)

@st.cache_data(ttl=60)
def fetch_activities_by_date_range(_supabase: Client, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch activities within date range with athlete info"""
    
    response = _supabase.table('activities')\
        .select("*, athletes(firstname, lastname)")\
        .gte('start_date', start_date)\
        .lte('start_date', end_date)\
        .order('start_date', desc=True)\
        .execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        # Flatten athlete info
        df['athlete_name'] = df['athletes'].apply(
            lambda x: f"{x['firstname']} {x['lastname']}" if x else "Unknown"
        )
        df = df.drop('athletes', axis=1)
        
        # Clean activity names and sport types - handle all formats
        def clean_field(value):
            if not isinstance(value, str):
                return value
            # Remove various root= formats
            if value.startswith("root='") and value.endswith("'"):
                cleaned = value[6:-1]  # Remove root=' from start and ' from end
            elif value.startswith('root="') and value.endswith('"'):
                cleaned = value[6:-1]  # Remove root=" from start and " from end
            elif value.startswith('root='):
                cleaned = value[5:]  # Remove root= prefix
                # Also remove quotes if present
                if cleaned.startswith("'") and cleaned.endswith("'"):
                    cleaned = cleaned[1:-1]
                elif cleaned.startswith('"') and cleaned.endswith('"'):
                    cleaned = cleaned[1:-1]
            else:
                cleaned = value
            
            # Apply specific replacements
            if cleaned == 'Ride':
                return 'Peloton'
            elif cleaned == 'Run':
                return 'Run'
            else:
                return cleaned
        
        # Clean both name and sport_type fields
        df['name'] = df['name'].apply(clean_field)
        df['sport_type'] = df['sport_type'].apply(clean_field)
        
        # Distinguish between Bike and Peloton based on elevation
        # If sport_type is 'Peloton' (converted from 'Ride') and has elevation, it's actually a bike ride
        mask_peloton_with_elevation = (df['sport_type'] == 'Peloton') & (df['total_elevation_gain'] > 0)
        df.loc[mask_peloton_with_elevation, 'sport_type'] = 'Bike'
        
        # Filter out non-competition activities like Tennis
        df = df[df['sport_type'] != 'Tennis']
        
        return df
    return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_heart_rate_zones_by_date(_supabase: Client, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch heart rate zone data for specified date range"""
    
    response = _supabase.table('heart_rate_zones')\
        .select("*, activities(athlete_id, name, start_date, sport_type, athletes(firstname, lastname))")\
        .gte('activities.start_date', start_date)\
        .lte('activities.start_date', end_date)\
        .execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        # Initialize new columns
        df['athlete_id'] = None
        df['athlete_name'] = None
        df['activity_name'] = None
        df['start_date'] = None
        df['sport_type'] = None
        
        # Flatten nested data properly
        for idx, row in df.iterrows():
            if row['activities']:
                df.at[idx, 'athlete_id'] = row['activities'].get('athlete_id')
                activity_name = row['activities'].get('name', '')
                
                # Clean activity names - handle specific replacements
                if isinstance(activity_name, str):
                    if activity_name.startswith("root='") and activity_name.endswith("'"):
                        cleaned = activity_name[6:-1]  # Remove root=' from start and ' from end
                        if cleaned == 'Ride':
                            df.at[idx, 'activity_name'] = 'Peloton'
                        elif cleaned == 'Run':
                            df.at[idx, 'activity_name'] = 'Treadmill'
                        else:
                            df.at[idx, 'activity_name'] = cleaned
                    elif activity_name.startswith('root='):
                        cleaned = activity_name[5:]  # Remove root= prefix
                        if cleaned == 'Ride':
                            df.at[idx, 'activity_name'] = 'Peloton'
                        elif cleaned == 'Run':
                            df.at[idx, 'activity_name'] = 'Treadmill'
                        else:
                            df.at[idx, 'activity_name'] = cleaned
                    else:
                        df.at[idx, 'activity_name'] = activity_name
                else:
                    df.at[idx, 'activity_name'] = activity_name
                    
                df.at[idx, 'start_date'] = row['activities'].get('start_date')
                df.at[idx, 'sport_type'] = row['activities'].get('sport_type')
                if row['activities'].get('athletes'):
                    athlete = row['activities']['athletes']
                    df.at[idx, 'athlete_name'] = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
        
        # Drop the nested column
        df = df.drop('activities', axis=1)
        
        # Remove rows without athlete_name
        df = df[df['athlete_name'].notna()]
        
        # Filter out non-competition activities like Tennis
        df = df[df['sport_type'] != 'Tennis']
        
        # Remove duplicate heart rate zone records for the same activity
        # This could happen if there are multiple HR zone entries for one activity
        if 'activity_id' in df.columns and len(df) > 0:
            original_count = len(df)
            df = df.drop_duplicates(subset=['activity_id'], keep='first')
            if len(df) != original_count:
                # Note: This debug message will be captured in the function
                pass
        
        return df
    return pd.DataFrame()

def calculate_hr_zone_points(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate HR zone points for each athlete"""
    if df.empty or 'athlete_name' not in df.columns:
        return pd.DataFrame()
    
    # Filter out rows without athlete_name
    df = df[df['athlete_name'].notna()]
    
    if df.empty:
        return pd.DataFrame()
    
    # Check for duplicate activity_ids that could cause point inflation
    if 'activity_id' in df.columns:
        original_count = len(df)
        duplicate_activities = df[df.duplicated('activity_id', keep=False)]
        if not duplicate_activities.empty:
            # Remove duplicates, keeping the first occurrence
            df = df.drop_duplicates('activity_id', keep='first')
            # Add debug info in sidebar for troubleshooting
            if len(df) != original_count:
                st.sidebar.warning(f"⚠️ Removed {original_count - len(df)} duplicate HR zone records")
    
    # Calculate points for each activity
    # Use zone_X_seconds columns from database (convert to minutes by dividing by 60)
    # Points calculation: Zone minutes × zone factor (1-5)
    df['zone_points'] = (
        (df.get('zone_1_seconds', df.get('zone_1_time', 0)).fillna(0) / 60) * 1 +
        (df.get('zone_2_seconds', df.get('zone_2_time', 0)).fillna(0) / 60) * 2 +
        (df.get('zone_3_seconds', df.get('zone_3_time', 0)).fillna(0) / 60) * 3 +
        (df.get('zone_4_seconds', df.get('zone_4_time', 0)).fillna(0) / 60) * 4 +
        (df.get('zone_5_seconds', df.get('zone_5_time', 0)).fillna(0) / 60) * 5
    )
    
    # Group by athlete - use correct column names (seconds or time)
    agg_dict = {
        'zone_points': 'sum',
        'activity_id': 'count'
    }
    
    # Add zone columns that actually exist in the dataframe
    for i in range(1, 6):
        if f'zone_{i}_seconds' in df.columns:
            agg_dict[f'zone_{i}_seconds'] = 'sum'
        elif f'zone_{i}_time' in df.columns:
            agg_dict[f'zone_{i}_time'] = 'sum'
    
    athlete_points = df.groupby('athlete_name').agg(agg_dict).round(0)
    
    athlete_points = athlete_points.rename(columns={'activity_id': 'activity_count'})
    athlete_points = athlete_points.sort_values('zone_points', ascending=False)
    
    return athlete_points

def calculate_athlete_cycling_stats(activities_df: pd.DataFrame, hr_zones_df: pd.DataFrame) -> dict:
    """Calculate cycling-specific stats for each athlete"""
    stats = {}
    
    if activities_df.empty:
        return stats
    
    # Get current competition week's Monday and Sunday
    monday, sunday = get_current_competition_week_dates()
    
    # Convert dates for filtering
    activities_df['date'] = pd.to_datetime(activities_df['start_date']).dt.date
    
    # Get unique athletes
    athletes = activities_df['athlete_name'].unique()
    
    for athlete in athletes:
        athlete_activities = activities_df[activities_df['athlete_name'] == athlete]
        
        # Filter for cycling activities (Ride, VirtualRide, Peloton, Bike)
        cycling_activities = athlete_activities[
            athlete_activities['sport_type'].isin(['Ride', 'VirtualRide', 'Peloton', 'Bike'])
        ]
        
        # Total cycling miles (all time in the selected date range)
        total_cycling_miles = cycling_activities['distance'].sum() / 1609.344 if not cycling_activities.empty else 0
        
        # Weekly cycling miles (current week)
        weekly_activities = cycling_activities[
            (cycling_activities['date'] >= monday) & 
            (cycling_activities['date'] <= sunday)
        ]
        weekly_cycling_miles = weekly_activities['distance'].sum() / 1609.344 if not weekly_activities.empty else 0
        
        # Weekly HR zone points (current week)
        weekly_zone_points = 0
        if not hr_zones_df.empty and 'athlete_name' in hr_zones_df.columns:
            hr_zones_df['date'] = pd.to_datetime(hr_zones_df['start_date']).dt.date
            weekly_hr_data = hr_zones_df[
                (hr_zones_df['athlete_name'] == athlete) &
                (hr_zones_df['date'] >= monday) & 
                (hr_zones_df['date'] <= sunday)
            ]
            if not weekly_hr_data.empty:
                weekly_points_df = calculate_hr_zone_points(weekly_hr_data)
                if not weekly_points_df.empty and 'zone_points' in weekly_points_df.columns:
                    weekly_zone_points = weekly_points_df['zone_points'].sum()
        
        stats[athlete] = {
            'total_cycling_miles': total_cycling_miles,
            'weekly_cycling_miles': weekly_cycling_miles,
            'weekly_zone_points': weekly_zone_points
        }
    
    return stats

def format_duration(seconds: Optional[float]) -> str:
    """Format duration from seconds to readable format"""
    if not seconds or pd.isna(seconds):
        return "N/A"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def format_distance(meters: Optional[float]) -> str:
    """Format distance from meters to miles"""
    if not meters or pd.isna(meters):
        return "N/A"
    
    miles = meters / 1609.344  # Convert meters to miles
    return f"{miles:.2f} mi"

def meters_to_miles(meters: Optional[float]) -> float:
    """Convert meters to miles"""
    if not meters or pd.isna(meters):
        return 0
    return meters / 1609.344

def mps_to_mph(mps: Optional[float]) -> float:
    """Convert meters per second to miles per hour"""
    if not mps or pd.isna(mps):
        return 0
    return mps * 2.237

def calculate_weekly_mileage(activities_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate weekly mileage by sport type for current week"""
    if activities_df.empty:
        return pd.DataFrame()
    
    # Get current competition week's Monday and Sunday
    monday, sunday = get_current_competition_week_dates()
    
    # Filter for current week
    df = activities_df.copy()
    df['date'] = pd.to_datetime(df['start_date']).dt.date
    current_week = df[(df['date'] >= monday) & (df['date'] <= sunday)]
    
    if current_week.empty:
        return pd.DataFrame()
    
    # Group by sport type and calculate total distance
    weekly_stats = current_week.groupby('sport_type').agg({
        'distance': lambda x: x.sum() / 1609.344,  # Convert to miles
        'moving_time': lambda x: x.sum() / 3600,   # Convert to hours
        'name': 'count'  # Count of activities
    }).round(2)
    
    weekly_stats.columns = ['Miles', 'Hours', 'Activities']
    weekly_stats = weekly_stats.sort_values('Miles', ascending=False)
    
    return weekly_stats

def calculate_athlete_streaks(activities_df: pd.DataFrame) -> dict:
    """Calculate current activity streaks for all athletes"""
    if activities_df.empty:
        return {}
    
    # Prepare data
    df = activities_df.copy()
    df['date'] = pd.to_datetime(df['start_date']).dt.date
    
    # Check if athlete_name column exists (it should from fetch_activities_by_date_range)
    if 'athlete_name' not in df.columns:
        return {}
    
    today = datetime.now().date()
    streaks = {}
    
    # Calculate streak for each athlete
    for athlete in df['athlete_name'].unique():
        athlete_dates = df[df['athlete_name'] == athlete]['date'].drop_duplicates().sort_values(ascending=False)
        
        if athlete_dates.empty:
            streaks[athlete] = 0
            continue
        
        # Check if they have an activity today or yesterday (to account for different time zones)
        latest_activity = athlete_dates.iloc[0]
        days_since_last = (today - latest_activity).days
        
        if days_since_last > 1:
            streaks[athlete] = 0
            continue
        
        # Calculate consecutive days working backwards from latest activity
        current_streak = 1
        expected_date = latest_activity - timedelta(days=1)
        
        # Check each previous day for consecutive activities
        for i in range(1, len(athlete_dates)):
            activity_date = athlete_dates.iloc[i]
            
            if activity_date == expected_date:
                current_streak += 1
                expected_date -= timedelta(days=1)
            else:
                # Gap found, break
                break
        
        streaks[athlete] = current_streak
    
    return streaks

def get_streak_badge(streak_days: int) -> dict:
    """Get badge emoji and description for streak length"""
    if streak_days >= 30:
        return {"emoji": "🏆", "name": "Legend", "color": "#FFD700"}
    elif streak_days >= 14:
        return {"emoji": "🔥", "name": "Fire", "color": "#FF4500"}
    elif streak_days >= 7:
        return {"emoji": "⚡", "name": "Lightning", "color": "#1E90FF"}
    elif streak_days >= 3:
        return {"emoji": "⭐", "name": "Star", "color": "#32CD32"}
    else:
        return {"emoji": "", "name": "", "color": "#808080"}


# Main app
def main():
    # Cache clearing button for debugging
    if st.sidebar.button("🔄 Clear Cache & Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    # NEW: Competition status banner at the very top
    current_week_num, current_week_status = get_current_competition_week()
    today = datetime.now().date()
    
    # Calculate competition progress
    if today < COMPETITION_START:
        days_until_start = (COMPETITION_START - today).days
        progress_percent = 0
        status_text = f"🚀 Competition starts in {days_until_start} days!"
    elif today > COMPETITION_END:
        progress_percent = 100
        status_text = "🏁 Competition Complete!"
    else:
        total_days = (COMPETITION_END - COMPETITION_START).days + 1
        days_elapsed = (today - COMPETITION_START).days + 1
        progress_percent = (days_elapsed / total_days) * 100
        days_remaining = (COMPETITION_END - today).days
        status_text = f"🔥 {current_week_status} • {days_remaining} days remaining"
    
    st.markdown(f"""
    <div class="competition-status">
        <div class="competition-title">🏆 BOURBON CHASERS GRAN FONDO COMPETITION 🏆</div>
        <div class="competition-dates">August 11 - October 5, 2025 • 8 Weeks of Competition</div>
        <div class="competition-week">{status_text}</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {progress_percent}%;"></div>
        </div>
        <div style="color: rgba(255, 255, 255, 0.8); margin-top: 10px;">
            Progress: {progress_percent:.1f}% Complete
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Modern header with logo (YOUR ORIGINAL CODE)
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        if logo_b64:
            st.markdown(f"""
            <div style='text-align: center; padding: 20px;'>
                <img src='data:image/png;base64,{logo_b64}' 
                     style='max-width: 400px; width: 100%; height: auto; margin-bottom: 20px;'
                     alt='Cycling Performance Hub Logo'>
                <h1 style='font-size: 2.5rem; background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%); 
                           -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                           margin-bottom: 10px;'>
                    BOURBON CHASERS CYCLING PERFORMANCE HUB
                </h1>
                <p style='color: #808080; font-size: 1.2rem; font-weight: 300; letter-spacing: 2px;'>
                    HINCAPIE GRAN FONDO TRAINING DASHBOARD
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Fallback if logo doesn't load
            st.markdown("""
            <div style='text-align: center; padding: 20px;'>
                <h1 style='font-size: 3rem; background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%); 
                           -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                           margin-bottom: 10px;'>
                    🚴 CYCLING PERFORMANCE HUB
                </h1>
                <p style='color: #808080; font-size: 1.2rem; font-weight: 300; letter-spacing: 2px;'>
                    HINCAPIE GRAN FONDO TRAINING DASHBOARD
                </p>
            </div>
            """, unsafe_allow_html=True)
    
    # Initialize Supabase
    supabase = init_supabase()
    
    # Sidebar with logo (YOUR ORIGINAL CODE + ENHANCED COMPETITION CONTROLS)
    with st.sidebar:
        # Display sidebar logo at the top
        if sidebar_logo_b64:
            st.markdown(f"""
            <div style='text-align: center; padding: 10px 0 20px 0;'>
                <img src='data:image/png;base64,{sidebar_logo_b64}' 
                     style='max-width: 250px; width: 95%; height: auto; margin-bottom: 15px;'
                     alt='Sidebar Logo'>
                <h2 style='color: #00d4ff; margin: 0;'>⚙️ COMPETITION CONTROLS</h2>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='text-align: center; padding: 20px 0;'>
                <h2 style='color: #00d4ff;'>⚙️ COMPETITION CONTROLS</h2>
            </div>
            """, unsafe_allow_html=True)
        
        # Calendar date range selector
        st.markdown("""
        <div style='background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%); 
                    padding: 15px; border-radius: 10px; border: 1px solid #00d4ff30; margin-bottom: 20px;'>
            <p style='color: #00d4ff; font-size: 0.9rem; margin: 0 0 10px 0; font-weight: 600;'>
                📅 ANALYSIS DATE RANGE
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # NEW: Quick selection buttons with smart logic
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏆 Full Competition", use_container_width=True):
                if today >= COMPETITION_START:
                    st.session_state['start_date'] = COMPETITION_START
                    st.session_state['end_date'] = min(today, COMPETITION_END)
                else:
                    # Pre-competition: show last 30 days
                    st.session_state['start_date'] = today - timedelta(days=30)
                    st.session_state['end_date'] = today
                st.rerun()
        with col2:
            if st.button("📅 Current Week", use_container_width=True):
                monday, sunday = get_current_competition_week_dates()
                st.session_state['start_date'] = monday
                st.session_state['end_date'] = min(sunday, today)
                st.rerun()
        
        # NEW: Date inputs with smart competition defaults
        today = datetime.now().date()
        
        # Smart default logic based on current date
        if today < COMPETITION_START:
            # Pre-competition: Show recent data leading up to competition
            default_start = today - timedelta(days=30)
            default_end = today
        elif today > COMPETITION_END:
            # Post-competition: Default to full competition period
            default_start = COMPETITION_START
            default_end = COMPETITION_END
        else:
            # During competition: Default to competition start through today
            default_start = COMPETITION_START
            default_end = today
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=st.session_state.get('start_date', default_start),
                min_value=COMPETITION_START - timedelta(days=60),  # Allow some pre-competition data
                max_value=today,
                help="Select the start date for analysis"
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=st.session_state.get('end_date', default_end),
                min_value=COMPETITION_START - timedelta(days=60),
                max_value=today,
                help="Select the end date for analysis"
            )
        
        # Validate date range
        if start_date > end_date:
            st.error("⚠️ Start date must be before end date")
            st.stop()
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Refresh button with custom styling
        if st.button("🔄 REFRESH DATA", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        # NEW: Enhanced competition info in sidebar
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%); 
                    padding: 15px; border-radius: 10px; border: 1px solid #00d4ff30; margin-top: 20px;'>
            <p style='color: #00d4ff; font-size: 0.9rem; margin: 0;'>COMPETITION STATUS</p>
            <p style='color: #4ade80; font-size: 0.8rem; margin: 5px 0 0 0;'>● {current_week_status}</p>
            <p style='color: #808080; font-size: 0.7rem; margin: 5px 0 0 0;'>
                Week {min(current_week_num, COMPETITION_WEEKS)} of {COMPETITION_WEEKS}
            </p>
            <p style='color: #808080; font-size: 0.7rem; margin: 5px 0 0 0;'>Real-time sync enabled</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Fetch data with date range
    with st.spinner("🔄 Loading performance data..."):
        athletes_df = fetch_athletes(supabase)
        
        # Convert dates to ISO format strings for API calls
        start_date_str = datetime.combine(start_date, datetime.min.time()).isoformat()
        end_date_str = datetime.combine(end_date, datetime.max.time()).isoformat()
        
        activities_df = fetch_activities_by_date_range(supabase, start_date_str, end_date_str)
        hr_zones_df = fetch_heart_rate_zones_by_date(supabase, start_date_str, end_date_str)
    
    # Display date range info
    date_range_days = (end_date - start_date).days + 1
    st.markdown(f"""
    <div style='text-align: center; margin: -10px 0 20px 0;'>
        <p style='color: #808080; font-size: 0.9rem;'>
            Analyzing data from <span style='color: #00d4ff; font-weight: 600;'>
            {start_date.strftime('%B %d, %Y')}</span> to 
            <span style='color: #00d4ff; font-weight: 600;'>{end_date.strftime('%B %d, %Y')}</span>
            ({date_range_days} days)
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # NEW: WEEKLY PERFORMANCE SECTION - Add this before the epic leaderboard
    if not hr_zones_df.empty and not activities_df.empty:
        st.markdown("""
        <div class="weekly-performance-section">
            <div class="weekly-performance-title">📊 WEEKLY COMPETITION PERFORMANCE</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Calculate weekly performance
        weekly_performance_df = calculate_weekly_athlete_performance(hr_zones_df, activities_df)
        
        if not weekly_performance_df.empty:
            # Week selector
            available_weeks = sorted(weekly_performance_df['Week_Number'].unique())
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                selected_week = st.selectbox(
                    "🗓️ Select Competition Week to View",
                    options=["All Weeks"] + [f"Week {w}" for w in available_weeks],
                    index=0,
                    help="Choose a specific week to see detailed performance breakdown"
                )
            
            if selected_week == "All Weeks":
                # Show summary table for all weeks
                st.markdown("### 🏆 Complete Competition Summary")
                
                # Calculate totals
                total_points = weekly_performance_df.groupby('Athlete')['Points'].sum().sort_values(ascending=False)
                total_miles = weekly_performance_df.groupby('Athlete')['Cycling_Miles'].sum()
                total_activities = weekly_performance_df.groupby('Athlete')['Activities'].sum()
                
                # Create summary dataframe
                summary_df = pd.DataFrame({
                    'Total Points': total_points,
                    'Total Cycling Miles': total_miles.round(1),
                    'Total Activities': total_activities,
                    'Avg Points/Week': (total_points / len(available_weeks)).round(1)
                })
                
                # Sort by Total Points (highest to lowest)
                summary_df = summary_df.sort_values('Total Points', ascending=False)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### 🥇 Overall Competition Standings")
                    st.dataframe(summary_df, use_container_width=True, height=300)
                
                with col2:
                    # Weekly points chart
                    fig = px.line(
                        weekly_performance_df,
                        x='Week_Number',
                        y='Points',
                        color='Athlete',
                        title='Weekly Points Progression',
                        markers=True,
                        line_shape='linear'
                    )
                    
                    fig.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white'),
                        height=300,
                        xaxis=dict(
                            title='Competition Week',
                            gridcolor='rgba(128,128,128,0.2)',
                            tickmode='linear',
                            tick0=1,
                            dtick=1
                        ),
                        yaxis=dict(title='Points Earned', gridcolor='rgba(128,128,128,0.2)'),
                        legend=dict(font=dict(color='white'))
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
            else:
                # Show specific week details
                week_num = int(selected_week.split()[1])
                week_data = weekly_performance_df[weekly_performance_df['Week_Number'] == week_num]
                
                if not week_data.empty:
                    date_range = week_data.iloc[0]['Date_Range']
                    st.markdown(f"### 🗓️ {selected_week} Performance ({date_range})")
                    
                    # Week statistics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        total_week_points = week_data['Points'].sum()
                        st.metric("📊 Total Points", f"{total_week_points:,}")
                    
                    with col2:
                        total_week_miles = week_data['Cycling_Miles'].sum()
                        st.metric("🚴 Total Miles", f"{total_week_miles:.1f}")
                    
                    with col3:
                        total_week_activities = week_data['Activities'].sum()
                        st.metric("🏃 Total Activities", f"{total_week_activities}")
                    
                    with col4:
                        participating_athletes = len(week_data)
                        st.metric("👥 Active Athletes", f"{participating_athletes}")
                    
                    # Week leaderboard
                    week_leaderboard = week_data.sort_values('Points', ascending=False).reset_index(drop=True)
                    week_leaderboard.index += 1  # Start ranking from 1
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 🏆 Week Rankings")
                        display_week_data = week_leaderboard[['Athlete', 'Points', 'Cycling_Miles', 'Activities']].copy()
                        display_week_data.columns = ['Athlete', 'Points', 'Cycling Miles', 'Activities']
                        st.dataframe(display_week_data, use_container_width=True, height=300)
                    
                    with col2:
                        # Week points chart
                        fig = px.bar(
                            week_leaderboard,
                            x='Athlete',
                            y='Points',
                            title=f'{selected_week} Points Distribution',
                            color='Points',
                            color_continuous_scale=['#4ade80', '#00d4ff', '#fbbf24', '#fb923c', '#f87171']
                        )
                        
                        fig.update_layout(
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='white'),
                            height=300,
                            showlegend=False,
                            coloraxis_showscale=False,
                            xaxis=dict(tickangle=-45)
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📊 No weekly performance data available for the selected date range.")

    # EPIC LEADERBOARD SECTION - YOUR ORIGINAL EPIC LEADERBOARD
    # Epic leaderboard styling and content
    st.markdown("""
    <style>
        /* Epic Leaderboard Styling - Completely Isolated */
        .epic-leaderboard {
            text-align: left !important;
            background: radial-gradient(ellipse at top, rgba(0, 212, 255, 0.1) 0%, rgba(0, 0, 0, 0.8) 70%);
            padding: 30px;
            border-radius: 20px;
            border: 2px solid rgba(0, 212, 255, 0.3);
            margin: 20px 0;
            box-shadow: 0 20px 60px rgba(0, 212, 255, 0.2);
            position: relative;
            overflow: hidden;
        }
        
        .epic-leaderboard::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: conic-gradient(from 0deg, transparent, rgba(0, 212, 255, 0.1), transparent, rgba(0, 212, 255, 0.1));
            animation: rotate 20s linear infinite;
            z-index: -1;
        }
        
        @keyframes rotate {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* Leaderboard title with epic styling */
        .epic-title {
            text-align: center !important;
            font-size: 3rem !important;
            font-weight: 900 !important;
            background: linear-gradient(135deg, #ffd700 0%, #ff8c00 30%, #00d4ff 70%, #ffffff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 50px rgba(255, 215, 0, 0.5);
            margin-bottom: 10px !important;
            text-transform: uppercase;
            letter-spacing: 3px;
            position: relative;
        }
        
        .epic-subtitle {
            text-align: center !important;
            color: rgba(255, 255, 255, 0.8);
            font-size: 1.2rem;
            margin-bottom: 40px !important;
            font-style: italic;
            letter-spacing: 1px;
        }
        
        /* Podium Container */
        .podium-container {
            display: flex;
            justify-content: center;
            align-items: end;
            gap: 20px;
            margin: 40px 0 60px 0;
            perspective: 1000px;
        }
        
        /* Podium positions */
        .podium-position {
            display: flex;
            flex-direction: column;
            align-items: center;
            transition: all 0.5s ease;
            cursor: pointer;
        }
        
        .podium-position:hover {
            transform: translateY(-10px) scale(1.05);
        }
        
        /* Podium bases with different heights */
        .podium-base {
            width: 120px;
            background: linear-gradient(135deg, #2a2a2a 0%, #1a1a1a 100%);
            border-radius: 10px 10px 0 0;
            border: 2px solid rgba(0, 212, 255, 0.3);
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-end;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }
        
        .first-place { height: 180px; border-color: #ffd700; }
        .second-place { height: 140px; border-color: #c0c0c0; }
        .third-place { height: 100px; border-color: #cd7f32; }
        
        /* Crown for winner */
        .crown {
            position: absolute;
            top: -40px;
            font-size: 3rem;
            animation: bounce 2s infinite;
            filter: drop-shadow(0 0 20px rgba(255, 215, 0, 0.8));
        }
        
        @keyframes bounce {
            0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-10px); }
            60% { transform: translateY(-5px); }
        }
        
        /* Athlete cards on podium */
        .podium-athlete {
            background: linear-gradient(135deg, rgba(0, 212, 255, 0.2) 0%, rgba(0, 0, 0, 0.4) 100%);
            padding: 15px;
            border-radius: 15px;
            text-align: center;
            margin-bottom: 15px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            width: 100px;
        }
        
        .athlete-name-podium {
            color: white;
            font-weight: 700;
            font-size: 0.9rem;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .athlete-points-podium {
            background: linear-gradient(135deg, #00d4ff 0%, #ffffff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 1.1rem;
            font-weight: 800;
            margin-bottom: 5px;
        }
        
        .athlete-activities-podium {
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.75rem;
        }
        
        /* Ranking position numbers */
        .position-number {
            color: white;
            font-size: 2rem;
            font-weight: 900;
            text-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
            margin: 10px 0;
        }
        
        /* Full rankings section */
        .full-rankings {
            background: linear-gradient(135deg, rgba(0, 0, 0, 0.6) 0%, rgba(30, 30, 30, 0.8) 100%);
            border-radius: 20px;
            padding: 30px;
            margin-top: 40px;
            border: 1px solid rgba(0, 212, 255, 0.3);
            backdrop-filter: blur(10px);
        }
        
        .rankings-title {
            color: #00d4ff;
            font-size: 2rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 30px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        
        /* Enhanced ranking cards */
        .epic-ranking-card {
            background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(30, 30, 30, 0.9) 100%);
            border: 1px solid rgba(0, 212, 255, 0.3);
            border-radius: 15px;
            padding: 20px;
            margin: 15px 0;
            display: flex;
            align-items: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .epic-ranking-card::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            width: 5px;
            background: linear-gradient(180deg, #ffd700 0%, #00d4ff 50%, #ff6b6b 100%);
            transform: scaleY(0);
            transition: all 0.3s ease;
        }
        
        .epic-ranking-card:hover {
            transform: translateX(10px);
            box-shadow: 0 15px 40px rgba(0, 212, 255, 0.3);
            border-color: rgba(0, 212, 255, 0.8);
        }
        
        .epic-ranking-card:hover::before {
            transform: scaleY(1);
        }
        
        .rank-position {
            font-size: 2rem;
            font-weight: 900;
            color: #00d4ff;
            min-width: 60px;
            text-align: center;
            text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
        }
        
        .athlete-details {
            flex-grow: 1;
            margin-left: 20px;
        }
        
        .athlete-name-full {
            color: white;
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .athlete-stats {
            display: flex;
            gap: 30px;
            align-items: center;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-value {
            color: #00d4ff;
            font-size: 1.4rem;
            font-weight: 700;
            display: block;
        }
        
        .stat-label {
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
               
        /* Competition stats */
        .competition-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        
        .stat-card {
            background: linear-gradient(135deg, rgba(255, 215, 0, 0.1) 0%, rgba(0, 212, 255, 0.1) 100%);
            border: 1px solid rgba(0, 212, 255, 0.3);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0, 212, 255, 0.2);
        }
        
        .stat-card-value {
            font-size: 2.5rem;
            font-weight: 900;
            background: linear-gradient(135deg, #ffd700 0%, #00d4ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .stat-card-label {
            color: rgba(255, 255, 255, 0.8);
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Epic leaderboard container
    st.markdown('<div class="epic-leaderboard">', unsafe_allow_html=True)
    
    # Epic title
    st.markdown("""
    <div class="epic-title">GRAN FONDO STRAVA CHAMPIONSHIP 🏆</div>
    <div class="epic-subtitle">Battle for Cycling Supremacy</div>
    """, unsafe_allow_html=True)
    
    if not hr_zones_df.empty:
        points_df = calculate_hr_zone_points(hr_zones_df)
        
        # Calculate activity streaks for all athletes
        athlete_streaks = calculate_athlete_streaks(activities_df)
        
        
        if not points_df.empty and len(points_df) >= 3:
            # Get top 3 for podium
            top_3 = points_df.head(3)
            
            # Competition stats
            total_points = points_df['zone_points'].sum()
            total_activities = points_df['activity_count'].sum()
            leader_points = points_df.iloc[0]['zone_points']
            
            # Find the longest current streak
            max_streak = max(athlete_streaks.values()) if athlete_streaks else 0
            active_streaks = len([s for s in athlete_streaks.values() if s > 0])
            
            st.markdown(f"""
            <div class="competition-stats">
                <div class="stat-card">
                    <div class="stat-card-value">{int(total_points):,}</div>
                    <div class="stat-card-label">Total Points Earned</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-value">{int(total_activities)}</div>
                    <div class="stat-card-label">Activities Completed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-value">{len(points_df)}</div>
                    <div class="stat-card-label">Athletes Competing</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-value">🔥 {max_streak}</div>
                    <div class="stat-card-label">Longest Streak (Days)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-value">{int(leader_points):,}</div>
                    <div class="stat-card-label">Leading Score</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Full rankings
            st.markdown("""
            <div class="full-rankings">
            """, unsafe_allow_html=True)
            
            for idx, (athlete, row) in enumerate(points_df.iterrows(), 1):
                medal_emoji = "👑" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"#{idx}"
                
                # Calculate points behind leader
                leader_points = points_df.iloc[0]['zone_points']
                points_behind = leader_points - row['zone_points']
                
                # Create the behind text
                if idx == 1:
                    behind_text = "LEADER"
                    behind_color = "#ffd700"
                else:
                    behind_text = f"-{int(points_behind):,}"
                    behind_color = "#ff6b6b"
                
                # Get streak for this athlete
                athlete_streak = athlete_streaks.get(athlete, 0)
                streak_badge = get_streak_badge(athlete_streak)
                
                if athlete_streak > 0:
                    if streak_badge["emoji"]:
                        streak_display = f"{streak_badge['emoji']} {athlete_streak} days"
                        streak_title = f"{streak_badge['name']} Badge - {athlete_streak} day streak!"
                    else:
                        streak_display = f"{athlete_streak} days"
                        streak_title = f"{athlete_streak} day streak"
                else:
                    streak_display = "💤 0 days"
                    streak_title = "No current streak"
                
                st.markdown(f"""
                <div class="epic-ranking-card">
                    <div class="rank-position">{medal_emoji}</div>
                    <div class="athlete-details">
                        <div class="athlete-name-full">{athlete}</div>
                        <div class="athlete-stats">
                            <div class="stat-item">
                                <span class="stat-value">{int(row['zone_points']):,}</span>
                                <span class="stat-label">Points</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-value" style="color: {behind_color};">{behind_text}</span>
                                <span class="stat-label">Behind Leader</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-value">{int(row['activity_count'])}</span>
                                <span class="stat-label">Activities</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-value" title="{streak_title}">{streak_display}</span>
                                <span class="stat-label">Current Streak</span>
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)  # Close full rankings
            
            # Scoring system explanation
            with st.expander("🎯 Championship Scoring System", expanded=False):
                st.markdown("""
                <div style='background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%); 
                            padding: 25px; border-radius: 15px; border: 1px solid rgba(0, 212, 255, 0.3);'>
                    <h4 style='color: #ffd700; margin-bottom: 20px; text-align: center; font-size: 1.3rem;'>
                        🏆 How Champions Are Made
                    </h4>
                    <div style='display: grid; gap: 15px;'>
                        <div style='display: flex; align-items: center; padding: 10px; border-radius: 8px; 
                                    background: rgba(74, 222, 128, 0.1); border-left: 4px solid #4ade80;'>
                            <span style='color: #4ade80; font-size: 1.5rem; margin-right: 15px;'>💚</span>
                            <div>
                                <span style='color: #4ade80; font-weight: 700;'>Recovery Zone:</span>
                                <span style='color: white; margin-left: 10px;'>1 point per minute</span>
                            </div>
                        </div>
                        <div style='display: flex; align-items: center; padding: 10px; border-radius: 8px; 
                                    background: rgba(34, 211, 238, 0.1); border-left: 4px solid #22d3ee;'>
                            <span style='color: #22d3ee; font-size: 1.5rem; margin-right: 15px;'>💙</span>
                            <div>
                                <span style='color: #22d3ee; font-weight: 700;'>Endurance Zone:</span>
                                <span style='color: white; margin-left: 10px;'>2 points per minute</span>
                            </div>
                        </div>
                        <div style='display: flex; align-items: center; padding: 10px; border-radius: 8px; 
                                    background: rgba(251, 191, 36, 0.1); border-left: 4px solid #fbbf24;'>
                            <span style='color: #fbbf24; font-size: 1.5rem; margin-right: 15px;'>💛</span>
                            <div>
                                <span style='color: #fbbf24; font-weight: 700;'>Tempo Zone:</span>
                                <span style='color: white; margin-left: 10px;'>3 points per minute</span>
                            </div>
                        </div>
                        <div style='display: flex; align-items: center; padding: 10px; border-radius: 8px; 
                                    background: rgba(251, 146, 60, 0.1); border-left: 4px solid #fb923c;'>
                            <span style='color: #fb923c; font-size: 1.5rem; margin-right: 15px;'>🧡</span>
                            <div>
                                <span style='color: #fb923c; font-weight: 700;'>Threshold Zone:</span>
                                <span style='color: white; margin-left: 10px;'>4 points per minute</span>
                            </div>
                        </div>
                        <div style='display: flex; align-items: center; padding: 10px; border-radius: 8px; 
                                    background: rgba(248, 113, 113, 0.1); border-left: 4px solid #f87171;'>
                            <span style='color: #f87171; font-size: 1.5rem; margin-right: 15px;'>❤️</span>
                            <div>
                                <span style='color: #f87171; font-weight: 700;'>VO2 Max Zone:</span>
                                <span style='color: white; margin-left: 10px;'>5 points per minute</span>
                            </div>
                        </div>
                    </div>
                    <div style='text-align: center; margin-top: 20px; padding: 15px; 
                                background: rgba(0, 212, 255, 0.1); border-radius: 10px;'>
                        <span style='color: #00d4ff; font-weight: 600; font-size: 1.1rem;'>
                            🎯 Strategy: Higher intensity zones = more points!
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Streak badges explanation
            with st.expander("🔥 Activity Streak Badges", expanded=False):
                st.markdown("""
                <div style='background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%); 
                            padding: 25px; border-radius: 15px; border: 1px solid rgba(255, 165, 0, 0.3);'>
                    <h4 style='color: #ffa500; margin-bottom: 20px; text-align: center; font-size: 1.3rem;'>
                        🏅 Consistency Rewards
                    </h4>
                    <div style='display: grid; gap: 15px;'>
                        <div style='display: flex; align-items: center; padding: 10px; border-radius: 8px; 
                                    background: rgba(50, 205, 50, 0.1); border-left: 4px solid #32cd32;'>
                            <span style='color: #32cd32; font-size: 1.5rem; margin-right: 15px;'>⭐</span>
                            <div>
                                <span style='color: #32cd32; font-weight: 700;'>Star Badge:</span>
                                <span style='color: white; margin-left: 10px;'>3+ consecutive days</span>
                            </div>
                        </div>
                        <div style='display: flex; align-items: center; padding: 10px; border-radius: 8px; 
                                    background: rgba(30, 144, 255, 0.1); border-left: 4px solid #1e90ff;'>
                            <span style='color: #1e90ff; font-size: 1.5rem; margin-right: 15px;'>⚡</span>
                            <div>
                                <span style='color: #1e90ff; font-weight: 700;'>Lightning Badge:</span>
                                <span style='color: white; margin-left: 10px;'>7+ consecutive days</span>
                            </div>
                        </div>
                        <div style='display: flex; align-items: center; padding: 10px; border-radius: 8px; 
                                    background: rgba(255, 69, 0, 0.1); border-left: 4px solid #ff4500;'>
                            <span style='color: #ff4500; font-size: 1.5rem; margin-right: 15px;'>🔥</span>
                            <div>
                                <span style='color: #ff4500; font-weight: 700;'>Fire Badge:</span>
                                <span style='color: white; margin-left: 10px;'>14+ consecutive days</span>
                            </div>
                        </div>
                        <div style='display: flex; align-items: center; padding: 10px; border-radius: 8px; 
                                    background: rgba(255, 215, 0, 0.1); border-left: 4px solid #ffd700;'>
                            <span style='color: #ffd700; font-size: 1.5rem; margin-right: 15px;'>🏆</span>
                            <div>
                                <span style='color: #ffd700; font-weight: 700;'>Legend Badge:</span>
                                <span style='color: white; margin-left: 10px;'>30+ consecutive days</span>
                            </div>
                        </div>
                    </div>
                    <div style='text-align: center; margin-top: 20px; padding: 15px; 
                                background: rgba(255, 165, 0, 0.1); border-radius: 10px;'>
                        <span style='color: #ffa500; font-weight: 600; font-size: 1.1rem;'>
                            🎯 Keep the momentum! Activity streaks encourage daily consistency
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
        
        elif not points_df.empty:
            st.markdown("""
            <div style='text-align: center; padding: 50px; color: rgba(255, 255, 255, 0.7);'>
                <h3>🚴‍♂️ Championship in Progress</h3>
                <p>Need at least 3 athletes to display the full podium ceremony!</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='text-align: center; padding: 80px; color: rgba(255, 255, 255, 0.7);'>
            <h2>🏁 Championship Awaits</h2>
            <p style='font-size: 1.2rem; margin-top: 20px;'>
                No heart rate data available for the selected period.<br>
                Get out there and start training!
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Close epic leaderboard container
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ATHLETE-SPECIFIC CYCLING KPIs SECTION (YOUR ORIGINAL CODE)
    if not activities_df.empty:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%); 
                    padding: 25px; border-radius: 15px; border: 1px solid #00d4ff30; margin-bottom: 30px;'>
            <h2 style='color: #00d4ff; text-align: center; margin-bottom: 25px;'>
                🚴 WEEKLY ATHLETE PERFORMANCE METRICS
            </h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Calculate athlete-specific stats
        athlete_stats = calculate_athlete_cycling_stats(activities_df, hr_zones_df)
        
        if athlete_stats:
            # Get current competition week display info
            monday, sunday = get_current_competition_week_dates()
            week_display = f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d')}"
            
            # Create columns for each athlete (up to 3 athletes per row)
            athletes_list = list(athlete_stats.keys())
            num_athletes = len(athletes_list)
            
            # Display athletes in rows of 3
            for row_start in range(0, num_athletes, 3):
                cols = st.columns(3)
                for col_idx in range(3):
                    athlete_idx = row_start + col_idx
                    if athlete_idx < num_athletes:
                        athlete = athletes_list[athlete_idx]
                        stats = athlete_stats[athlete]
                        
                        with cols[col_idx]:
                            # Create centered athlete card with name
                            st.markdown(f"""
                            <div class="athlete-card">
                                <div class="athlete-name">{athlete}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Create centered metrics container
                            col_container = st.container()
                            with col_container:
                                # Use Streamlit metrics for KPIs with enhanced styling
                                st.metric(
                                    label="⚡ Weekly HR Zone Points",
                                    value=f"{int(stats['weekly_zone_points']):,}",
                                    delta=week_display,
                                    delta_color="off"
                                )
                                
                                st.metric(
                                    label="🚴 Weekly Cycling Miles",
                                    value=f"{stats['weekly_cycling_miles']:.1f} mi",
                                    delta="This Week",
                                    delta_color="off"
                                )
                                
                                st.metric(
                                    label="🏆 Total Cycling Miles",
                                    value=f"{stats['total_cycling_miles']:.1f} mi",
                                    delta="Selected Period",
                                    delta_color="off"
                                )
            
            # Add a summary row with totals
            total_weekly_points = sum(s['weekly_zone_points'] for s in athlete_stats.values())
            total_weekly_miles = sum(s['weekly_cycling_miles'] for s in athlete_stats.values())
            total_cycling_miles = sum(s['total_cycling_miles'] for s in athlete_stats.values())
            
            # Team totals section with enhanced styling
            st.markdown("""
            <div style='background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(0, 153, 204, 0.1) 100%);
                        border-radius: 20px; padding: 30px; margin: 40px 0 20px 0;
                        border: 2px solid rgba(0, 212, 255, 0.3);
                        box-shadow: 0 10px 40px rgba(0, 212, 255, 0.2);'>
                <div class="team-totals-header">🏅 BOURBON CHASERS TEAM TOTALS 🏅</div>
            </div>
            """, unsafe_allow_html=True)
            
            total_cols = st.columns(3)
            with total_cols[0]:
                st.metric(
                    label="💪 Team Weekly Zone Points",
                    value=f"{int(total_weekly_points):,}",
                    delta=f"Combined {week_display}",
                    delta_color="off"
                )
            with total_cols[1]:
                st.metric(
                    label="🚴‍♂️ Team Weekly Cycling Miles",
                    value=f"{total_weekly_miles:.1f} mi",
                    delta="Combined This Week",
                    delta_color="off"
                )
            with total_cols[2]:
                st.metric(
                    label="🎯 Team Total Cycling Miles",
                    value=f"{total_cycling_miles:.1f} mi",
                    delta="Combined Selected Period",
                    delta_color="off"
                )

    # GLOBAL ATHLETE FILTER SECTION (YOUR ORIGINAL CODE)
    st.markdown("""
    <div class="global-filter">
        <div class="filter-title">🎯 ATHLETE ANALYSIS FILTER</div>
        <p style='text-align: center; color: rgba(255, 255, 255, 0.8); margin-bottom: 20px; font-size: 1.1rem;'>
            Select an athlete to filter both the Activities Chart and Performance Stats below
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get unique athletes for filter
    if not activities_df.empty:
        athlete_names = sorted(activities_df['athlete_name'].unique())
        
        # Center the selectbox
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            selected_athlete = st.selectbox(
                "👤 Choose Athlete for Detailed Analysis",
                ["All Team Members"] + list(athlete_names),
                key="global_athlete_filter",
                help="This filter will apply to both tabs below - Activities Chart and Performance Stats"
            )
        
        # Filter data based on selection
        if selected_athlete != "All Team Members":
            filtered_activities = activities_df[activities_df['athlete_name'] == selected_athlete]
            if not hr_zones_df.empty and 'athlete_name' in hr_zones_df.columns:
                filtered_hr_zones = hr_zones_df[hr_zones_df['athlete_name'] == selected_athlete]
            else:
                filtered_hr_zones = pd.DataFrame()
        else:
            filtered_activities = activities_df
            filtered_hr_zones = hr_zones_df if not hr_zones_df.empty else pd.DataFrame()
        
        # Display current filter status
        if selected_athlete != "All Team Members":
            st.markdown(f"""
            <div class="athlete-banner">
                <div class="athlete-name-banner">🏆 Viewing: {selected_athlete}</div>
                <p style='color: rgba(255, 255, 255, 0.8); margin: 10px 0 0 0; font-size: 1rem;'>
                    Individual Performance Analysis
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="athlete-banner">
                <div class="athlete-name-banner">🏆 Viewing: All Team Members</div>
                <p style='color: rgba(255, 255, 255, 0.8); margin: 10px 0 0 0; font-size: 1rem;'>
                    Complete Team Performance Overview
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        # Create tabs with enhanced styling
        tab1, tab2 = st.tabs([
            "📊 ACTIVITIES CHART", 
            "📈 PERFORMANCE STATS"
        ])
        
        # Tab 1: Activities Chart (YOUR ORIGINAL CODE)
        with tab1:
            st.markdown('<div class="tab-content">', unsafe_allow_html=True)
            
            if selected_athlete != "All Team Members":
                st.markdown(f'<div class="tab-title">📊 {selected_athlete}\'s Activities</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="tab-title">📊 Team Activities Overview</div>', unsafe_allow_html=True)
            
            if not filtered_activities.empty:
                # Quick stats for the filtered data
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_activities = len(filtered_activities)
                    st.metric("📊 Activities", total_activities)
                
                with col2:
                    total_distance_miles = filtered_activities['distance'].sum() / 1609.344
                    st.metric("🛣️ Total Distance", f"{total_distance_miles:.1f} mi")
                
                with col3:
                    total_time_hours = filtered_activities['moving_time'].sum() / 3600
                    st.metric("⏱️ Total Time", f"{total_time_hours:.1f} hrs")
                
                with col4:
                    if selected_athlete != "All Team Members":
                        avg_hr = filtered_activities['average_heartrate'].mean()
                        st.metric("❤️ Avg HR", f"{avg_hr:.0f} bpm" if not pd.isna(avg_hr) else "N/A")
                    else:
                        unique_athletes = filtered_activities['athlete_name'].nunique()
                        st.metric("👥 Athletes", unique_athletes)
                
                # Format the dataframe for display
                display_df = filtered_activities[['start_date', 'athlete_name', 'name', 'sport_type', 
                                               'distance', 'moving_time', 'average_heartrate', 
                                               'average_speed', 'total_elevation_gain']].copy()
                
                # Format columns
                display_df['start_date'] = pd.to_datetime(display_df['start_date']).dt.strftime('%Y-%m-%d %H:%M')
                display_df['distance'] = display_df['distance'].apply(format_distance)
                display_df['moving_time'] = display_df['moving_time'].apply(format_duration)
                display_df['average_speed'] = display_df['average_speed'].apply(
                    lambda x: f"{mps_to_mph(x):.1f} mph" if x and not pd.isna(x) else "N/A"
                )
                display_df['total_elevation_gain'] = display_df['total_elevation_gain'].apply(
                    lambda x: f"{x * 3.28084:.0f} ft" if x and not pd.isna(x) else "N/A"
                )
                display_df['average_heartrate'] = display_df['average_heartrate'].apply(
                    lambda x: f"{x:.0f} bpm" if x and not pd.isna(x) else "N/A"
                )
                
                # Add sport type emoji
                sport_emojis = {
                    'Ride': '🚴',
                    'VirtualRide': '🚴💻',
                    'Peloton': '🚴',
                    'Bike': '🚴‍♂️',
                    'Run': '🏃',
                    'Treadmill': '🏃',
                    'Walk': '🚶',
                    'Hike': '🥾',
                    'Swim': '🏊',
                    'Workout': '💪',
                    'WeightTraining': '🏋️'
                }
                
                display_df['sport_type'] = display_df['sport_type'].apply(
                    lambda x: f"{sport_emojis.get(x, '🏃')} {x}" if x else "N/A"
                )
                
                # Rename columns for display
                display_df.columns = ['Date', 'Athlete', 'Activity', 'Type', 'Distance', 
                                     'Duration', 'Avg HR', 'Avg Speed', 'Elevation']
                
                # Hide athlete column if viewing single athlete
                if selected_athlete != "All Team Members":
                    display_df = display_df.drop('Athlete', axis=1)
                
                # Display with custom styling
                st.dataframe(
                    display_df, 
                    use_container_width=True, 
                    hide_index=True,
                    height=400,
                    column_config={
                        "Date": st.column_config.TextColumn("Date", width="medium"),
                        "Activity": st.column_config.TextColumn("Activity", width="large"),
                    }
                )
                
                # Activity timeline chart
                if 'start_date' in filtered_activities.columns:
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    timeline_df = filtered_activities.copy()
                    timeline_df['date'] = pd.to_datetime(timeline_df['start_date']).dt.date
                    
                    if selected_athlete != "All Team Members":
                        # For individual athlete, show activity types over time
                        daily_activities = timeline_df.groupby(['date', 'sport_type']).size().reset_index(name='count')
                        
                        fig = px.bar(
                            daily_activities, 
                            x='date', 
                            y='count', 
                            color='sport_type',
                            title=f"{selected_athlete}'s Daily Activities by Type",
                            labels={'count': 'Number of Activities', 'date': 'Date', 'sport_type': 'Activity Type'},
                            color_discrete_sequence=['#00d4ff', '#4ade80', '#fbbf24', '#fb923c', '#f87171']
                        )
                    else:
                        # For all athletes, show by athlete
                        daily_counts = timeline_df.groupby(['date', 'athlete_name']).size().reset_index(name='count')
                        
                        fig = px.bar(
                            daily_counts, 
                            x='date', 
                            y='count', 
                            color='athlete_name',
                            title="Team Daily Activity Distribution",
                            labels={'count': 'Number of Activities', 'date': 'Date', 'athlete_name': 'Athlete'},
                            color_discrete_sequence=['#00d4ff', '#4ade80', '#fbbf24', '#fb923c', '#f87171']
                        )
                    
                    fig.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white'),
                        xaxis=dict(gridcolor='rgba(128,128,128,0.2)', title_font=dict(color='white')),
                        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', title_font=dict(color='white')),
                        legend=dict(font=dict(color='white')),
                        height=400,
                        margin=dict(l=40, r=40, t=60, b=40)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
            
            else:
                st.markdown("""
                <div style='text-align: center; padding: 80px; color: rgba(255, 255, 255, 0.7);'>
                    <h3>🚴 No Activities Found</h3>
                    <p style='font-size: 1.2rem; margin-top: 20px;'>
                        No activities available for the selected athlete and date range.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Tab 2: Performance Stats (YOUR ORIGINAL CODE)
        with tab2:
            st.markdown('<div class="tab-content">', unsafe_allow_html=True)
            
            if selected_athlete != "All Team Members":
                st.markdown(f'<div class="tab-title">📈 {selected_athlete}\'s Performance Stats</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="tab-title">📈 Team Performance Stats</div>', unsafe_allow_html=True)
            
            if not filtered_activities.empty:
                # Enhanced metric cards with cycling theme
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if selected_athlete != "All Team Members":
                        activities_count = len(filtered_activities)
                        st.metric("📊 Total Activities", activities_count)
                    else:
                        unique_athletes = filtered_activities['athlete_name'].nunique()
                        st.metric("👥 Total Athletes", unique_athletes)
                    
                    cycling_activities = filtered_activities[
                        filtered_activities['sport_type'].isin(['Ride', 'VirtualRide', 'Peloton', 'Bike'])
                    ]
                    st.metric("🚴 Cycling Activities", len(cycling_activities))
                
                with col2:
                    total_distance_miles = filtered_activities['distance'].sum() / 1609.344
                    st.metric("🛣️ Total Distance", f"{total_distance_miles:.1f} mi")
                    
                    cycling_distance_miles = cycling_activities['distance'].sum() / 1609.344 if not cycling_activities.empty else 0
                    st.metric("🚴 Cycling Distance", f"{cycling_distance_miles:.1f} mi")
                
                with col3:
                    total_time = filtered_activities['moving_time'].sum() / 3600
                    st.metric("⏱️ Total Time", f"{total_time:.1f} hours")
                    
                    cycling_time = cycling_activities['moving_time'].sum() / 3600 if not cycling_activities.empty else 0
                    st.metric("🚴 Cycling Time", f"{cycling_time:.1f} hours")
                
                with col4:
                    avg_hr = filtered_activities['average_heartrate'].mean()
                    st.metric("❤️ Avg Heart Rate", f"{avg_hr:.0f} bpm" if not pd.isna(avg_hr) else "N/A")
                    
                    max_hr = filtered_activities['max_heartrate'].max()
                    st.metric("💥 Max Heart Rate", f"{max_hr:.0f} bpm" if not pd.isna(max_hr) else "N/A")
                
                # Performance insights section
                st.markdown("<br>", unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("""
                    <div class="summary-card">
                        <h4 style='color: #00d4ff; text-align: center; margin-bottom: 20px;'>
                            🎯 ACTIVITY BREAKDOWN
                        </h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Activity type breakdown
                    sport_counts = filtered_activities['sport_type'].value_counts()
                    
                    fig = px.bar(
                        x=sport_counts.values,
                        y=sport_counts.index,
                        orientation='h',
                        color=sport_counts.values,
                        color_continuous_scale=['#4ade80', '#00d4ff', '#fbbf24', '#fb923c', '#f87171'],
                        labels={'x': 'Number of Activities', 'y': 'Activity Type'}
                    )
                    
                    fig.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white'),
                        showlegend=False,
                        height=300,
                        margin=dict(l=20, r=20, t=20, b=20),
                        coloraxis_showscale=False
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.markdown("""
                    <div class="summary-card">
                        <h4 style='color: #00d4ff; text-align: center; margin-bottom: 20px;'>
                            💪 TRAINING INTENSITY
                        </h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Heart rate zone summary if available
                    if not filtered_hr_zones.empty:
                        # Use correct column names (seconds or time) and convert to hours
                        zone_totals = {}
                        zone_names = ['Recovery', 'Endurance', 'Tempo', 'Threshold', 'VO2 Max']
                        for i, zone_name in enumerate(zone_names, 1):
                            if f'zone_{i}_seconds' in filtered_hr_zones.columns:
                                zone_totals[zone_name] = filtered_hr_zones[f'zone_{i}_seconds'].sum() / 3600
                            elif f'zone_{i}_time' in filtered_hr_zones.columns:
                                zone_totals[zone_name] = filtered_hr_zones[f'zone_{i}_time'].sum() / 3600
                            else:
                                zone_totals[zone_name] = 0
                        
                        zone_totals = {k: v for k, v in zone_totals.items() if v > 0}
                        
                        if zone_totals:
                            fig = px.pie(
                                values=list(zone_totals.values()),
                                names=list(zone_totals.keys()),
                                color_discrete_sequence=['#4ade80', '#22d3ee', '#fbbf24', '#fb923c', '#f87171'],
                                hole=0.5
                            )
                            
                            fig.update_traces(
                                textposition='inside',
                                textinfo='percent',
                                hovertemplate='<b>%{label}</b><br>%{value:.1f} hours<br>%{percent}<extra></extra>'
                            )
                            
                            fig.update_layout(
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)',
                                font=dict(color='white'),
                                showlegend=True,
                                legend=dict(font=dict(size=10)),
                                height=300,
                                margin=dict(l=20, r=20, t=20, b=20)
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.markdown("""
                            <div style='text-align: center; padding: 50px; color: rgba(255, 255, 255, 0.5);'>
                                <p>No HR zone data<br>for this selection</p>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style='text-align: center; padding: 50px; color: rgba(255, 255, 255, 0.5);'>
                            <p>💓 No heart rate<br>zone data available</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Performance summary table
                if selected_athlete != "All Team Members":
                    st.markdown(f"""
                    <div class="summary-card" style='margin-top: 30px;'>
                        <h4 style='color: #00d4ff; text-align: center; margin-bottom: 20px;'>
                            🏆 {selected_athlete}'s Activity Summary
                        </h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Create summary by sport type
                    sport_summary = filtered_activities.groupby('sport_type').agg({
                        'distance': lambda x: x.sum() / 1609.344,  # Convert to miles
                        'moving_time': lambda x: x.sum() / 3600,   # Convert to hours
                        'average_heartrate': 'mean',
                        'average_speed': lambda x: x.mean() * 2.237,  # Convert to mph
                        'total_elevation_gain': lambda x: x.sum() * 3.28084,  # Convert to feet
                        'name': 'count'  # Count of activities
                    }).round(2)
                    
                    sport_summary.columns = ['Total Miles', 'Total Hours', 'Avg HR (bpm)', 
                                           'Avg Speed (mph)', 'Total Elevation (ft)', 'Activities']
                    
                    # Format the summary for display
                    sport_summary['Total Miles'] = sport_summary['Total Miles'].apply(lambda x: f"{x:.1f}")
                    sport_summary['Total Hours'] = sport_summary['Total Hours'].apply(lambda x: f"{x:.1f}")
                    sport_summary['Avg HR (bpm)'] = sport_summary['Avg HR (bpm)'].apply(lambda x: f"{x:.0f}" if not pd.isna(x) else "N/A")
                    sport_summary['Avg Speed (mph)'] = sport_summary['Avg Speed (mph)'].apply(lambda x: f"{x:.1f}" if not pd.isna(x) else "N/A")
                    sport_summary['Total Elevation (ft)'] = sport_summary['Total Elevation (ft)'].apply(lambda x: f"{x:.0f}" if not pd.isna(x) else "N/A")
                    
                    st.dataframe(sport_summary, use_container_width=True)
                
                else:
                    # Team comparison
                    st.markdown("""
                    <div class="summary-card" style='margin-top: 30px;'>
                        <h4 style='color: #00d4ff; text-align: center; margin-bottom: 20px;'>
                            🏆 Team Performance Comparison
                        </h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Create team comparison
                    team_summary = filtered_activities.groupby('athlete_name').agg({
                        'distance': lambda x: x.sum() / 1609.344,  # Convert to miles
                        'moving_time': lambda x: x.sum() / 3600,   # Convert to hours
                        'average_heartrate': 'mean',
                        'name': 'count'  # Count of activities
                    }).round(2)
                    
                    team_summary.columns = ['Total Miles', 'Total Hours', 'Avg HR (bpm)', 'Activities']
                    
                    # Format the summary
                    team_summary['Total Miles'] = team_summary['Total Miles'].apply(lambda x: f"{x:.1f}")
                    team_summary['Total Hours'] = team_summary['Total Hours'].apply(lambda x: f"{x:.1f}")
                    team_summary['Avg HR (bpm)'] = team_summary['Avg HR (bpm)'].apply(lambda x: f"{x:.0f}" if not pd.isna(x) else "N/A")
                    
                    # Sort by total miles descending
                    team_summary = team_summary.sort_values('Total Miles', ascending=False, key=lambda x: pd.to_numeric(x, errors='coerce'))
                    
                    st.dataframe(team_summary, use_container_width=True)
            
            else:
                st.markdown("""
                <div style='text-align: center; padding: 80px; color: rgba(255, 255, 255, 0.7);'>
                    <h3>📈 No Performance Data</h3>
                    <p style='font-size: 1.2rem; margin-top: 20px;'>
                        No performance data available for the selected athlete and date range.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        st.info("🚴 No activity data available. Please check your date range or data connection.")
    
    # NEW: Competition footer
    st.markdown("""
    <div style='text-align: center; margin-top: 50px; padding: 20px; 
                background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(30, 30, 30, 0.9) 100%);
                border-radius: 15px; border: 1px solid rgba(0, 212, 255, 0.3);'>
        <p style='color: #00d4ff; font-weight: 600; margin: 0;'>
            🚴 May the best cyclist win the Hincapie Gran Fondo Competition! 🏆
        </p>
        <p style='color: #808080; font-size: 0.9rem; margin: 10px 0 0 0;'>
            Competition Period: August 11 - October 5, 2025 • 8 Weeks of Epic Competition
        </p>
    </div>
    """, unsafe_allow_html=True)

# TEMPORARY ADMIN SECTION FOR FIXING EXISTING ACTIVITIES
# Add ?admin=true to the URL to show this section
if st.query_params.get("admin") == "true":
    st.markdown("---")
    st.header("🔧 Admin: Fix Activity Classifications")
    st.warning("⚠️ This is a one-time fix to reclassify existing activities based on elevation data.")
    
    def fix_existing_activities_admin(supabase):
        """
        Fix existing activities in the database by reclassifying 'Peloton' activities
        that have elevation data as 'Bike' activities.
        """
        st.write("🔧 Starting activity classification fix...")
        
        # Fetch all activities that might need fixing
        st.write("📊 Fetching activities from database...")
        response = supabase.table('activities').select("*").execute()
        
        if not response.data:
            st.error("❌ No activities found in database")
            return
        
        df = pd.DataFrame(response.data)
        st.write(f"📋 Found {len(df)} total activities")
        
        # Clean sport_type for analysis (same logic as in app.py)
        def clean_sport_type_admin(value):
            if not isinstance(value, str):
                return value
            
            # Remove various root= formats
            if value.startswith("root='") and value.endswith("'"):
                cleaned = value[6:-1]
            elif value.startswith('root="') and value.endswith('"'):
                cleaned = value[6:-1]
            elif value.startswith('root='):
                cleaned = value[5:]
                if cleaned.startswith("'") and cleaned.endswith("'"):
                    cleaned = cleaned[1:-1]
                elif cleaned.startswith('"') and cleaned.endswith('"'):
                    cleaned = cleaned[1:-1]
            else:
                cleaned = value
            
            # Apply specific replacements
            if cleaned == 'Ride':
                return 'Peloton'  # Will be corrected to 'Bike' if has elevation
            elif cleaned == 'Run':
                return 'Run'
            else:
                return cleaned
        
        df['cleaned_sport_type'] = df['sport_type'].apply(clean_sport_type_admin)
        
        # Show current distribution
        st.write("📈 Current sport_type distribution:")
        st.write(df['cleaned_sport_type'].value_counts())
        
        # Find activities that should be reclassified
        peloton_activities = df[df['cleaned_sport_type'] == 'Peloton'].copy()
        
        if peloton_activities.empty:
            st.success("✅ No Peloton activities found to analyze")
            return
        
        st.write(f"🔍 Found {len(peloton_activities)} activities currently classified as 'Peloton'")
        
        # Check elevation data
        peloton_activities['has_elevation'] = peloton_activities['total_elevation_gain'].fillna(0) > 0
        
        with_elevation = peloton_activities[peloton_activities['has_elevation']]
        without_elevation = peloton_activities[~peloton_activities['has_elevation']]
        
        st.write(f"• {len(with_elevation)} have elevation data (should be 'Bike')")
        st.write(f"• {len(without_elevation)} have no elevation (correctly 'Peloton')")
        
        if with_elevation.empty:
            st.success("✅ No activities need to be reclassified")
            return
        
        # Show some examples
        st.write(f"📋 Sample activities that will be changed from 'Peloton' to 'Bike':")
        for _, row in with_elevation.head(5).iterrows():
            elevation_ft = row['total_elevation_gain'] * 3.28084 if row['total_elevation_gain'] else 0
            st.write(f"• {row['start_date']} - {row['name']} ({elevation_ft:.0f}ft elevation)")
        
        # Add a button to perform the fix
        if st.button(f"🔄 Update {len(with_elevation)} activities from 'Peloton' to 'Bike'"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            updated_count = 0
            failed_count = 0
            
            for i, (_, row) in enumerate(with_elevation.iterrows()):
                try:
                    # Update the sport_type to 'Bike'
                    update_response = supabase.table('activities')\
                        .update({'sport_type': 'Bike'})\
                        .eq('id', row['id'])\
                        .execute()
                    
                    if update_response.data:
                        updated_count += 1
                    else:
                        failed_count += 1
                        st.error(f"❌ Failed to update activity {row['id']}")
                        
                except Exception as e:
                    failed_count += 1
                    st.error(f"❌ Error updating activity {row['id']}: {e}")
                
                # Update progress
                progress = (i + 1) / len(with_elevation)
                progress_bar.progress(progress)
                status_text.text(f"Updating {i + 1}/{len(with_elevation)} activities...")
            
            progress_bar.empty()
            status_text.empty()
            
            st.success(f"🎉 Update complete!")
            st.write(f"✅ Successfully updated: {updated_count}")
            if failed_count > 0:
                st.write(f"❌ Failed updates: {failed_count}")
            
            # Verify the changes
            st.write(f"🔍 Verifying updates...")
            response = supabase.table('activities').select("*").execute()
            df_updated = pd.DataFrame(response.data)
            df_updated['cleaned_sport_type'] = df_updated['sport_type'].apply(clean_sport_type_admin)
            
            st.write("📈 Updated sport_type distribution:")
            st.write(df_updated['cleaned_sport_type'].value_counts())
            
            st.success("✅ Activity classification fix completed!")
    
    # Run the admin function
    fix_existing_activities_admin(supabase)

if __name__ == "__main__":
    main()