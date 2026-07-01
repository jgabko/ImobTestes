"""
Dashboard de análise de preços de imóveis em Curitiba — agora lendo os dados
direto do Supabase (imoveis_raw + precos_previstos + cep_coordenadas), em vez
de arquivos CSV locais.

Pré-requisitos:
  - treinar_modelo.py        já rodado (gera o .pkl)
  - pipeline_precificacao.py já rodado (popula precos_previstos)
  - geocode_cep.py           já rodado (popula cep_coordenadas)

Rodar com:
  streamlit run dashboard.py
"""
import json
from pathlib import Path

import plotly.express as px
import streamlit as st

from supabase_f import fetch_dados_dashboard

st.set_page_config(page_title="Imóveis Curitiba - Preço de Mercado", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
try:
    with open(BASE_DIR / "metricas_modelo.json", "r", encoding="utf-8") as f:
        MARGEM_ERRO = json.load(f).get("margem_erro", 90_000)
except FileNotFoundError:
    MARGEM_ERRO = 90_000

CORES_STATUS = {
    "Acima do mercado": "#E74C3C",
    "Abaixo do mercado": "#27AE60",
    "Dentro da faixa esperada": "#95A5A6",
}


@st.cache_data(ttl=600)
def carregar_dados():
    return fetch_dados_dashboard()


df = carregar_dados()

st.title("🏠 Imóveis em Curitiba: Preço Real x Preço de Mercado")
st.caption(
    f"O modelo de Machine Learning prevê um preço de mercado para cada imóvel. "
    f"Considerando a margem de erro do modelo (± R$ {MARGEM_ERRO:,.0f}), cada imóvel é "
    f"classificado como abaixo, dentro ou acima do preço esperado."
)

if df.empty:
    st.warning("Nenhum dado encontrado. Rode `pipeline_precificacao.py` para popular o banco.")
    st.stop()

# ----------------------------------------------------------------------
# Filtros
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")
    if st.button("🔄 Recarregar dados do Supabase"):
        st.cache_data.clear()
        st.rerun()

    bairros = sorted(df["bairro"].dropna().unique())
    bairros_sel = st.multiselect("Bairro", bairros, default=[])
    if bairros_sel:
        df = df[df["bairro"].isin(bairros_sel)]

    faixa_preco = st.slider(
        "Faixa de preço (R$)",
        min_value=int(df["preco_real"].min()),
        max_value=int(df["preco_real"].max()),
        value=(int(df["preco_real"].min()), int(df["preco_real"].max())),
        step=10_000,
    )
    df = df[(df["preco_real"] >= faixa_preco[0]) & (df["preco_real"] <= faixa_preco[1])]

# ----------------------------------------------------------------------
# KPIs
# ----------------------------------------------------------------------
contagem = df["status"].value_counts()
total = len(df)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de imóveis", f"{total:,}")
col2.metric("🔴 Acima do mercado", f"{contagem.get('Acima do mercado', 0):,}")
col3.metric("🟢 Abaixo do mercado", f"{contagem.get('Abaixo do mercado', 0):,}")
col4.metric("⚪ Dentro da faixa", f"{contagem.get('Dentro da faixa esperada', 0):,}")

st.divider()

# ----------------------------------------------------------------------
# Distribuição da diferença (real - previsto)
# ----------------------------------------------------------------------
st.subheader("Distribuição: Preço Real − Preço Previsto")
fig_hist = px.histogram(
    df, x="diferenca", color="status", nbins=60,
    color_discrete_map=CORES_STATUS,
    labels={"diferenca": "Diferença (R$)"},
)
fig_hist.add_vline(x=MARGEM_ERRO, line_dash="dash", line_color="gray")
fig_hist.add_vline(x=-MARGEM_ERRO, line_dash="dash", line_color="gray")
st.plotly_chart(fig_hist, width="stretch")

st.divider()

# ----------------------------------------------------------------------
# Mapas
# ----------------------------------------------------------------------
df_mapa = df.dropna(subset=["latitude", "longitude"])
sem_coordenadas = total - len(df_mapa)
if sem_coordenadas:
    st.warning(
        f"{sem_coordenadas} imóveis não puderam ser plotados no mapa "
        f"(CEP sem coordenadas — rode geocode_cep.py novamente para completar)."
    )

aba_calor, aba_pontos = st.tabs(["🔥 Mapa de calor (densidade de imóveis)", "📍 Mapa por status"])

with aba_calor:
    fig_calor = px.density_mapbox(
        df_mapa, lat="latitude", lon="longitude", z="preco_real",
        radius=18, center={"lat": -25.4284, "lon": -49.2733}, zoom=10.5,
        mapbox_style="open-street-map",
        color_continuous_scale="YlOrRd",
        labels={"preco_real": "Preço (R$)"},
    )
    fig_calor.update_layout(height=650, margin={"r": 0, "t": 0, "l": 0, "b": 0})
    st.plotly_chart(fig_calor, width="stretch")

with aba_pontos:
    fig_pontos = px.scatter_mapbox(
        df_mapa, lat="latitude", lon="longitude", color="status",
        color_discrete_map=CORES_STATUS,
        center={"lat": -25.4284, "lon": -49.2733}, zoom=10.5,
        mapbox_style="open-street-map",
        hover_data={"bairro": True, "preco_real": ":,.0f", "preco_previsto": ":,.0f", "latitude": False, "longitude": False},
    )
    fig_pontos.update_layout(height=650, margin={"r": 0, "t": 0, "l": 0, "b": 0})
    st.plotly_chart(fig_pontos, width="stretch")