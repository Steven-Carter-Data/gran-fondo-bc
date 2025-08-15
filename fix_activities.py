#!/usr/bin/env python3
"""
Script to add to app.py to fix existing activities in the database by distinguishing 
between 'Bike' (with elevation) and 'Peloton' (without elevation) activities.

This can be run as a one-time function within the Streamlit app.
"""

def fix_existing_activities(supabase):
    """
    Fix existing activities in the database by reclassifying 'Peloton' activities
    that have elevation data as 'Bike' activities.
    """
    import pandas as pd
    
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
    def clean_sport_type(value):
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
    
    df['cleaned_sport_type'] = df['sport_type'].apply(clean_sport_type)
    
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
        df_updated['cleaned_sport_type'] = df_updated['sport_type'].apply(clean_sport_type)
        
        st.write("📈 Updated sport_type distribution:")
        st.write(df_updated['cleaned_sport_type'].value_counts())
        
        st.success("✅ Activity classification fix completed!")

def clean_sport_type(value):
    """Clean sport_type field similar to app.py logic"""
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

def main():
    print("🔧 Starting activity classification fix...")
    
    # Load Supabase configuration
    try:
        supabase_url, supabase_key = load_supabase_config()
        supabase: Client = create_client(supabase_url, supabase_key)
        print("✅ Connected to Supabase")
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return
    
    # Fetch all activities that might need fixing
    print("\n📊 Fetching activities from database...")
    response = supabase.table('activities').select("*").execute()
    
    if not response.data:
        print("❌ No activities found in database")
        return
    
    df = pd.DataFrame(response.data)
    print(f"📋 Found {len(df)} total activities")
    
    # Clean sport_type for analysis
    df['cleaned_sport_type'] = df['sport_type'].apply(clean_sport_type)
    
    # Show current distribution
    print("\n📈 Current sport_type distribution:")
    print(df['cleaned_sport_type'].value_counts())
    
    # Find activities that should be reclassified
    # Activities with sport_type 'Peloton' (or raw 'Ride') that have elevation
    peloton_activities = df[df['cleaned_sport_type'] == 'Peloton'].copy()
    
    if peloton_activities.empty:
        print("\n✅ No Peloton activities found to analyze")
        return
    
    print(f"\n🔍 Found {len(peloton_activities)} activities currently classified as 'Peloton'")
    
    # Check elevation data
    peloton_activities['has_elevation'] = peloton_activities['total_elevation_gain'].fillna(0) > 0
    
    with_elevation = peloton_activities[peloton_activities['has_elevation']]
    without_elevation = peloton_activities[~peloton_activities['has_elevation']]
    
    print(f"   • {len(with_elevation)} have elevation data (should be 'Bike')")
    print(f"   • {len(without_elevation)} have no elevation (correctly 'Peloton')")
    
    if with_elevation.empty:
        print("\n✅ No activities need to be reclassified")
        return
    
    # Show some examples
    print(f"\n📋 Sample activities that will be changed from 'Peloton' to 'Bike':")
    for _, row in with_elevation.head(5).iterrows():
        elevation_ft = row['total_elevation_gain'] * 3.28084 if row['total_elevation_gain'] else 0
        print(f"   • {row['start_date']} - {row['name']} ({elevation_ft:.0f}ft elevation)")
    
    # Ask for confirmation
    response = input(f"\n❓ Update {len(with_elevation)} activities from 'Peloton' to 'Bike'? (y/N): ")
    
    if response.lower() != 'y':
        print("❌ Update cancelled")
        return
    
    # Perform the updates
    print(f"\n🔄 Updating {len(with_elevation)} activities...")
    
    updated_count = 0
    failed_count = 0
    
    for _, row in with_elevation.iterrows():
        try:
            # Update the sport_type to 'Bike'
            update_response = supabase.table('activities')\
                .update({'sport_type': 'Bike'})\
                .eq('id', row['id'])\
                .execute()
            
            if update_response.data:
                updated_count += 1
                if updated_count % 10 == 0:
                    print(f"   ✅ Updated {updated_count}/{len(with_elevation)} activities...")
            else:
                failed_count += 1
                print(f"   ❌ Failed to update activity {row['id']}")
                
        except Exception as e:
            failed_count += 1
            print(f"   ❌ Error updating activity {row['id']}: {e}")
    
    print(f"\n🎉 Update complete!")
    print(f"   ✅ Successfully updated: {updated_count}")
    print(f"   ❌ Failed updates: {failed_count}")
    
    # Verify the changes
    print(f"\n🔍 Verifying updates...")
    response = supabase.table('activities').select("*").execute()
    df_updated = pd.DataFrame(response.data)
    df_updated['cleaned_sport_type'] = df_updated['sport_type'].apply(clean_sport_type)
    
    print("\n📈 Updated sport_type distribution:")
    print(df_updated['cleaned_sport_type'].value_counts())

if __name__ == "__main__":
    main()