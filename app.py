# -*- coding: utf-8 -*-
# KMG Labs - EFC | Projeção Climática RCP 8.5 — Vale S.A

import io, os, zipfile, typing as t
import streamlit as st
import pandas as pd

try:
    import geopandas as gpd
    import folium
    from streamlit_folium import st_folium
    GEO_OK = True
except Exception:
    GEO_OK = False

from unidecode import unidecode

# ---- CONFIG TEMA ----
st.set_page_config(page_title="KMG Labs - EFC", page_icon="🌎", layout="wide")
st.markdown("""
<style>
.stApp { background:#111; color:#e6e6e6; }
.block-container { padding-top: 0.5rem; }
.stMetric { background:#1b1b1b; border-radius:12px; padding:10px; }
hr { border:none; height:1px; background:#2a2a2a; }
#barra {
    background-color: #ED7D31;
    height: 14px;
    border-radius: 4px;
}
.download-area button {
    background-color: #ED7D31 !important;
    color: white !important;
    border-radius: 8px !important;
    font-weight: bold !important;
}
#map { z-index: 0 !important; }
.legend {
    background: white;
    border: 1px solid black;
    border-radius: 4px;
    padding: 6px;
    font-size: 11px;
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
    df = pd.read_excel(path)
    ren={}
    for c in df.columns:
        lc=c.lower().strip()
        if lc in ["municipio","município","nm_mun","nome_municipio"]: ren[c]="municipio"
        if lc in ["variavel","variável","variable"]: ren[c]="variavel"
        if lc in ["valor","value","media"]: ren[c]="valor"
    df=df.rename(columns=ren)
    df["municipio"]=df["municipio"].astype(str).str.strip()
    df["variavel"]=df["variavel"].astype(str).str.strip()
    df["valor"]=pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["valor"])

@st.cache_data
def load_shp_zip(zipfile_path="municipios.zip"):
    if not GEO_OK: return None
    ext="shp_cache"
    os.makedirs(ext, exist_ok=True)
    with zipfile.ZipFile(zipfile_path,"r") as z: z.extractall(ext)
    shp=None
    for r,_,fs in os.walk(ext):
        for f in fs:
            if f.lower().endswith(".shp"): shp=os.path.join(r,f); break
        if shp: break
    g=gpd.read_file(shp)
    g["mun_norm"]=g["NM_MUN"].apply(normalize)
    g=g.to_crs(3857)
    g["geometry"]=g.geometry.simplify(200,preserve_topology=True)
    return g.to_crs(4326)

def fmt(x): 
    try: return f"{float(x):,.2f}".replace(",",".")
    except: return x

# ---- SIDEBAR ----
with st.sidebar:
    st.header("⚙️ Controles")
    up_file = st.file_uploader("Enviar novo dados.xlsx", type=["xlsx"])
    df = load_excel(up_file) if up_file else load_excel()
    variaveis = sorted(df["variavel"].unique())

    # Ordenação customizada
    ordem_meses = [
        "JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO",
        "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"
    ]
    mensais = [v for v in variaveis if "MENSAL" in v.upper()]
    mensais_sorted = sorted(mensais, key=lambda x: ordem_meses.index(x.split("-")[-1].strip().upper()))

    anuais = [v for v in variaveis if "ANUAL" in v.upper()]

    variaveis_ord = mensais_sorted + anuais

    variavel = st.selectbox("Variável", ["Selecione uma variável"] + variaveis_ord)
    show_map = st.checkbox("Exibir Mapa Temático", True)

if variavel == "Selecione uma variável":
    st.info("Selecione uma variável para começar.")
    st.stop()

# ---- RANKEAMENTO ----
res = df[df["variavel"]==variavel].copy().sort_values("valor",ascending=False).reset_index(drop=True)
res["mun_norm"]=res["municipio"].apply(normalize)

# ---- KPIs ----
k1,k2,k3,k4 = st.columns(4)
k1.metric("Máximo", fmt(res["valor"].max()))
k2.metric("Mínimo", fmt(res["valor"].min()))
k3.metric("Média", fmt(res["valor"].mean()))
k4.metric("Mediana", fmt(res["valor"].median()))

# ---- TABELA EXCEL-LIKE ----
st.markdown(f"### Ranking — {variavel}")

def barra(v, vmax):
    p = (v / vmax) if vmax > 0 else 0
    return f"""
        <div style="width:100%;background:#333;border-radius:4px;height:14px;">
            <div id="barra" style="width:{p*100:.1f}%;"></div>
        </div>
    """

vmax = res["valor"].max()
res["Gráfico"] = res["valor"].apply(lambda v: barra(v,vmax))

st.write(res[["municipio","valor","Gráfico"]].to_html(escape=False,index=False), unsafe_allow_html=True)

# ---- MAPA ----
if show_map and GEO_OK:
    st.markdown("### Mapa Temático")

    gdf = load_shp_zip()
    gdf = gdf.merge(res, on="mun_norm", how="left")

    m = folium.Map(location=[-15,-55], zoom_start=4, tiles=None)
    folium.TileLayer("cartodbdark_matter", name="Mapa base (escuro)").add_to(m)

    ch = folium.Choropleth(
        geo_data=gdf.to_json(),
        data=gdf,
        columns=["mun_norm","valor"],
        key_on="feature.properties.mun_norm",
        fill_opacity=0.85, line_opacity=0.2,
        lege