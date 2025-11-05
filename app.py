# -*- coding: utf-8 -*-
# KMG Labs - EFC | Projeção Climatológica RCP 8.5 — Vale S.A

import io, os, zipfile, typing as t
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

try:
    import geopandas as gpd
    import folium
    from streamlit_folium import st_folium
    GEO_OK = True
except Exception:
    GEO_OK = False

from unidecode import unidecode

# ---- CONFIG UI ----
st.set_page_config(page_title="KMG Labs - EFC", page_icon="🌎", layout="wide")
st.markdown("""
<style>
.stApp { background:#111; color:#e6e6e6; }
.block-container { padding-top: 0.5rem; }
.stMetric { background:#1b1b1b; border-radius:12px; padding:10px; }
hr { border:none; height:1px; background:#2a2a2a; }
img[data-testid="stImage"] {
    height:100px !important;
    object-fit:contain !important;
}
</style>
""", unsafe_allow_html=True)

# ---- BRANDING TOP ----
c1, c2 = st.columns([1, 8])
with c1:
    if os.path.exists("logo.png"):
        st.image("logo.png")
with c2:
    st.markdown("<div style='padding-top:10px;'>"
                "<span style='font-size:30px;font-weight:700;'>KMG Labs - EFC</span><br>"
                "<span style='font-size:17px;color:#ccc;'>Projeção Climática RCP 8.5 — Vale S.A</span>"
                "</div>", unsafe_allow_html=True)
st.markdown("---")

# ---- HELPERS ----
def normalize(x): 
    return " ".join(unidecode(str(x)).strip().upper().split())

@st.cache_data
def load_excel(path="dados.xlsx"):
    df = pd.read_excel(path)
    ren = {}
    for c in df.columns:
        lc = c.lower().strip()
        if lc in ["municipio","município","nm_mun","nome_municipio"]: ren[c]="municipio"
        if lc in ["variavel","variável","variable"]: ren[c]="variavel"
        if lc in ["valor","value","media"]: ren[c]="valor"
    df = df.rename(columns=ren)
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
    up = st.file_uploader("Enviar novo dados.xlsx", type=["xlsx"])
    df = load_excel(up) if up else load_excel()
    variaveis = sorted(df["variavel"].unique())
    variavel = st.selectbox("Variável", ["Selecione uma variável"] + variaveis)
    top_n = st.slider("Top N", 3, 30, 6)
    show_map = st.checkbox("Exibir Mapa", True)

if variavel == "Selecione uma variável":
    st.info("Selecione uma variável à esquerda ⬅️")
    st.stop()

# ---- RANKING ----
res = df[df["variavel"]==variavel].copy().sort_values("valor",ascending=False).reset_index(drop=True)
res["mun_norm"] = res["municipio"].apply(normalize)

k1,k2,k3,k4 = st.columns(4)
k1.metric("Máximo", fmt(res["valor"].max()))
k2.metric("Mínimo", fmt(res["valor"].min()))
k3.metric("Média", fmt(res["valor"].mean()))
k4.metric("Mediana", fmt(res["valor"].median()))

st.markdown("### 🏆 Ranking dos Municípios")
st.dataframe(res[["municipio","valor"]], hide_index=True)

# ---- GRÁFICO ----
st.markdown(f"### 📈 Top {top_n} — {variavel}")
topv=res.head(top_n)
fig, ax = plt.subplots(figsize=(9,6))
bars = ax.barh(topv["municipio"], topv["valor"], color="#ED7D31")
ax.invert_yaxis()
ax.grid(axis="x", linestyle="--", alpha=0.4)
for b in bars:
    ax.text(b.get_width()*1.01, b.get_y()+b.get_height()/2,
            fmt(b.get_width()), va="center", fontsize=9, color="#eee")
st.pyplot(fig)

# ---- MAPA ----
if show_map and GEO_OK:
    gdf = load_shp_zip()
    if gdf is not None:
        gdf = gdf.merge(res, on="mun_norm", how="left")

        m = folium.Map(location=[-15,-55], zoom_start=4, tiles=None)
        folium.TileLayer("cartodbdark_matter", name="Mapa base (escuro)").add_to(m)

        fg = folium.FeatureGroup(name="Mapa Temático")
        ch = folium.Choropleth(
            geo_data=gdf.to_json(),
            data=gdf,
            columns=["mun_norm","valor"],
            key_on="feature.properties.mun_norm",
            fill_opacity=0.85, line_opacity=0.15,
            legend_name=f"Valor — {variavel}"
        )
        ch.add_to(m)  # ✅ fix principal

        # tooltip sem layercontrol
        folium.GeoJson(
            gdf,
            control=False,
            style_function=lambda x: {"color":"transparent","weight":0,"fillOpacity":0},
            tooltip=folium.GeoJsonTooltip(
                fields=["NM_MUN","valor"],
                aliases=["Município","Valor"],
                localize=True
            )
        ).add_to(m)

        # Top N
        tops=set(topv["mun_norm"])
        folium.GeoJson(
            gdf[gdf["mun_norm"].isin(tops)],
            name=f"Top {top_n}",
            style_function=lambda x: {"color":"#ffcc00","weight":3,"fillOpacity":0},
            tooltip=folium.GeoJsonTooltip(
                fields=["NM_MUN","valor"],
                aliases=["Município","Valor"],
                localize=True
            )
        ).add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)

        # Zoom automático
        focus = gdf[gdf["valor"].notna()]
        minx,miny,maxx,maxy = focus.total_bounds
        m.fit_bounds([[miny,minx],[maxy,maxx]])

        st_folium(m, height=560, width=None)
    else:
        st.warning("📌 Shapefile não carregado.")

# ---- DOWNLOADS ----
csv = res.to_csv(index=False).encode("utf-8")
st.download_button("Baixar CSV", csv, "ranking.csv", "text/csv")

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as w:
    res.to_excel(w, index=False, sheet_name="ranking")
buffer.seek(0)
st.download_button("Baixar Excel", buffer, "ranking.xlsx")