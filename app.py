# -*- coding: utf-8 -*-
# KMG — Projeção Climatológica RCP 8.5 — EFC Vale S.A
# Painel Streamlit com:
# - Tema escuro
# - Upload de dados.xlsx
# - Seleção de variável (sem pré-seleção)
# - Ranking, KPIs, gráfico horizontal
# - Mapa temático contínuo (Folium) usando municipios.zip (shapefile Brasil) -> join por NM_MUN
# - Top N configurável e destacado
# - Downloads CSV/Excel

import io
import os
import zipfile
import typing as t

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Opcional/interativo para mapa
try:
    import geopandas as gpd
    from shapely.geometry import Polygon, MultiPolygon  # noqa: F401
    import folium
    from streamlit_folium import st_folium
    GEO_OK = True
except Exception:
    GEO_OK = False

from unidecode import unidecode

# ---------------------------
# Aparência / Tema
# ---------------------------
st.set_page_config(
    page_title="KMG — Projeção Climát. RCP 8.5 — EFC Vale S.A",
    page_icon="📊",
    layout="wide",
)

# Força estilo escuro (para Streamlit Cloud, sugerido usar as configs do tema no app settings)
st.markdown(
    """
    <style>
    .stApp { background-color:#111111; color:#e6e6e6; }
    .block-container { padding-top: 1.2rem; }
    .stMetric { background:#1b1b1b; border-radius:12px; padding:10px; }
    .css-ocqkz7 { color:#e6e6e6 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# Branding
# ---------------------------
st.markdown("## **KMG**")
st.markdown("### Projeção Climatológica RCP 8.5 — EFC Vale S.A")
st.markdown("---")

# ---------------------------
# Helpers
# ---------------------------
def normalize_name(s: t.Any) -> str:
    s = str(s).strip().upper()
    s = unidecode(s)
    s = " ".join(s.split())
    return s

@st.cache_data
def load_excel_default(path: str = "dados.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path)
    # normaliza nomes das colunas
    rename = {}
    for c in df.columns:
        lc = c.strip().lower()
        if lc in ["municipio", "município", "nm_mun", "city", "nome_municipio"]:
            rename[c] = "municipio"
        elif lc in ["variavel", "variável", "variable", "indicador"]:
            rename[c] = "variavel"
        elif lc in ["valor", "value", "media", "média"]:
            rename[c] = "valor"
    if rename:
        df = df.rename(columns=rename)
    # garantias
    for col in ["municipio", "variavel", "valor"]:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente: {col}")
    # tipos
    df["municipio"] = df["municipio"].astype(str).str.strip()
    df["variavel"] = df["variavel"].astype(str).str.strip()
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["valor"])
    return df

@st.cache_data
def load_shapefile_zip(zip_path: str = "municipios.zip") -> "gpd.GeoDataFrame | None":
    """Lê um shapefile compactado .zip que contém o Brasil inteiro.
    Espera campo de nome municipal 'NM_MUN'. Retorna GeoDataFrame."""
    if not GEO_OK:
        return None
    extract_dir = "shp_cache"
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)
    shp_file = None
    for root, _, files in os.walk(extract_dir):
        for f in files:
            if f.lower().endswith(".shp"):
                shp_file = os.path.join(root, f)
                break
        if shp_file: break
    if shp_file is None:
        raise FileNotFoundError("Shapefile (.shp) não encontrado dentro do ZIP.")
    gdf = gpd.read_file(shp_file)
    if "NM_MUN" not in gdf.columns:
        raise ValueError("Campo 'NM_MUN' não encontrado no shapefile.")
    # normaliza chave de join
    gdf["mun_norm"] = gdf["NM_MUN"].apply(normalize_name)
    # simplificação leve para performance de web (opcional)
    try:
        gdf = gdf.to_crs(3857)
        gdf["geometry"] = gdf.geometry.simplify(tolerance=200, preserve_topology=True)
        gdf = gdf.to_crs(4326)
    except Exception:
        pass
    return gdf

def fmt_num(x: t.Any) -> str:
    try:
        return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"

def export_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="ranking")
    buf.seek(0)
    return buf.read()

# ---------------------------
# Sidebar (Upload + Controles)
# ---------------------------
with st.sidebar:
    st.header("⚙️ Controles")

    # Upload opcional de novo Excel
    up = st.file_uploader("Enviar novo dados.xlsx", type=["xlsx"], help="Substituir dados temporariamente para esta sessão.")
    if up is not None:
        df = pd.read_excel(up)
        # normaliza colunas
        rename = {}
        for c in df.columns:
            lc = c.strip().lower()
            if lc in ["municipio", "município", "nm_mun", "city", "nome_municipio"]:
                rename[c] = "municipio"
            elif lc in ["variavel", "variável", "variable", "indicador"]:
                rename[c] = "variavel"
            elif lc in ["valor", "value", "media", "média"]:
                rename[c] = "valor"
        if rename:
            df = df.rename(columns=rename)
        for col in ["municipio", "variavel", "valor"]:
            if col not in df.columns:
                st.error(f"Coluna obrigatória ausente no arquivo enviado: {col}")
                st.stop()
        df["municipio"] = df["municipio"].astype(str).str.strip()
        df["variavel"] = df["variavel"].astype(str).str.strip()
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna(subset=["valor"])
    else:
        df = load_excel_default("dados.xlsx")

    # Sem variável pré-selecionada
    variaveis = sorted(df["variavel"].unique())
    variavel = st.selectbox("Selecione a variável", options=["— Selecione —"] + variaveis, index=0)

    # Top N para destaque
    top_n = st.slider("Top N (destaque)", min_value=3, max_value=30, value=5, step=1)

    show_map = st.checkbox("Exibir mapa temático", value=True)
    st.caption("O mapa usa seu shapefile (municipios.zip) e join pelo campo NM_MUN.")

# Se não selecionou variável ainda, mostra instruções e sai
if variavel == "— Selecione —":
    st.info("Selecione uma **variável** na barra lateral para ver o ranking, gráficos e mapa.")
    st.stop()

# ---------------------------
# Filtro principal e ranking
# ---------------------------
res = (
    df[df["variavel"] == variavel]
    .copy()
    .sort_values("valor", ascending=False)
    .reset_index(drop=True)
)
res["mun_norm"] = res["municipio"].apply(normalize_name)

# KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Máximo", fmt_num(res["valor"].max()))
c2.metric("Mínimo", fmt_num(res["valor"].min()))
c3.metric("Média", fmt_num(res["valor"].mean()))
c4.metric("Mediana", fmt_num(res["valor"].median()))

# Tabela ranking
st.markdown("### 🏆 Ranking dos Municípios")
st.dataframe(res[["municipio", "valor"]], use_container_width=True, hide_index=True)

# ---------------------------
# Gráfico horizontal (Top N)
# ---------------------------
st.markdown("### 📈 Gráfico de Barras (Top N)")
top_view = res.head(top_n)
fig, ax = plt.subplots(figsize=(9, 6))
ax.barh(top_view["municipio"], top_view["valor"])
ax.invert_yaxis()
ax.set_xlabel("Valor")
ax.set_ylabel("Município")
ax.set_title(variavel)
st.pyplot(fig)

# ---------------------------
# Mapa temático (Folium) — contínuo + highlight Top N
# ---------------------------
if show_map:
    if not GEO_OK:
        st.info("Para exibir o mapa no deploy/local, instale dependências geoespaciais (geopandas, folium, streamlit-folium).")
    else:
        st.markdown("### 🗺️ Mapa Temático (contínuo, join por NM_MUN)")
        try:
            gdf = load_shapefile_zip("municipios.zip")
        except Exception as e:
            st.error(f"Erro ao carregar o shapefile: {e}")
            gdf = None

        if gdf is not None and len(gdf) > 0:
            # merge por mun_norm
            gdfm = gdf.merge(res[["mun_norm", "valor"]], on="mun_norm", how="left")

            # Centro aproximado do Brasil
            m = folium.Map(location=[-14.2350, -51.9253], zoom_start=4, tiles="cartodb dark_matter")

            # Choropleth contínuo
            folium.Choropleth(
                geo_data=gdfm.to_json(),
                data=gdfm,
                columns=["mun_norm", "valor"],
                key_on="feature.properties.mun_norm",
                fill_opacity=0.85,
                line_opacity=0.2,
                legend_name=f"Valor — {variavel}",
            ).add_to(m)

            # Tooltip
            folium.GeoJson(
                gdfm,
                name="Municípios",
                style_function=lambda x: {"fillOpacity": 0, "color": "transparent", "weight": 0},
                tooltip=folium.GeoJsonTooltip(
                    fields=["NM_MUN", "valor"],
                    aliases=["Município", "Valor"],
                    localize=True,
                    labels=True,
                ),
                highlight_function=lambda x: {"weight": 2, "color": "#ffffff"},
            ).add_to(m)

            # Destaque Top N (borda)
            tops = set(top_view["mun_norm"])
            folium.GeoJson(
                gdfm[gdfm["mun_norm"].isin(tops)],
                name=f"Top {top_n}",
                style_function=lambda x: {"color": "#ffcc00", "weight": 3, "fillOpacity": 0},
                tooltip=folium.GeoJsonTooltip(fields=["NM_MUN", "valor"], aliases=["Município", "Valor"]),
            ).add_to(m)

            folium.LayerControl(collapsed=False).add_to(m)

            st_folium(m, width=None, height=560)

        else:
            st.warning("Shapefile vazio ou não carregado.")

# ---------------------------
# Downloads
# ---------------------------
st.markdown("### ⬇️ Downloads")
csv_bytes = res[["municipio", "variavel", "valor"]].to_csv(index=False).encode("utf-8")
st.download_button(
    "Baixar CSV (variável filtrada)",
    data=csv_bytes,
    file_name=f"ranking_{variavel}.csv",
    mime="text/csv"
)

excel_bytes = export_excel_bytes(res[["municipio", "variavel", "valor"]])
st.download_button(
    "Baixar Excel (variável filtrada)",
    data=excel_bytes,
    file_name=f"ranking_{variavel}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
