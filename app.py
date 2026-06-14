import streamlit as st

# 1. PAGE CONFIG
st.set_page_config(page_title="Nadi Jyotish Engine", layout="wide")

import datetime
import requests
import swisseph as swe
import pandas as pd

# 2. PREVENT SILENT C-LIBRARY CRASHES
swe.set_ephe_path('') 

# =====================================================================
# ASTROLOGICAL CONSTANTS
# =====================================================================
PLANETS = {
    swe.SUN: "Sun", swe.MOON: "Moon", swe.MARS: "Mars", 
    swe.MERCURY: "Mercury", swe.JUPITER: "Jupiter", 
    swe.VENUS: "Venus", swe.SATURN: "Saturn",
    swe.TRUE_NODE: "Rahu"
}

VIMSHOTTARI_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
VIMSHOTTARI_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
TOTAL_VIM_YEARS = 120
NAKSHATRA_SPAN = 360.0 / 27.0 

# =====================================================================
# CORE ENGINES
# =====================================================================
def get_nadi_lords(longitude):
    """Calculates Star Lord and Sub Lord based on 120-year Vimshottari fraction."""
    longitude = longitude % 360.0
    nakshatra_idx = int(longitude / NAKSHATRA_SPAN)
    nakshatra_start_lord_idx = (nakshatra_idx * 3) % 9
    position_in_nakshatra = longitude - (nakshatra_idx * NAKSHATRA_SPAN)
    
    star_lord = VIMSHOTTARI_LORDS[nakshatra_start_lord_idx]
    
    sub_lord = None
    accumulated_span = 0.0
    for i in range(9):
        current_lord_idx = (nakshatra_start_lord_idx + i) % 9
        dasha_years = VIMSHOTTARI_YEARS[current_lord_idx]
        sub_span = (dasha_years / TOTAL_VIM_YEARS) * NAKSHATRA_SPAN
        if accumulated_span <= position_in_nakshatra < (accumulated_span + sub_span):
            sub_lord = VIMSHOTTARI_LORDS[current_lord_idx]
            break
        accumulated_span += sub_span
        
    return star_lord, sub_lord

def determine_bhava_placement(planet_long, cusp_dict):
    """Dynamically drops the planet into the correct Placidus house."""
    asc_cusp = cusp_dict[1]
    normalized_planet = (planet_long - asc_cusp) % 360.0
    bounds = {h: (cusp_dict[h] - asc_cusp) % 360.0 for h in range(1, 13)}
    
    for house in range(1, 12):
        if bounds[house] <= normalized_planet < bounds[house + 1]:
            return house
    return 12

@st.cache_data(show_spinner=False)
def get_coordinates(place_name):
    """Fetches Lat/Lon securely."""
    url = f"https://nominatim.openstreetmap.org/search?q={place_name}&format=json&limit=1"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=5).json()
        if isinstance(response, list) and len(response) > 0:
            return float(response[0]['lat']), float(response[0]['lon'])
    except Exception:
        pass
    return None, None

# =====================================================================
# DYNAMIC ORCHESTRATION PIPELINE
# =====================================================================
def generate_nadi_data(dob, tob, lat, lon, tz_offset):
    # Convert Local Time to UTC properly
    local_dt = datetime.datetime.combine(dob, tob)
    utc_dt = local_dt - datetime.timedelta(hours=tz_offset)
    
    jul_day = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, 
                         utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)
    
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    
    # BULLETPROOF AYANAMSA EXTRACTION: 
    # Calculate Sun in both Tropical and Sidereal, find the difference manually.
    # This prevents the library from throwing "0" if ephemeris files are missing.
    res_trop = swe.calc_ut(jul_day, swe.SUN, 0)
    res_sid = swe.calc_ut(jul_day, swe.SUN, swe.FLG_SIDEREAL)
    
    trop_sun = res_trop[0][0] if isinstance(res_trop, tuple) and isinstance(res_trop[0], tuple) else res_trop[0]
    sid_sun = res_sid[0][0] if isinstance(res_sid, tuple) and isinstance(res_sid[0], tuple) else res_sid[0]
    
    lahiri_ayanamsa = (trop_sun - sid_sun) % 360.0
    if lahiri_ayanamsa > 180: lahiri_ayanamsa -= 360.0
    if lahiri_ayanamsa < -180: lahiri_ayanamsa += 360.0
    
    # Apply Umang Taneja's Nadi Rule: Lahiri + 6 mins (0.1 deg)
    nadi_ayanamsa = lahiri_ayanamsa + 0.1 
    
    # Generate Tropical Houses and shift to Nadi Sidereal dynamically
    cusps, ascmc = swe.houses_ex(jul_day, lat, lon, b'P') 
    cusp_dict = {}
    offset = 0 if len(cusps) == 13 else -1
    for i in range(1, 13):
        cusp_dict[i] = (cusps[i + offset] - nadi_ayanamsa) % 360.0
            
    sign_owners = {
        1: "Mars", 2: "Venus", 3: "Mercury", 4: "Moon", 5: "Sun", 6: "Mercury",
        7: "Venus", 8: "Mars", 9: "Jupiter", 10: "Saturn", 11: "Saturn", 12: "Jupiter"
    }
    
    house_ownerships = {lord: [] for lord in VIMSHOTTARI_LORDS}
    for house_num in range(1, 13):
        cusp_sign = int(cusp_dict[house_num] / 30.0) + 1
        owner = sign_owners[cusp_sign]
        house_ownerships[owner].append(house_num)

    planetary_data = {}
    
    for p_id, p_name in PLANETS.items():
        res = swe.calc_ut(jul_day, p_id, 0)
        trop_long = res[0][0] if isinstance(res, tuple) and isinstance(res[0], tuple) else res[0]
        raw_long = (trop_long - nadi_ayanamsa) % 360.0
        
        placement = determine_bhava_placement(raw_long, cusp_dict)
        star_lord, sub_lord = get_nadi_lords(raw_long)
        
        planetary_data[p_name] = {
            "placement": placement,
            "ownership": house_ownerships[p_name],
            "star_lord_name": star_lord,
            "sub_lord_name": sub_lord
        }
        
    # True Node (Rahu/Ketu) specific logic
    rahu_res = swe.calc_ut(jul_day, swe.TRUE_NODE, 0)
    rahu_tropical = rahu_res[0][0] if isinstance(rahu_res, tuple) and isinstance(rahu_res[0], tuple) else rahu_res[0]
    
    rahu_long = (rahu_tropical - nadi_ayanamsa) % 360.0
    ketu_long = (rahu_long + 180.0) % 360.0
    
    ketu_placement = determine_bhava_placement(ketu_long, cusp_dict)
    ketu_star, ketu_sub = get_nadi_lords(ketu_long)
    
    planetary_data["Ketu"] = {
        "placement": ketu_placement,
        "ownership": house_ownerships["Ketu"],
        "star_lord_name": ketu_star,
        "sub_lord_name": ketu_sub
    }

    # Build the fully formatted display table
    table_data = []
    for p_name, data in planetary_data.items():
        p_houses = list(set([data["placement"]] + data["ownership"]))
        p_houses_str = ", ".join(map(str, sorted(p_houses)))
        
        stl_name = data["star_lord_name"]
        sl_name = data["sub_lord_name"]
        
        stl_houses = list(set([planetary_data[stl_name]["placement"]] + planetary_data[stl_name]["ownership"]))
        sl_houses = list(set([planetary_data[sl_name]["placement"]] + planetary_data[sl_name]["ownership"]))
        
        stl_str = f"{stl_name} (" + ", ".join(map(str, sorted(stl_houses))) + ")"
        sl_str = f"{sl_name} (" + ", ".join(map(str, sorted(sl_houses))) + ")"
        
        table_data.append({
            "Planet": p_name,
            "Planet Houses (P)": p_houses_str,
            "Star Lord (StL)": stl_str,
            "Sub Lord (SL)": sl_str
        })
        
    return table_data, nadi_ayanamsa

# =====================================================================
# STREAMLIT UI LAYOUT
# =====================================================================
st.title("🪐 Universal Nadi Significance Engine")
st.markdown("Generates dynamic Nirayana Bhava Chalit scripts for any birth details using True Nodes, Placidus Cusps, and Nadi Ayanamsa.")

with st.sidebar:
    st.header("Birth Details")
    dob_input = st.date_input("Date of Birth", value=datetime.date(1983, 1, 15), min_value=datetime.date(1900, 1, 1))
    tob_input = st.time_input("Time of Birth", value=datetime.time(1, 43))
    
    st.markdown("---")
    st.markdown("**Location Settings**")
    place_input = st.text_input("City, Country", value="Muzaffarnagar, India")
    
    use_manual_coords = st.checkbox("Enter Lat/Lon Manually", value=False)
    if use_manual_coords:
        manual_lat = st.number_input("Latitude", value=29.4727, format="%.4f")
        manual_lon = st.number_input("Longitude", value=77.7085, format="%.4f")
        
    tz_input = st.number_input("Timezone Offset (Hours from UTC)", value=5.5, step=0.5)
    
    st.markdown("---")
    generate_btn = st.button("Generate Script", type="primary", use_container_width=True)

if generate_btn:
    try:
        with st.spinner("Calculating Ephemeris Data..."):
            
            if use_manual_coords:
                lat, lon = manual_lat, manual_lon
            else:
                lat, lon = get_coordinates(place_input)
            
            if lat is None or lon is None:
                st.error("Could not locate city. Check the 'Enter Lat/Lon Manually' box and input coordinates directly.")
            else:
                data, ayanamsa = generate_nadi_data(dob_input, tob_input, lat, lon, tz_input)
                df = pd.DataFrame(data)
                
                st.success("Calculation Complete")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Latitude", f"{lat:.4f}")
                col2.metric("Longitude", f"{lon:.4f}")
                
                degrees = int(ayanamsa)
                minutes = int((ayanamsa - degrees) * 60)
                col3.metric("Nadi Ayanamsa Applied", f"{degrees}° {minutes}'")
                
                st.subheader("Dynamic Nadi Significance Table")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                st.info("⚠️ **Note on Rahu & Ketu:** The script currently displays their Base Placement + Sign Lord ownership. If manual planetary aspects exist in the chart (e.g., Saturn aspecting Ketu), those extra houses must be mentally added to the nodes' scripts by the astrologer.")
                
    except Exception as e:
        import traceback
        st.error(f"A calculation error occurred: {str(e)}")
        st.code(traceback.format_exc(), language="python")