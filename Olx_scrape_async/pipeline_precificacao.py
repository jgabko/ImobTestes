"""
Pipeline de precificação: para cada imóvel raspado da OLX que ainda não foi
processado (checked = false), prevê o preço de mercado com o modelo treinado,
compara com o preço real anunciado e salva o resultado no Supabase.

Pré-requisito: rodar `treinar_modelo.py` antes, para gerar
`melhor_modelo_precificacao.pkl`, `colunas_modelo.pkl` e `metricas_modelo.json`.

Uso:
  python pipeline_precificacao.py
"""
import json
from pathlib import Path

import joblib
import pandas as pd

from feature_engineering import preparar_X
from supabase_f import fetch_imoveis_pendentes, salvar_comparacao_preco

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_MODELO = BASE_DIR / "melhor_modelo_precificacao.pkl"
ARQUIVO_COLUNAS = BASE_DIR / "colunas_modelo.pkl"
ARQUIVO_METRICAS = BASE_DIR / "metricas_modelo.json"
MARGEM_ERRO_PADRAO = 90_000


def carregar_margem_erro() -> float:
    try:
        with open(ARQUIVO_METRICAS, "r", encoding="utf-8") as f:
            return json.load(f).get("margem_erro", MARGEM_ERRO_PADRAO)
    except FileNotFoundError:
        return MARGEM_ERRO_PADRAO


def classificar(diferenca, margem_erro):
    if diferenca > margem_erro:
        return "Acima do mercado"
    if diferenca < -margem_erro:
        return "Abaixo do mercado"
    return "Dentro da faixa esperada"


def executar_pipeline_de_precificacao():
    print("=== Iniciando Pipeline de Precificação ===")

    try:
        modelo = joblib.load(ARQUIVO_MODELO)
        colunas_modelo = joblib.load(ARQUIVO_COLUNAS)
    except FileNotFoundError as e:
        print(f"[Erro] Arquivo do modelo não encontrado: {e}")
        print(f"        Rode 'python treinar_modelo.py' (esperado em: {BASE_DIR}) para gerá-lo.")
        return
    except Exception as e:
        return print(f"[Erro] Falha ao carregar o modelo/colunas: {e}")

    margem_erro = carregar_margem_erro()
    print(f"[Config] Margem de erro do modelo: R$ {margem_erro:,.0f}")

    dados_imoveis = fetch_imoveis_pendentes()
    if not dados_imoveis:
        return print("[Status] Nenhum imóvel pendente. Encerrando.")

    df_imoveis = pd.DataFrame(dados_imoveis)
    col_id = "id" if "id" in df_imoveis.columns else "uuid"

    print("[ML] Montando features e realizando predições...")
    X_pred = preparar_X(df_imoveis, colunas_modelo=colunas_modelo)
    previsoes = modelo.predict(X_pred)

    print("=== Comparando preço real x previsto e salvando no banco ===")
    for imovel_id, preco_real, preco_previsto in zip(df_imoveis[col_id], df_imoveis["preco"], previsoes):
        diferenca = float(preco_real) - float(preco_previsto)
        status = classificar(diferenca, margem_erro)
        salvar_comparacao_preco(imovel_id, preco_real, preco_previsto, diferenca, status)

    print("=== Processo Finalizado com Sucesso ===")


if __name__ == "__main__":
    executar_pipeline_de_precificacao()