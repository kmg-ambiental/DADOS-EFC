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
    MAP_ON = True
except:
    MAP_ON = False

# ---- TEMA ----
st.set_page_config(page_title="KMG Labs - EFC", page_icon="🌎", layout="wide")
st.markdown("""
<style>
.stApp { background:#111; color:#e6e6e6; }
.legend-custom {
    position: fixed;
    top: 75px;
    right: 25px;
    z-index: 9999;
    background: white;
    color: black;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
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
def load_excel(path="dados.xlsx"):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()
    return df

@st.cache_data
def load_shp(path="municipios.zip"):
    ext="shp_tmp"
    os.makedirs(ext, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        z.extractall(ext)
    shp = None
    for root,_,files in os.walk(ext):
        for f in files:
            if f.lower().endswith(".shp"):
                shp = os.path.join(root,f)
                break
        if shp: break
    g = gpd.read_file(shp)
    g["NM_NORM"] = g["NM_MUN"].apply(normalize)
    return g.to_crs(epsg=4326)

# ---- LOAD DADOS ----
df = load_excel()
municipio_col = "MUNICIPIO"
var_col = "VARIAVEL"
val_col = "VALOR"
df["NM_NORM"] = df[municipio_col].apply(normalize)

# ---- VAR LIST ORDERING ----
ord_meses = [
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"
]

def ordem(v):
    up = v.upper()
    for i,m in enumerate(ord_meses):
        if m in up:
            return i
    return 99

variaveis_unique = sorted(df[var_col].unique(), key=ordem)

# ---- SIDEBAR ----
with st.sidebar:
    st.header("⚙️ Controles")
    variavel = st.selectbox("Variável", variaveis_unique)
    show_map = st.checkbox("Exibir mapa temático", True, help="Pode desmarcar em caso de desempenho lento.")

# ---- FILTRO ----
df_sel = df[df[var_col] == variavel].copy()
df_sel = df_sel[[municipio_col, val_col]].sort_values(val_col, ascending=False)

# ---- TABELA ----
st.subheader(f"📊 Dados — {variavel}")
st.dataframe(df_sel, width="stretch")

# ---- MAPA ----
if show_map and MAP_ON:
    st.subheader("🗺️ Mapa Temático")

    gdf = load_shp()
    gdf = gdf.merge(df_sel, left_on="NM_NORM", right_on="MUNICIPIO", how="left")

    m = folium.Map(location=[-6, -47], zoom_start=6, tiles="cartodbdark_matter")

    folium.Choropleth(
        geo_data=gdf.to_json(),
        data=gdf,
        columns=["NM_NORM", val_col],
        key_on="feature.properties.NM_NORM",
        fill_color="YlOrRd",
        fill_opacity=0.85,
        line_opacity=0.3,
        nan_fill_color="gray"
    ).add_to(m)

    legend = f'<div class="legend-custom">{variavel}</div>'
    m.get_root().html.add_child(folium.Element(legend))

    focus = gdf[gdf[val_col].notna()]
    if len(focus):
        minx,miny,maxx,maxy = focus.total_bounds
        m.fit_bounds([[miny,minx],[maxy,maxx]])

    st_folium(m, height=560, width=None)

# ---- DOWNLOAD ----
st.subheader("💾 Exportar Dados")
csv = df_sel.to_csv(index=False).encode("utf-8")
st.download_button("Baixar CSV", csv, file_name="dados_filtrados.csv", mime="text/csv")