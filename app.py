# -*- coding: utf-8 -*-
# KMG Labs - EFC | Projeção Climática RCP 8.5 — Vale S.A

import io, os, zipfile
import streamlit as st
import pandas as pd
from unidecode import unidecode

try:
    import geopandas as gpd
    import folium
    from streamlit_folium import st_folium
    GEO_OK = True
except:
    GEO_OK = False

# ---- CONFIG ----
st.set_page_config(page_title="KMG Labs - EFC", page_icon="🌎", layout="wide")

st.markdown("""
<style>
.stApp { background:#111; color:#e6e6e6; }
.block-container { padding-top: 0.7rem; }
.legend-custom {
    position: fixed;
    top: 75px;
    right: 25px;
    z-index: 9999;
    background: white;
    color: black;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid #333;
}
</style>
""", unsafe_allow_html=True)

st.title("KMG Labs - EFC")
st.caption("Projeção Climática RCP 8.5 — Vale S.A")
st.markdown("---")

def normalize(s):
    return " ".join(unidecode(str(s)).strip().upper().split())


@st.cache_data
def load_excel(fn="dados.xlsx"):
    df = pd.read_excel(fn)
    df.columns = df.columns.str.strip()
    return df


@st.cache_data
def load_shp():
    ext="shp_cache"
    os.makedirs(ext, exist_ok=True)
    with zipfile.ZipFile("municipios.zip") as z:
        z.extractall(ext)
    shp=None
    for r,_,fs in os.walk(ext):
        for f in fs:
            if f.endswith(".shp"):
                shp=os.path.join(r,f)
                break
        if shp: break
    g = gpd.read_file(shp)
    g["NM_NORM"] = g["NM_MUN"].apply(normalize)
    return g


# ---- DADOS ----
df = load_excel()
municipio_col = df.columns[0]
valor_col = df.columns[1]

df["NM_NORM"] = df[municipio_col].apply(normalize)

st.subheader("Dados")
st.dataframe(df[[municipio_col, valor_col]], use_container_width=True)

# ---- MAPA ----
if GEO_OK:
    st.subheader("Mapa Temático")

    gdf = load_shp()
    gdf = gdf.merge(df, on="NM_NORM", how="left")

    m = folium.Map(location=[-7,-49], zoom_start=6, tiles="cartodbdark_matter")

    folium.Choropleth(
        geo_data=gdf.to_json(),
        data=gdf,
        columns=["NM_NORM", valor_col],
        key_on="feature.properties.NM_NORM",
        fill_color="YlOrRd",
        fill_opacity=0.85,
        line_opacity=0.25,
        nan_fill_color="gray"
    ).add_to(m)

    legend_html = f'<div class="legend-custom">{valor_col}</div>'
    m.get_root().html.add_child(folium.Element(legend_html))

    focus = gdf[gdf[valor_col].notna()]
    if len(focus):
        m.fit_bounds([[focus.total_bounds[1], focus.total_bounds[0]],
                      [focus.total_bounds[3], focus.total_bounds[2]]])

    st_folium(m, height=560, width=None)

# ---- DOWNLOAD ----
st.subheader("Exportar")
csv = df[[municipio_col, valor_col]].to_csv(index=False).encode("utf-8")
st.download_button("Baixar CSV", csv, file_name="dados.csv", mime="text/csv")