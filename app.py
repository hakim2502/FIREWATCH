import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# ==========================================
# FIREWATCH MALAYSIA - WEB DASHBOARD
# ==========================================

st.set_page_config(
    page_title="FIREWATCH Malaysia",
    page_icon="🔥",
    layout="wide"
)

# ==========================================
# TITLE
# ==========================================

st.title("🔥 FIREWATCH MALAYSIA")
st.markdown("### Real-Time Forest Fire Hotspot Monitoring Dashboard")
st.markdown("---")


# ==========================================
# LOAD DATA
# ==========================================

@st.cache_data
def load_data():

    # Hotspot data
    fire = pd.read_csv("fire_data_malaysia.csv")

    # District boundaries
    districts = gpd.read_file("malaysia.district.geojson")

    # Convert hotspot coordinates into GeoDataFrame
    points = gpd.GeoDataFrame(
        fire,
        geometry=gpd.points_from_xy(
            fire["longitude"],
            fire["latitude"]
        ),
        crs="EPSG:4326"
    )

    # Project to metres for reliable distance calculation
    points_m = points.to_crs("EPSG:3857")
    districts_m = districts.to_crs("EPSG:3857")

    district_names = []
    state_names = []

    print("Matching hotspots to districts...")

    for point in points_m.geometry:

        matched = districts_m[districts_m.geometry.contains(point)]

        if len(matched) > 0:
            row = matched.iloc[0]

        else:
            # If point is slightly outside polygon,
            # find nearest district
            distances = districts_m.geometry.distance(point)
            nearest_index = distances.idxmin()
            row = districts_m.loc[nearest_index]

        district_names.append(row["name"])
        state_names.append(row["state_name"])

    points["district"] = district_names
    points["state"] = state_names

    return points, districts


points, districts = load_data()


# ==========================================
# RISK CALCULATION
# ==========================================

def individual_risk(frp):

    if frp > 30:
        return "HIGH"

    elif frp >= 10:
        return "MODERATE"

    else:
        return "LOW"


points["risk"] = points["frp"].apply(individual_risk)


# ==========================================
# DISTRICT RISK
# ==========================================

district_summary = (
    points
    .groupby(["district", "state"])
    .agg(
        hotspots=("frp", "count"),
        total_frp=("frp", "sum"),
        highest_frp=("frp", "max")
    )
    .reset_index()
)


def district_risk(row):

    if row["hotspots"] >= 10 or row["highest_frp"] > 30:
        return "HIGH"

    elif row["hotspots"] >= 5 or row["highest_frp"] >= 10:
        return "MODERATE"

    else:
        return "LOW"


district_summary["risk"] = district_summary.apply(
    district_risk,
    axis=1
)


# ==========================================
# DASHBOARD NUMBERS
# ==========================================

total_hotspots = len(points)

high_risk = len(points[points["risk"] == "HIGH"])
moderate_risk = len(points[points["risk"] == "MODERATE"])
low_risk = len(points[points["risk"] == "LOW"])

highest_frp = points["frp"].max()


# ==========================================
# METRICS
# ==========================================

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "🔥 Total Hotspots",
        total_hotspots
    )

with col2:
    st.metric(
        "🔴 High Risk",
        high_risk
    )

with col3:
    st.metric(
        "🟠 Moderate Risk",
        moderate_risk
    )

with col4:
    st.metric(
        "🟢 Low Risk",
        low_risk
    )

with col5:
    st.metric(
        "⚡ Highest FRP",
        f"{highest_frp:.2f} MW"
    )


st.markdown("---")


# ==========================================
# MAP
# ==========================================

st.subheader("🗺️ Malaysia Fire Risk Map")


m = folium.Map(
    location=[4.2, 109.5],
    zoom_start=6,
    tiles="OpenStreetMap"
)


# ==========================================
# DISTRICT COLORS
# ==========================================

risk_colors = {
    "HIGH": "red",
    "MODERATE": "orange",
    "LOW": "green",
    "NO DATA": "gray"
}


# Create lookup dictionary
risk_lookup = {}

for _, row in district_summary.iterrows():

    key = (row["district"], row["state"])

    risk_lookup[key] = row["risk"]


# ==========================================
# DISTRICT POLYGONS
# ==========================================

for _, district in districts.iterrows():

    district_name = district["name"]
    state_name = district["state_name"]

    risk = risk_lookup.get(
        (district_name, state_name),
        "NO DATA"
    )

    color = risk_colors[risk]

    tooltip_text = (
        f"{district_name}, {state_name}"
        f"<br>Risk: {risk}"
    )

    folium.GeoJson(
        district["geometry"],
        style_function=lambda feature, color=color: {
            "fillColor": color,
            "color": color,
            "weight": 1,
            "fillOpacity": 0.35
        },
        tooltip=folium.Tooltip(
            tooltip_text
        )
    ).add_to(m)


# ==========================================
# HOTSPOT POINTS
# ==========================================

for _, row in points.iterrows():

    if row["risk"] == "HIGH":
        point_color = "red"

    elif row["risk"] == "MODERATE":
        point_color = "orange"

    else:
        point_color = "green"

    popup_text = f"""
    <b>🔥 FIREWATCH HOTSPOT</b><br><br>

    <b>State:</b> {row['state']}<br>
    <b>District:</b> {row['district']}<br>
    <b>Risk:</b> {row['risk']}<br>
    <b>FRP:</b> {row['frp']:.2f} MW<br>
    <b>Latitude:</b> {row['latitude']}<br>
    <b>Longitude:</b> {row['longitude']}
    """

    folium.CircleMarker(
        location=[
            row["latitude"],
            row["longitude"]
        ],
        radius=5,
        color=point_color,
        fill=True,
        fill_color=point_color,
        fill_opacity=0.8,
        popup=folium.Popup(
            popup_text,
            max_width=300
        )
    ).add_to(m)


# ==========================================
# LEGEND
# ==========================================

legend_html = """
<div style="
position: fixed;
bottom: 30px;
left: 30px;
width: 180px;
background-color: white;
border: 2px solid grey;
z-index: 9999;
padding: 10px;
font-size: 14px;
">

<b>🔥 Risk Level</b><br><br>

<span style="color:red;">●</span>
HIGH<br>

<span style="color:orange;">●</span>
MODERATE<br>

<span style="color:green;">●</span>
LOW<br>

<span style="color:gray;">●</span>
NO DATA

</div>
"""

m.get_root().html.add_child(
    folium.Element(legend_html)
)


# ==========================================
# DISPLAY MAP
# ==========================================

st_folium(
    m,
    width=None,
    height=650
)


# ==========================================
# DISTRICT SUMMARY
# ==========================================

st.markdown("---")

st.subheader("📊 District Risk Summary")

display_data = district_summary.copy()

display_data = display_data.sort_values(
    ["risk", "hotspots"],
    ascending=[True, False]
)

display_data = display_data[
    [
        "district",
        "state",
        "hotspots",
        "total_frp",
        "highest_frp",
        "risk"
    ]
]

display_data.columns = [
    "District",
    "State",
    "Hotspots",
    "Total FRP",
    "Highest FRP",
    "Risk"
]

st.dataframe(
    display_data,
    use_container_width=True,
    hide_index=True
)


# ==========================================
# FOOTER
# ==========================================

st.markdown("---")

st.caption(
    "FIREWATCH Malaysia | Forest Fire Hotspot Monitoring System"
)
