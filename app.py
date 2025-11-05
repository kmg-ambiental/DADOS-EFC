# -*- coding: utf-8 -*-
# KMG Labs - EFC | Projeção Climática RCP 8.5 — Vale S.A

import os, zipfile
import pandas as pd
import streamlit as st
from unidecode import unidecode

try:
    import geopandas as gpd
    import folium
    from streamlit_folium import st_folium
    MAP_OK = True
except:
    MAP_OK = False


# ---- VISUAL / THEME ----
st.set_page_config(page_title="KMG Labs - EFC", page_icon="🌎", layout="wide")
st.markdown("""
<style>
.stApp { background:#111; color:#eee; }
.block-container { padding-top:0.7rem; }

.legend-custom {
    position: fixed;
    top: 88px;
    right: 25px;
    z-index: 9999;
    background: rgba(255,255,255,0.95);
    color: #000;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid #333;
}
</style>
""", unsafe_allow_html=True)


# ---- HEADER ----
col1, col2 = st.columns([3,1])

with col1:
    st.title("KMG Labs - EFC")
    st.caption("Projeção Climática RCP 8.5 — Vale S.A")

with col2:
    dl_placeholder = st.container()

st.write("---")


# ---- HELPERS ----
def normalize(s):
    return " ".join(unidecode(str(s)).strip().upper().split())


# ---- LOAD EXCEL ----
@st.cache_data
def load_excel():
    df = pd.read_excel("dados.xlsx")
    df.columns = [c.strip() for c in df.columns]
    df["NM_NORM"] = df["MUNICIPIO"].apply(normalize)
    return df


# ---- LOAD SHAPEFILE ----
@st.cache_data
def load_shp():
    folder = "shp_cache"
    os.makedirs(folder, exist_ok=True)
    with zipfile.ZipFile("municipios.zip") as z:
        z.extractall(folder)

    shp_path = None
    for r,_,fs in os.walk(folder):
        for f in fs:
            if f.lower().endswith(".shp"):
                shp_path = os.path.join(r,f)
                break
        if shp_path: break

    g = gpd.read_file(shp_path)
    g["NM_NORM"] = g["NM_MUN"].apply(normalize)
    return g.to_crs(epsg=4326)


df = load_excel()


# ---- ORDER VARIABLES ----
meses_ord = [
    "JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO",
    "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"
]
def ordenar(v):
    u = v.upper()
    for i,m in enumerate(meses_ord):
        if m in u:
            return i
    return 999  # Anuais por último

variaveis = sorted(df["VARIAVEL"].unique(), key=ordenar)


# ---- SIDEBAR CONTROLS ----
with st.sidebar:
    st.header("⚙️ Controles")
    variavel = st.selectbox("Variável", variaveis)
    show_map = st.checkbox("Exibir Mapa Temático", True)


# ---- FILTER DATA ----
df_sel = df[df["VARIAVEL"] == variavel].copy()
df_sel["NM_NORM"] = df_sel["MUNICIPIO"].apply(normalize)
df_sel = df_sel[['MUNICIPIO','NM_NORM','VALOR']].sort_values("VALOR", ascending=False)


# ---- TABLE ----
st.subheader(f"📊 Dados — {variavel}")
st.dataframe(df_sel[['MUNICIPIO','VALOR']], width="stretch")


# ---- EXPORT BUTTON ----
with dl_placeholder:
    st.download_button(
        "Baixar CSV",
        df_sel[['MUNICIPIO','VALOR']].to_csv(index=False).encode("utf-8"),
        file_name=f"dados_{normalize(variavel)}.csv",
        mime="text/csv"
    )


# ---- MAP ----
if show_map and MAP_OK:
    st.subheader("🗺️ Mapa Temático")

    gdf = load_shp()
    gdf = gdf.merge(df_sel, on="NM_NORM", how="left")

    m = folium.Map(location=[-6.5,-47.5], zoom_start=6, tiles="cartodbpositron")

    folium.Choropleth(
        geo_data=gdf.to_json(),
        data=gdf,
        columns=["NM_NORM","VALOR"],
        key_on="feature.properties.NM_NORM",
        fill_color="YlOrRd",
        fill_opacity=0.85,
        line_opacity=0.4,
        nan_fill_color="gray"
    ).add_to(m)

    legend = f'<div class="legend-custom">{variavel}</div>'
    m.get_root().html.add_child(folium.Element(legend))

    focus = gdf[gdf["VALOR"].notna()]
    if len(focus):
        minx,miny,maxx,maxy = focus.total_bounds
        m.fit_bounds([[miny,minx],[maxy,maxx]])

    st_folium(m, height=560, width="stretch")