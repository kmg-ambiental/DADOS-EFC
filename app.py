# -*- coding: utf-8 -*-
# KMG Labs - EFC | Projeção Climática RCP 8.5 — Vale S.A

import os
import zipfile
import pandas as pd
import streamlit as st
from unidecode import unidecode

try:
    import geopandas as gpd
    import folium
    from streamlit_folium import st_folium
    MAP_ON = True
except:
    MAP_ON = False


# --- CONFIGURAÇÃO DO TEMA ---
st.set_page_config(page_title="KMG Labs - EFC", page_icon="🌎", layout="wide")
st.markdown("""
<style>
.stApp { background:#111; color:#e6e6e6; }
.legend-custom {
    position: fixed;
    top: 80px; right: 20px;
    z-index: 9999;
    background:white;
    color:black;
    padding:4px 10px;
    border-radius:6px;
    font-size:12px;
    font-weight:bold;
    border:1px solid #333;
}
</style>
""", unsafe_allow_html=True)

st.title("KMG Labs - EFC")
st.caption("Projeção Climática RCP 8.5 — Vale S.A")
st.markdown("---")


# --- FUNÇÕES ---
def normalize(s: str):
    return " ".join(unidecode(str(s)).strip().upper().split())


@st.cache_data
def load_excel():
    df = pd.read_excel("dados.xlsx")
    df.columns = [c.strip() for c in df.columns]
    df["NM_NORM"] = df["MUNICIPIO"].apply(normalize)
    return df


@st.cache_data
def load_shp():
    ext = "shp_cache"
    os.makedirs(ext, exist_ok=True)

    with zipfile.ZipFile("municipios.zip") as z:
        z.extractall(ext)

    shp = None
    for r, _, fs in os.walk(ext):
        for f in fs:
            if f.lower().endswith(".shp"):
                shp = os.path.join(r, f)
                break

    gdf = gpd.read_file(shp)
    gdf["NM_NORM"] = gdf["NM_MUN"].apply(normalize)
    return gdf.to_crs(epsg=4326)


# --- CARREGAR DADOS ---
df = load_excel()
variaveis = sorted(df["VARIAVEL"].unique())


# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Controles")
    variavel = st.selectbox("Variável", variaveis)
    show_map = st.checkbox("Exibir Mapa Temático", True)


# --- FILTRAR DADOS ---
df_sel = df[df["VARIAVEL"] == variavel].copy()
df_sel = df_sel[["MUNICIPIO", "VALOR"]].sort_values("VALOR", ascending=False)


# --- TABELA ---
st.subheader(f"📊 Dados — {variavel}")
st.dataframe(df_sel, width="stretch")


# --- MAPA TEMÁTICO ---
if show_map and MAP_ON:
    st.subheader("🗺️ Mapa Temático")

    gdf = load_shp()
    gdf = gdf.merge(df_sel, on="NM_NORM", how="left")

    m = folium.Map(location=[-6, -47], zoom_start=6, tiles="cartodbdark_matter")

    folium.Choropleth(
        geo_data=gdf.to_json(),
        data=gdf,
        columns=["NM_NORM", "VALOR"],
        key_on="feature.properties.NM_NORM",
        fill_color="YlOrRd",
        fill_opacity=0.85,
        line_opacity=0.3,
        nan_fill_color="gray"
    ).add_to(m)

    legend = f'<div class="legend-custom">{variavel}</div>'
    m.get_root().html.add_child(folium.Element(legend))

    bounds = gdf[gdf["VALOR"].notna()].total_bounds
    if len(bounds) == 4:
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

    st_folium(m, height=560, width=None)


# --- DOWNLOAD ---
st.subheader("💾 Exportar Dados")
csv = df_sel.to_csv(index=False).encode("utf-8")
st.download_button("Baixar CSV", csv, file_name="dados_filtrados.csv", mime="text/csv")