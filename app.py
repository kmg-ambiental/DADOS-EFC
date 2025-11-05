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


# ---- CONFIGURAÇÃO VISUAL ----
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

.download-btn-container {
    display: flex;
    justify-content: flex-end;
    margin-top: -50px;
    margin-right: 10px;
}
</style>
""", unsafe_allow_html=True)

# ---- HEADER ----
col1, col2 = st.columns([3,1])

with col1:
    st.title("KMG Labs - EFC")
    st.caption("Projeção Climática RCP 8.5 — Vale S.A")

st.write("---")

# ---- FUNÇÃO NORMALIZAÇÃO ----
def normalize(s):
    return " ".join(unidecode(str(s)).strip().upper().split())

# ---- CARREGAR DADOS ----
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

    shp_path = None
    for r,_,fs in os.walk(ext):
        for f in fs:
            if f.lower().endswith(".shp"):
                shp_path = os.path.join(r,f)
                break
        if shp_path: break

    g = gpd.read_file(shp_path)
    g["NM_NORM"] = g["NM_MUN"].apply(normalize)
    return g.to_crs(epsg=4326)

df = load_excel()

# ---- ORDEM VARIÁVEIS PELOS MESES ----
meses_ord = [
    "JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO",
    "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"
]

def ordenar_variavel(v):
    u = v.upper()
    for i,m in enumerate(meses_ord):
        if m in u:
            return i
    return 999  # anuais depois dos meses

variaveis = sorted(df["VARIAVEL"].unique(), key=ordenar_variavel)

# ---- SIDEBAR ----
with st.sidebar:
    st.header("⚙️ Controles")
    variavel = st.selectbox("Variável", variaveis)
    show_map = st.checkbox("Exibir Mapa Temático", True)

# ---- AGRUPAMENTO ( MÉDIA ) ----
df_sel = (
    df[df["VARIAVEL"] == variavel]
    .groupby(["MUNICIPIO","NM_NORM"], as_index=False)["VALOR"]
    .mean()
    .sort_values("VALOR", ascending=False)
)

# ---- TABELA ----
st.subheader(f"📊 Dados — {variavel}")
st.dataframe(df_sel[["MUNICIPIO","VALOR"]], width="stretch")

# ---- DOWNLOAD ----
with st.container():
    st.markdown('<div class="download-btn-container">', unsafe_allow_html=True)
    st.download_button(
        "Baixar CSV",
        data=df_sel[['MUNICIPIO','VALOR']].to_csv(index=False).encode("utf-8"),
        file_name=f"{normalize(variavel).replace(' ','_').lower()}_EFC.csv",
        mime="text/csv"
    )
    st.markdown('</div>', unsafe_allow_html=True)

# ---- MAPA TEMÁTICO ----
if show_map and MAP_OK:
    st.subheader("🗺️ Mapa Temático")

    gdf = load_shp()
    gdf = gdf.merge(df_sel, on="NM_NORM", how="left")

    m = folium.Map(
        location=[-6.5,-47.5],
        zoom_start=6,
        tiles="cartodbpositron"
    )

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

    legenda = f'<div class="legend-custom">{variavel}</div>'
    m.get_root().html.add_child(folium.Element(legenda))

    focus = gdf[gdf["VALOR"].notna()]
    if len(focus):
        minx,miny,maxx,maxy = focus.total_bounds
        m.fit_bounds([[miny,minx],[maxy,maxx]])

    st_folium(m, height=560, width="stretch")