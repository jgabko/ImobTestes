"""
Pipeline completo, do fim ao fim:

  1) Raspa os anúncios novos da OLX (scraper assíncrono, já valida/limpa via Pydantic)
  2) Salva os imóveis brutos no Supabase (tabela imoveis_raw)
  3) Geocodifica os CEPs novos que apareceram (para o mapa de calor)
  4) Roda o modelo de ML: prevê o preço de mercado de cada imóvel pendente,
     compara com o preço real anunciado e salva o resultado (acima/abaixo/dentro
     da faixa) no Supabase

Depois de rodar este arquivo, o dashboard (`streamlit run dashboard.py`) já
reflete os dados novos.

Posição esperada deste arquivo: raiz do projeto, com a seguinte estrutura:

  pipeline.py                      <- este arquivo
  Supabase_itens.py
  pipeline_precificacao.py
  feature_engineering.py
  geocode_cep.py
  dashboard.py
  melhor_modelo_precificacao.pkl   <- gerado por treinar_modelo.py
  colunas_modelo.pkl               <- gerado por treinar_modelo.py
  metricas_modelo.json             <- gerado por treinar_modelo.py
  Olx_scrape_async/
      scraping/
          olx_async.py
          supabase_db.py

Uso:
  python pipeline.py
"""
import asyncio
import sys
from pathlib import Path

# Garante que o pacote do scraper (Olx_scrape_async/scraping) seja encontrado
# não importa de onde este script seja executado.
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "Olx_scrape_async"))

from scraping.olx_async import rodar_scraper          # noqa: E402
from scraping.supabase_db import salvar_no_supabase   # noqa: E402

from geocode import main as geocodificar_ceps_pendentes              # noqa: E402
from pipeline_precificacao import executar_pipeline_de_precificacao      # noqa: E402


def _titulo(texto: str):
    print("\n" + "=" * 60)
    print(f" {texto}")
    print("=" * 60)


def executar_pipeline_completo():
    _titulo("INICIANDO PIPELINE COMPLETO - OLX -> SUPABASE -> ML -> DASHBOARD")

    # ------------------------------------------------------------
    # PASSO 1: Scraping
    # ------------------------------------------------------------
    print("\n>>> PASSO 1: Iniciando o Robô de Extração...")
    dados_extraidos = asyncio.run(rodar_scraper())

    # ------------------------------------------------------------
    # PASSO 2: Salvar os dados brutos no Supabase
    # ------------------------------------------------------------
    if dados_extraidos:
        print(f"\n>>> PASSO 2: Enviando {len(dados_extraidos)} imóveis para o Banco de Dados...")
        salvar_no_supabase(dados_extraidos, nome_tabela="imoveis_raw")
    else:
        print("\n>>> PASSO 2: ⚠️ A extração não retornou nenhum dado novo. Envio pulado.")

    # ------------------------------------------------------------
    # PASSO 3: Geocodificar CEPs novos (não bloqueia o pipeline se falhar)
    # ------------------------------------------------------------
    print("\n>>> PASSO 3: Geocodificando CEPs novos para o mapa de calor...")
    try:
        geocodificar_ceps_pendentes()
    except Exception as e:
        print(f"⚠️ Falha ao geocodificar CEPs (etapa não bloqueante, seguindo em frente): {e}")

    # ------------------------------------------------------------
    # PASSO 4: Prever preço de mercado e comparar com o preço real
    # ------------------------------------------------------------
    print("\n>>> PASSO 4: Calculando preço previsto e comparando com o preço real...")
    try:
        executar_pipeline_de_precificacao()
    except Exception as e:
        print(f"❌ Falha na etapa de precificação: {e}")

    _titulo("PIPELINE COMPLETO FINALIZADO COM SUCESSO!")
    print("Dashboard pronto para refletir os novos dados: streamlit run dashboard.py\n")


if __name__ == "__main__":
    executar_pipeline_completo()