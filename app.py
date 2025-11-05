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
except Exception:
    GEO_OK = False


# ---- CONFIG TEMA ----
st.set_page_config(page_title="KMG Labs - EFC", page_icon="🌎", layout="wide")
st.markdown("""
<style>
.stApp { background:#111; color:#e6e6e6; }
.block-container { padding-top: 0.7rem; }
.dataframe tbody tr td { color:#eee !important; }
.download-area button {
    background-color: #ED7D31 !important;
    color: white !important;
    border-radius: 8px !important;
    font-weight: bold !important;
}
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


# ---- CABEÇALHO ----
st.markdown("""
<div style='margin-bottom:-10px;padding-left:5px;'>
<span style='font-size:30px;font-weight:700;'>KMG Labs - EFC</span><br>
<span style='font-size:17px;color:#ccc;'>Projeção Climática RCP 8.5 — Vale S.A</span>
</div>
""", unsafe_allow_html=True)
st.markdown("---")


# ---- HELPERS ----
def normalize(x): 
    return " ".join(unidecode(str(x)).strip().upper().split())


@st.cache_data
def load_excel(path="dados.xlsx"):
    return pd.read_excel(path)


@st.cache_data
def load_shapefile_zip(path="municipios.zip"):
    if not GEO_OK:
        return None
    ext="shp_cache"
    os.makedirs(ext, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        z.extractall(ext)
    shp=None
    for r,_,fs in os.walk(ext):
        for f in fs:
            if f.lower().endswith(".shp"):
                shp=os.path.join(r,f)
                break
        if shp: break
    g=gpd.read_file(shp)
    g["mun_norm"]=g["NM_MUN"].apply(normalize)
    return g


# ---- SIDEBAR ----
with st.sidebar:
    st.header("⚙️ Controles")

    df = load_excel()
    municipios_col = df.columns[0]
    variaveis = sorted(df.columns[2:])

    variavel = st.selectbox("Variável", variaveis)
    show_map = st.checkbox("Exibir Mapa Temático", True)


# ---- DADOS ----
st.markdown(f"### Dados — {variavel}")

df_local = df.copy()
df_local["mun_norm"] = df_local[municipios_col].apply(normalize)
df_local = df_local[[municipios_col, variavel]].sort_values(variavel, ascending=False)

st.dataframe(df_local, use_container_width=True)


# ---- MAPA ----
if show_map and GEO_OK:
    st.markdown("### Mapa Temático")

    gdf = load_shapefile_zip()
    gdf = gdf.merge(df_local, on="mun_norm", how="left")

    m = folium.Map(location=[-15,-55], zoom_start=4, tiles="cartodbdark_matter")

    # Sem legenda do Folium
    ch = folium.Choropleth(
        geo_data=gdf.to_json(),
        data=gdf,
        columns=["mun_norm", variavel],
        key_on="feature.properties.mun_norm",
        fill_color="YlOrRd",
        fill_opacity=0.85,
        line_opacity=0.25,
        show=True
    )
    ch.add_to(m)

    # FIX: legenda discreta e clara
    legend_html = f"""
    <div class="legend-custom">{variavel}</div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Zoom automático nos dados disponíveis
    focus = gdf[gdf[variavel].notna()]
    if len(focus):
        minx,miny,maxx,maxy = focus.total_bounds
        m.fit_bounds([[miny,minx],[maxy,maxx]])

    st_folium(m, height=560, width=None)


# ---- DOWNLOAD ----
st.markdown("### Exportar dados")
csv = df_local.to_csv(index=False).encode("utf-8")
st.download_button("Baixar CSV", csv, file_name="dados_filtrados.csv", mime="text/csv")