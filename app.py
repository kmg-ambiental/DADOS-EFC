# -*- coding: utf-8 -*-
# KMG Labs - EFC | Projeção Climatológica RCP 8.5 — Vale S.A

import io, os, zipfile, typing as t
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# módulos do mapa
try:
    import geopandas as gpd
    import folium
    from streamlit_folium import st_folium
    GEO_OK = True
except Exception:
    GEO_OK = False

from unidecode import unidecode

# --------------------- Config / Tema ---------------------
st.set_page_config(page_title="KMG Labs - EFC", page_icon="🌎", layout="wide")

st.markdown("""
<style>
.stApp { background:#111; color:#e6e6e6; }
.block-container { padding-top: 1rem; }
.stMetric { background:#1b1b1b; border-radius:12px; padding:10px; }
hr { border: none; height: 1px; background: #2a2a2a; }
</style>
""", unsafe_allow_html=True)

# --------------------- Branding topo ---------------------
c1, c2 = st.columns([1,6])
with c1:
    # coloque sua logo na raiz do repo com o nome logo.png
    if os.path.exists("logo.png"):
        st.image("logo.png", width=100)
with c2:
    st.markdown("## **KMG Labs - EFC**")
    st.markdown("Projeção Climatológica RCP 8.5 — Vale S.A")
st.markdown("---")

# --------------------- Helpers ---------------------------
def normalize_name(s: t.Any) -> str:
    s = unidecode(str(s)).strip().upper()
    return " ".join(s.split())

@st.cache_data
def load_excel(path="dados.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path)
    # normaliza nomes
    ren = {}
    for c in df.columns:
        lc = c.strip().lower()
        if lc in ["municipio","município","nm_mun","nome_municipio"]: ren[c]="municipio"
        elif lc in ["variavel","variável","variable","indicador"]:      ren[c]="variavel"
        elif lc in ["valor","value","media","média"]:                   ren[c]="valor"
    df = df.rename(columns=ren)
    for col in ["municipio","variavel","valor"]:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente: {col}")
    df["municipio"] = df["municipio"].astype(str).str.strip()
    df["variavel"]  = df["variavel"].astype(str).str.strip()
    df["valor"]     = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["valor"])
    return df

@st.cache_data
def load_shapefile_zip(zip_path="municipios.zip"):
    if not GEO_OK: return None
    ext = "shp_cache"
    os.makedirs(ext, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z: z.extractall(ext)
    shp = None
    for r,_,fs in os.walk(ext):
        for f in fs:
            if f.lower().endswith(".shp"): shp = os.path.join(r,f); break
        if shp: break
    if shp is None: raise FileNotFoundError("Shapefile (.shp) não encontrado no ZIP.")
    gdf = gpd.read_file(shp)
    if "NM_MUN" not in gdf.columns:
        raise ValueError("Campo 'NM_MUN' não existe no shapefile.")
    gdf["mun_norm"] = gdf["NM_MUN"].apply(normalize_name)
    # simplificação leve p/ web
    try:
        gdf = gdf.to_crs(3857)
        gdf["geometry"] = gdf.geometry.simplify(200, preserve_topology=True)
        gdf = gdf.to_crs(4326)
    except Exception:
        pass
    return gdf

def fmt(x): 
    try: return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    except: return "—"

def export_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="ranking")
    buf.seek(0)
    return buf.read()

# --------------------- Sidebar ---------------------------
with st.sidebar:
    st.header("⚙️ Controles")
    up = st.file_uploader("Enviar novo dados.xlsx", type=["xlsx"])
    if up is None:
        df = load_excel("dados.xlsx")
    else:
        df = load_excel(up)

    variaveis = sorted(df["variavel"].unique())
    variavel = st.selectbox("Selecione a variável", ["— Selecione —"] + variaveis, index=0)
    top_n = st.slider("Top N (destaque)", 3, 30, 6)
    show_map = st.checkbox("Exibir mapa", value=True)

if variavel == "— Selecione —":
    st.info("Selecione uma **variável** na barra lateral para exibir ranking, gráfico e mapa.")
    st.stop()

# --------------------- Ranking + KPIs --------------------
res = df[df["variavel"]==variavel].copy().sort_values("valor", ascending=False).reset_index(drop=True)
res["mun_norm"] = res["municipio"].apply(normalize_name)

k1,k2,k3,k4 = st.columns(4)
k1.metric("Máximo", fmt(res["valor"].max()))
k2.metric("Mínimo", fmt(res["valor"].min()))
k3.metric("Média",  fmt(res["valor"].mean()))
k4.metric("Mediana",fmt(res["valor"].median()))

st.markdown("### 🏆 Ranking dos Municípios")
st.dataframe(res[["municipio","valor"]], use_container_width=True, hide_index=True)

# --------------------- Gráfico estilo Excel --------------
st.markdown("### 📈 Gráfico (Top N) — estilo Excel")
topv = res.head(top_n)

fig, ax = plt.subplots(figsize=(9,6))
bars = ax.barh(topv["municipio"], topv["valor"], color="#ED7D31")  # laranja Office
ax.invert_yaxis()
ax.set_xlabel("Valor")
ax.set_ylabel("Município")
ax.set_title(variavel)
ax.grid(axis="x", alpha=0.3, linestyle="--")
# valores nas barras
for b in bars:
    w = b.get_width()
    ax.text(w + (max(topv["valor"])*0.01), b.get_y()+b.get_height()/2,
            fmt(w), va="center", fontsize=9)
st.pyplot(fig)

# --------------------- Mapa Folium -----------------------
if show_map and GEO_OK:
    st.markdown("### 🗺️ Mapa Temático (contínuo, join por NM_MUN)")

    try:
        gdf = load_shapefile_zip("municipios.zip")
    except Exception as e:
        st.error(f"Erro ao carregar o shapefile: {e}")
        gdf = None

    if gdf is not None and len(gdf):
        gdfm = gdf.merge(res[["mun_norm","valor"]], on="mun_norm", how="left")

        # Base map escuro com nome limpo
        m = folium.Map(location=[-14.2350,-51.9253], zoom_start=4, tiles=None)
        folium.TileLayer("cartodbdark_matter", name="Mapa base (escuro)").add_to(m)

        # Choropleth dentro de um FeatureGroup p/ nome amigável
        fg = folium.FeatureGroup(name="Mapa Temático", show=True)
        ch = folium.Choropleth(
            geo_data=gdfm.to_json(),
            data=gdfm,
            columns=["mun_norm","valor"],
            key_on="feature.properties.mun_norm",
            fill_opacity=0.85, line_opacity=0.15, legend_name=f"Valor — {variavel}"
        )
        ch.add_to(fg)
        fg.add_to(m)

        # Tooltip (sem aparecer no LayerControl)
        folium.GeoJson(
            gdfm,
            control=False,
            style_function=lambda x: {"weight":0, "color":"transparent", "fillOpacity":0},
            tooltip=folium.GeoJsonTooltip(
                fields=["NM_MUN","valor"],
                aliases=["Município","Valor"],
                localize=True
            )
        ).add_to(m)

        # Destaque Top N
        tops = set(topv["mun_norm"])
        folium.GeoJson(
            gdfm[gdfm["mun_norm"].isin(tops)],
            name=f"Top {top_n}",
            style_function=lambda x: {"color":"#ffcc00","weight":3,"fillOpacity":0},
            tooltip=folium.GeoJsonTooltip(fields=["NM_MUN","valor"], aliases=["Município","Valor"])
        ).add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)

        # 🔎 Fit bounds nos municípios com valor (foco no shape)
        focus = gdfm[gdfm["valor"].notna()]
        if len(focus):
            minx, miny, maxx, maxy = focus.total_bounds
        else:
            minx, miny, maxx, maxy = gdfm.total_bounds
        m.fit_bounds([[miny, minx],[maxy, maxx]])

        st_folium(m, height=560, width=None)
    else:
        st.warning("Shapefile vazio ou não carregado.")

# --------------------- Downloads -------------------------
st.markdown("### ⬇️ Downloads")
csv_bytes = res[["municipio","variavel","valor"]].to_csv(index=False).encode("utf-8")
st.download_button("Baixar CSV (variável filtrada)", data=csv_bytes,
                   file_name=f"ranking_{variavel}.csv", mime="text/csv")
excel_bytes = io.BytesIO()
with pd.ExcelWriter(excel_bytes, engine="openpyxl") as w:
    res.to_excel(w, index=False, sheet_name="ranking")
excel_bytes.seek(0)
st.download_button("Baixar Excel (variável filtrada)", data=excel_bytes,
                   file_name=f"ranking_{variavel}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
