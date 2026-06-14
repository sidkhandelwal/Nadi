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

SHORT_NAMES = {
    "Sun": "Sun", "Moon": "Mon", "Mars": "Mar", 
    "Mercury": "Mer", "Jupiter": "Jup", "Venus": "Ven", 
    "Saturn": "Sat", "Rahu": "Rah", "Ketu": "Ket"
}

VIMSHOTTARI_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
VIMSHOTTARI_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
TOTAL_VIM_YEARS = 120
NAKSHATRA_SPAN = 360.0 / 27.0 

# =====================================================================
# CORE ENGINES
# =====================================================================
def get_nadi_lords(longitude):
    longitude = longitude % 360.0
    nakshatra_idx = int(longitude / NAKSHATRA_SPAN)
    
    star_lord_idx = nakshatra_idx % 9
    position_in_nakshatra = longitude - (nakshatra_idx * NAKSHATRA_SPAN)
    
    star_lord = VIMSHOTTARI_LORDS[star_lord_idx]
    
    sub_lord = None
    accumulated_span = 0.0
    for i in range(9):
        current_lord_idx = (star_lord_idx + i) % 9
        dasha_years = VIMSHOTTARI_YEARS[current_lord_idx]
        sub_span = (dasha_years / TOTAL_VIM_YEARS) * NAKSHATRA_SPAN
        if accumulated_span <= position_in_nakshatra < (accumulated_span + sub_span) + 1e-6:
            sub_lord = VIMSHOTTARI_LORDS[current_lord_idx]
            break
        accumulated_span += sub_span
        
    return star_lord, sub_lord

def determine_bhava_placement(planet_long, cusp_dict):
    asc_cusp = cusp_dict[1]
    normalized_planet = (planet_long - asc_cusp) % 360.0
    bounds = {h: (cusp_dict[h] - asc_cusp) % 360.0 for h in range(1, 13)}
    
    for house in range(1, 12):
        if bounds[house] <= normalized_planet < bounds[house + 1]:
            return house
    return 12

def get_aspecting_planets(target_sign, planetary_data_with_signs):
    influencers = []
    for p_name, data in planetary_data_with_signs.items():
        if p_name in ["Rahu", "Ketu"]:
            continue 
            
        p_sign = data["sign"]
        
        if p_sign == target_sign:
            influencers.append(p_name)
            continue
            
        dist = (target_sign - p_sign) % 12
        if dist < 0: dist += 12
        dist += 1 
        
        if dist == 7:
            influencers.append(p_name)
        elif p_name == "Mars" and dist in [4, 8]:
            influencers.append(p_name)
        elif p_name == "Jupiter" and dist in [5, 9]:
            influencers.append(p_name)
        elif p_name == "Saturn" and dist in [3, 10]:
            influencers.append(p_name)
            
    return influencers

def get_coordinates(place_name):
    """
    Geocoding Engine fixed with proper API headers and parameter passing
    to bypass OpenStreetMap's anti-bot blocks.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': place_name,
        'format': 'json',
        'limit': 1
    }
    # A unique, respectful user agent prevents IP blocking
    headers = {'User-Agent': 'UmangTanejaNadiEngine_Local/1.0'}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status() # Automatically throws an error if blocked (e.g., 403)
        data = response.json()
        if data and len(data) > 0:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        st.sidebar.warning(f"Geocoding API issue: {e}")
    return None, None

# =====================================================================
# VISUAL CHART GENERATOR 
# =====================================================================
def format_chart_text(sign_num, planets_list):
    lines = [str(sign_num)]
    for i in range(0, len(planets_list), 2):
        lines.append(" ".join(planets_list[i:i+2]))
    return "\n".join(lines)

def create_north_indian_svg(data_dict):
    svg = """
    <svg viewBox="0 0 400 400" style="width:100%; max-width: 450px; height:auto; background-color:#fffaf0; border: 1px solid #e0e0e0; border-radius:8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);" xmlns="http://www.w3.org/2000/svg">
        <rect x="2" y="2" width="396" height="396" fill="none" stroke="#d32f2f" stroke-width="3"/>
        <line x1="2" y1="2" x2="398" y2="398" stroke="#d32f2f" stroke-width="2"/>
        <line x1="2" y1="398" x2="398" y2="2" stroke="#d32f2f" stroke-width="2"/>
        <polygon points="200,2 2,200 200,398 398,200" fill="none" stroke="#d32f2f" stroke-width="2"/>
    """
    centers = {
        1: (200, 100), 2: (100, 50), 3: (50, 100), 4: (100, 200),
        5: (50, 300), 6: (100, 350), 7: (200, 300), 8: (300, 350),
        9: (350, 300), 10: (300, 200), 11: (350, 100), 12: (300, 50)
    }
    for h, text in data_dict.items():
        cx, cy = centers[h]
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if i == 0: 
                dy = (i - len(lines)/2.0 + 0.8) * 16
                svg += f'<text x="{cx}" y="{cy + dy}" font-family="Arial" font-size="13" font-weight="bold" fill="#9e9e9e" text-anchor="middle">{line}</text>'
            else: 
                dy = (i - len(lines)/2.0 + 0.8) * 16
                svg += f'<text x="{cx}" y="{cy + dy}" font-family="Arial" font-size="15" font-weight="bold" fill="#0D47A1" text-anchor="middle">{line}</text>'
    svg += "</svg>"
    return svg

# =====================================================================
# DYNAMIC ORCHESTRATION PIPELINE
# =====================================================================
def generate_nadi_data(dob, tob, lat, lon, tz_offset):
    local_dt = datetime.datetime.combine(dob, tob)
    utc_dt = local_dt - datetime.timedelta(hours=tz_offset)
    jul_day = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, 
                         utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)
    
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    
    res_trop = swe.calc_ut(jul_day, swe.SUN, 0)
    res_sid = swe.calc_ut(jul_day, swe.SUN, swe.FLG_SIDEREAL)
    trop_sun = res_trop[0][0] if isinstance(res_trop, tuple) and isinstance(res_trop[0], tuple) else res_trop[0]
    sid_sun = res_sid[0][0] if isinstance(res_sid, tuple) and isinstance(res_sid[0], tuple) else res_sid[0]
    
    lahiri_ayanamsa = (trop_sun - sid_sun) % 360.0
    if lahiri_ayanamsa > 180: lahiri_ayanamsa -= 360.0
    if lahiri_ayanamsa < -180: lahiri_ayanamsa += 360.0
    nadi_ayanamsa = lahiri_ayanamsa + 0.1 
    
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
    
    # Pass 1: Compute basic info for all true planets
    for p_id, p_name in PLANETS.items():
        res = swe.calc_ut(jul_day, p_id, 0)
        p_trop = res[0][0] if isinstance(res, tuple) and isinstance(res[0], tuple) else res[0]
        raw_long = (p_trop - nadi_ayanamsa) % 360.0
        
        placement = determine_bhava_placement(raw_long, cusp_dict)
        star_lord, sub_lord = get_nadi_lords(raw_long)
        
        planetary_data[p_name] = {
            "placement": placement,
            "ownership": house_ownerships[p_name],
            "star_lord_name": star_lord,
            "sub_lord_name": sub_lord,
            "raw_long": raw_long,
            "sign": int(raw_long / 30.0) + 1
        }
        
    # Pass 2: Setup Nodes
    rahu_res = swe.calc_ut(jul_day, swe.TRUE_NODE, 0)
    rahu_trop = rahu_res[0][0] if isinstance(rahu_res, tuple) and isinstance(rahu_res[0], tuple) else rahu_res[0]
    rahu_long = (rahu_trop - nadi_ayanamsa) % 360.0
    ketu_long = (rahu_long + 180.0) % 360.0
    
    planetary_data["Rahu"] = {
        "placement": determine_bhava_placement(rahu_long, cusp_dict),
        "ownership": house_ownerships["Rahu"],
        "star_lord_name": get_nadi_lords(rahu_long)[0],
        "sub_lord_name": get_nadi_lords(rahu_long)[1],
        "raw_long": rahu_long,
        "sign": int(rahu_long / 30.0) + 1
    }
    
    planetary_data["Ketu"] = {
        "placement": determine_bhava_placement(ketu_long, cusp_dict),
        "ownership": house_ownerships["Ketu"],
        "star_lord_name": get_nadi_lords(ketu_long)[0],
        "sub_lord_name": get_nadi_lords(ketu_long)[1],
        "raw_long": ketu_long,
        "sign": int(ketu_long / 30.0) + 1
    }

    # Pass 3: Node Rules (Aspects, Conjunctions, AND Sign Lord)
    for node in ["Rahu", "Ketu"]:
        node_sign = planetary_data[node]["sign"]
        
        sign_lord = sign_owners[node_sign]
        influencing_planets = [sign_lord]
        influencing_planets.extend(get_aspecting_planets(node_sign, planetary_data))
        influencing_planets = list(set(influencing_planets))
        
        node_extra_houses = []
        for inf_p in influencing_planets:
            node_extra_houses.append(planetary_data[inf_p]["placement"])
            node_extra_houses.extend(planetary_data[inf_p]["ownership"])
            
        planetary_data[node]["ownership"].extend(node_extra_houses)
        planetary_data[node]["ownership"] = list(set(planetary_data[node]["ownership"]))

    # ==========================================
    # CHART GENERATION LOGIC
    # ==========================================
    asc_sidereal = (ascmc[0] - nadi_ayanamsa) % 360.0
    asc_sign = int(asc_sidereal / 30.0) + 1
    
    lagna_dict = {}
    for h in range(1, 13):
        sign_here = (asc_sign + h - 2) % 12 + 1
        planets_here = ["Asc"] if h == 1 else []
        for p, d in planetary_data.items():
            if int(d["raw_long"] / 30.0) + 1 == sign_here:
                planets_here.append(SHORT_NAMES[p])
        lagna_dict[h] = format_chart_text(sign_here, planets_here)

    chalit_dict = {}
    for h in range(1, 13):
        sign_here = int(cusp_dict[h] / 30.0) + 1
        planets_here = ["Asc"] if h == 1 else []
        for p, d in planetary_data.items():
            if d["placement"] == h:
                planets_here.append(SHORT_NAMES[p])
        chalit_dict[h] = format_chart_text(sign_here, planets_here)

    # ==========================================
    # TABLE GENERATION LOGIC
    # ==========================================
    table_data = []
    planet_order = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    
    for p_name in planet_order:
        data = planetary_data[p_name]
        p_houses = list(set([data["placement"]] + data["ownership"]))
        p_houses = [h for h in p_houses if h != 0]
        p_houses_str = ", ".join(map(str, sorted(p_houses)))
        
        stl_name = data["star_lord_name"]
        sl_name = data["sub_lord_name"]
        
        stl_data = planetary_data[stl_name]
        sl_data = planetary_data[sl_name]
        
        stl_houses = list(set([stl_data["placement"]] + stl_data["ownership"]))
        sl_houses = list(set([sl_data["placement"]] + sl_data["ownership"]))
        
        stl_houses = [h for h in stl_houses if h != 0]
        sl_houses = [h for h in sl_houses if h != 0]
        
        stl_str = f"{stl_name} (" + ", ".join(map(str, sorted(stl_houses))) + ")"
        sl_str = f"{sl_name} (" + ", ".join(map(str, sorted(sl_houses))) + ")"
        
        table_data.append({
            "Planet": p_name,
            "Planet Houses (P)": p_houses_str,
            "Star Lord (StL)": stl_str,
            "Sub Lord (SL)": sl_str
        })
        
    return table_data, nadi_ayanamsa, lagna_dict, chalit_dict

# =====================================================================
# STREAMLIT UI LAYOUT
# =====================================================================
st.title("🪐 Universal Nadi Significance Engine")
st.markdown("Generates dynamic Nirayana Bhava Chalit scripts with fully automated Node Agent rules.")

with st.sidebar:
    st.header("Birth Details")
    dob_input = st.date_input("Date of Birth", value=datetime.date(1983, 1, 15), min_value=datetime.date(1900, 1, 1))

    tob_input = st.time_input("Time of Birth", value=datetime.time(1, 43), step=60)
    
    st.markdown("---")
    place_input = st.text_input("City, Country", value="Pune, India")
    
    use_manual_coords = st.checkbox("Enter Lat/Lon Manually", value=False)
    if use_manual_coords:
        manual_lat = st.number_input("Latitude", value=18.5204, format="%.4f")
        manual_lon = st.number_input("Longitude", value=73.8567, format="%.4f")
        
    tz_input = st.number_input("Timezone Offset (Hours from UTC)", value=5.5, step=0.5)
    
    st.markdown("---")
    generate_btn = st.button("Generate Chart & Script", type="primary", use_container_width=True)

if generate_btn:
    try:
        with st.spinner("Calculating Ephemeris Data..."):
            
            if use_manual_coords:
                lat, lon = manual_lat, manual_lon
            else:
                lat, lon = get_coordinates(place_input)
            
            if lat is None or lon is None:
                st.error("Could not locate city via API. Please check the 'Enter Lat/Lon Manually' box and input coordinates directly.")
            else:
                data, ayanamsa, lagna_chart, chalit_chart = generate_nadi_data(dob_input, tob_input, lat, lon, tz_input)
                df = pd.DataFrame(data)
                
                st.success("Calculation Complete")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Latitude", f"{lat:.4f}")
                col2.metric("Longitude", f"{lon:.4f}")
                
                degrees = int(ayanamsa)
                minutes = int((ayanamsa - degrees) * 60)
                col3.metric("Nadi Ayanamsa Applied", f"{degrees}° {minutes}'")
                
                st.markdown("---")
                
                # Visual Charts Display
                chart_col1, chart_col2 = st.columns(2)
                with chart_col1:
                    st.markdown("<h4 style='text-align: center;'>Lagna Chart (Rashi)</h4>", unsafe_allow_html=True)
                    st.markdown(f"<div style='display: flex; justify-content: center;'>{create_north_indian_svg(lagna_chart)}</div>", unsafe_allow_html=True)
                    
                with chart_col2:
                    st.markdown("<h4 style='text-align: center;'>Bhav Chalit (Nirayana)</h4>", unsafe_allow_html=True)
                    st.markdown(f"<div style='display: flex; justify-content: center;'>{create_north_indian_svg(chalit_chart)}</div>", unsafe_allow_html=True)
                
                st.markdown("<br><hr>", unsafe_allow_html=True)
                
                # Table Display
                st.subheader("Dynamic Nadi Significance Table")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                st.success("✔️ **Node Rules Applied:** Rahu and Ketu have successfully inherited the houses of the planets that own their signs, conjunct them, and aspect them.")
                
    except Exception as e:
        import traceback
        st.error(f"A calculation error occurred: {str(e)}")
        st.code(traceback.format_exc(), language="python")