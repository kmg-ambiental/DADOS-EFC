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
    top: 85px; right: 20px;
    z-index: 9999;
    background:white;
    color:black;
    padding:4px 9px;
    border-radius:6px;
    font-size:11px;
    border:1px solid #000;
}
</style>
""", unsafe_allow_html=True)

st.title("KMG Labs - EFC")
st.caption("Projeção Climática RCP 8.5 — Vale S.A")
st.write("---")


def normalize(s: str):
    return " ".join(unidecode(str(s)).strip().upper().split())


# ---- CARREGANDO ARQUIVOS ----
@st.cache_data
def load_excel():
    df = pd.read_excel("dados.xlsx")
    df.columns = df.columns.str.strip()
    df["NM_NORM"] = df["MUNICIPIO"].apply(normalize)
    return df

@st.cache_data
def load_shp():
    ext = "shp_tmp"
    os.makedirs(ext, exist_ok=True)
    with zipfile.ZipFile("municipios.zip") as z:
        z.extractall(ext)
    shp = None
    for r,_,fs in os.walk(ext):
        for f in fs:
            if f.endswith(".shp"):
                shp = os.path.join(r,f)
                break
        if shp: break
    g=gpd.read_file(shp)
    g["NM_NORM"]=g["NM_MUN"].apply(normalize)
    return g.to_crs(epsg=4326)


df = load_excel()

# ORDENAR VARIÁVEIS CORRETAMENTE POR MÊS
ord_meses = [
    "JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO",
    "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"
]

def ordem_variavel(v):
    v_up = v.upper()
    for i,mes in enumerate(ord_meses):
        if mes in v_up:
            return i
    return 999  # variáveis anuais

variaveis = sorted(df["VARIAVEL"].unique(), key=ordem_variavel)


# ---- SIDEBAR ----
with st.sidebar:
    st.header("⚙️ Controles")
    variavel = st.selectbox("Variável", variaveis)
    mostrar_mapa = st.checkbox("Exibir Mapa Temático", True)


# ---- FILTRO DADOS ----
df_sel = df[df["VARIAVEL"] == variavel].copy()
df_sel["NM_NORM"] = df_sel["MUNICIPIO"].apply(normalize)
df_sel = df_sel[["MUNICIPIO","NM_NORM","VALOR"]].sort_values("VALOR", ascending=False)


# ---- TABELA ----
st.subheader(f"📊 Dados — {variavel}")
st.dataframe(df_sel[["MUNICIPIO","VALOR"]], width="stretch")


# ---- MAPA ----
if mostrar_mapa and MAP_OK:
    st.subheader("🗺️ Mapa Temático")

    gdf = load_shp()
    gdf = gdf.merge(df_sel, on="NM_NORM", how="left")

    m = folium.Map(location=[-6.5,-47.5], zoom_start=6, tiles="cartodbdark_matter")

    folium.Choropleth(
        geo_data=gdf.to_json(),
        data=gdf,
        columns=["NM_NORM","VALOR"],
        key_on="feature.properties.NM_NORM",
        fill_color="YlOrRd",
        fill_opacity=0.85,
        line_opacity=0.25,
        nan_fill_color="gray"
    ).add_to(m)

    legend=f'<div class="legend-custom">{variavel}</div>'
    m.get_root().html.add_child(folium.Element(legend))

    focus=gdf[gdf["VALOR"].notna()]
    if len(focus):
        minx,miny,maxx,maxy = focus.total_bounds
        m.fit_bounds([[miny,minx],[maxy,maxx]])

    st_folium(m,height=560,width="stretch")


# ---- DOWNLOAD ----
st.subheader("💾 Exportar Dados")
st.download_button(
    "Baixar CSV",
    df_sel[["MUNICIPIO","VALOR"]].to_csv(index=False).encode("utf-8"),
    file_name="dados_filtrados.csv",
    mime="text/csv"
)