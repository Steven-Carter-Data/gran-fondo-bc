# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Bourbon Chasers Gran Fondo Competition Dashboard** - A Streamlit-based web application that tracks cycling performance for an 8-week competition (August 11 - October 5, 2025). The app integrates with Strava data via Supabase to display athlete performance metrics, heart rate zone analysis, and competition leaderboards.

## Architecture

### Tech Stack
- **Frontend Framework**: Streamlit (>=1.28.0)
- **Data Processing**: Pandas (>=2.0.0)
- **Visualization**: Plotly (>=5.17.0)
- **Database**: Supabase (>=2.0.0)
- **Authentication**: Supabase credentials stored in `.streamlit/secrets.toml`

### Core Components

#### Main Application (`app.py`)
Single-file Streamlit application (~3000+ lines) containing:
- Competition date management (8-week period)
- Athlete performance tracking
- Heart rate zone calculations and point scoring
- Weekly performance analytics
- Interactive dashboards with multiple views

#### Key Data Flows
1. **Data Fetching**: Functions prefixed with `fetch_` retrieve data from Supabase
   - `fetch_athletes()`: Gets athlete roster
   - `fetch_activities_by_date_range()`: Retrieves Strava activities
   - `fetch_heart_rate_zones_by_date()`: Gets HR zone data

2. **Calculations**: Functions prefixed with `calculate_` process raw data
   - `calculate_hr_zone_points()`: Computes performance points based on HR zones
   - `calculate_weekly_athlete_performance()`: Aggregates weekly stats
   - `calculate_athlete_cycling_stats()`: Generates comprehensive statistics
   - `calculate_athlete_streaks()`: Tracks consecutive days with activities

3. **UI Components**: Heavy use of custom HTML/CSS for styling
   - Epic leaderboard display with streak counters
   - Weekly performance charts
   - Athlete comparison views
   - Team totals dashboard
   - Activity streak tracking (daily consistency)

## Development Commands

### Running the Application
```bash
# Start the Streamlit app
streamlit run app.py

# Alternative with specific port
streamlit run app.py --server.port 8501
```

### Dependencies Management
```bash
# Install dependencies
pip install -r requirements.txt

# Update dependencies
pip install --upgrade -r requirements.txt
```

### Environment Setup
The application requires Supabase credentials configured in `.streamlit/secrets.toml`:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase anon/public key

## Database Schema

The app expects these Supabase tables:
- **athletes**: Athlete roster and metadata
- **activities**: Strava activity data including distance, duration, elevation
- **hr_zones**: Heart rate zone data for point calculations

Key columns used:
- Activities: `athlete_id`, `start_date`, `distance`, `moving_time`, `total_elevation_gain`
- HR Zones: `athlete_id`, `start_date`, `zone_1_seconds` through `zone_5_seconds`

## Competition Logic

### Week Calculation
- Competition runs Monday to Sunday for 8 weeks
- Week boundaries defined in `get_competition_week_dates()`
- Current week status tracked by `get_current_competition_week()`

### Point System
Heart rate zones earn different points:
- Zone 1: 1 point per hour
- Zone 2: 2 points per hour
- Zone 3: 3 points per hour
- Zone 4: 4 points per hour
- Zone 5: 5 points per hour

## UI/UX Features

- **Caching**: Uses `@st.cache_data` with 60-second TTL for performance
- **Responsive Design**: Custom CSS for mobile and desktop views
- **Interactive Filters**: Athlete selection, date range pickers
- **Real-time Updates**: Data refreshes every minute via cache expiration

## Testing & Debugging

### Common Issues
1. **Python 3.13 Compatibility**: Special asyncio handling included for Python 3.13+
2. **Data Loading**: Check Supabase connection if data doesn't appear
3. **Date Ranges**: Ensure dates fall within competition period (Aug 11 - Oct 5, 2025)

### Debug Mode
Add debug prints after data fetching to verify:
```python
st.write(f"Loaded {len(df)} records")
```

## Deployment Considerations

- Assets folder contains logo images (`logo.png`, `sidebar-logo.png`)
- Streamlit Cloud deployment requires secrets configuration
- Consider setting up proper error boundaries for production