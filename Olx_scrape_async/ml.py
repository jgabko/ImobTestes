"""
Treina três modelos (Random Forest, XGBoost, LightGBM), compara o desempenho
no conjunto de teste e salva o melhor como `melhor_modelo_precificacao.pkl`.

Esse .pkl é o arquivo consumido depois pelo `pipeline_precificacao.py` para
prever o preço de mercado dos imóveis raspados da OLX.

Saídas:
  - melhor_modelo_precificacao.pkl  -> pipeline treinado (pré-processador + regressor)
  - colunas_modelo.pkl              -> lista de colunas (features) esperadas pelo modelo
  - metricas_modelo.json            -> métricas de todos os modelos + margem de erro usada

Uso:
  python treinar_modelo.py
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

from feature_engineering import (
    FEATURES_CATEGORICAS,
    FEATURES_NUMERICAS,
    montar_features_binarias,
)

BASE_DIR = Path(__file__).resolve().parent
CAMINHO_CSV = "/home/JGMK/Documents/ImobTestes/ML_IMOB_CWB/imoveis_limpos.csv"
ARQUIVO_MODELO = BASE_DIR / "melhor_modelo_precificacao.pkl"
ARQUIVO_COLUNAS = BASE_DIR / "colunas_modelo.pkl"
ARQUIVO_METRICAS = BASE_DIR / "metricas_modelo.json"
MARGEM_ERRO = 90_000  # taxa de erro do modelo, em R$, usada depois para classificar acima/abaixo


def main():
    print("Carregando os dados...")
    df = pd.read_csv(CAMINHO_CSV)

    # ------------------------------------------------------------------
    # 1) Remoção de outliers extremos (preço e metragem) só para o treino
    # ------------------------------------------------------------------
    print("Removendo outliers extremos...")
    q1_preco, q3_preco = df["preco"].quantile(0.25), df["preco"].quantile(0.75)
    iqr_preco = q3_preco - q1_preco
    limite_sup_preco = q3_preco + 1.5 * iqr_preco
    limite_inf_preco = max(0, q1_preco - 1.5 * iqr_preco)

    q1_m, q3_m = df["metragem"].quantile(0.25), df["metragem"].quantile(0.75)
    iqr_m = q3_m - q1_m
    limite_sup_m = q3_m + 1.5 * iqr_m
    limite_inf_m = max(10, q1_m - 1.5 * iqr_m)

    df_filtrado = df[
        (df["preco"] >= limite_inf_preco) & (df["preco"] <= limite_sup_preco) &
        (df["metragem"] >= limite_inf_m) & (df["metragem"] <= limite_sup_m)
    ].copy()
    print(f"-> {df.shape[0] - df_filtrado.shape[0]} registros excluídos por serem outliers.")

    # ------------------------------------------------------------------
    # 2) Engenharia de features (módulo compartilhado com a inferência)
    # ------------------------------------------------------------------
    print("Processando características (one-hot multi-label)...")
    df_final = montar_features_binarias(df_filtrado)
    features_binarias = [c for c in df_final.columns if c.startswith("imovel_") or c.startswith("condo_")]
    colunas_modelo = FEATURES_NUMERICAS + FEATURES_CATEGORICAS + features_binarias

    # Preço NUNCA entra como feature (X): ele é o alvo (y) que queremos prever.
    # CEP também não entra como feature do modelo: só é usado depois, no
    # dashboard, para posicionar o imóvel no mapa.
    X = df_final[colunas_modelo]
    y = df_final["preco"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), FEATURES_NUMERICAS),
            ("cat", OneHotEncoder(handle_unknown="ignore"), FEATURES_CATEGORICAS),
        ],
        remainder="passthrough",
    )

    # ------------------------------------------------------------------
    # 3) Competição de modelos
    # ------------------------------------------------------------------
    modelos = {
        "Random Forest": RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1),
        "XGBoost": XGBRegressor(n_estimators=300, learning_rate=0.1, random_state=42, n_jobs=-1),
        "LightGBM": LGBMRegressor(n_estimators=300, learning_rate=0.1, random_state=42, n_jobs=-1, verbose=-1),
    }

    resultados = {}
    melhor_nome, melhor_r2, melhor_pipeline = None, -float("inf"), None

    print("\n=== INICIANDO TREINAMENTO E COMPARAÇÃO ===")
    for nome, algoritmo in modelos.items():
        print(f"Treinando {nome}...")
        pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("regressor", algoritmo)])
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)

        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        resultados[nome] = {"r2": r2, "mae": mae, "rmse": rmse}

        if r2 > melhor_r2:
            melhor_r2, melhor_nome, melhor_pipeline = r2, nome, pipeline

    print("\n=== PLACAR FINAL ===")
    for nome, m in resultados.items():
        print(f"{nome}: R²={m['r2']:.4f}  MAE=R$ {m['mae']:,.2f}  RMSE=R$ {m['rmse']:,.2f}")
    print(f"\n🏆 Vencedor: {melhor_nome} (R²={melhor_r2:.4f})")

    # ------------------------------------------------------------------
    # 4) Salvando o melhor modelo + metadados
    # ------------------------------------------------------------------
    joblib.dump(melhor_pipeline, ARQUIVO_MODELO)
    joblib.dump(colunas_modelo, ARQUIVO_COLUNAS)

    with open(ARQUIVO_METRICAS, "w", encoding="utf-8") as f:
        json.dump({
            "melhor_modelo": melhor_nome,
            "margem_erro": MARGEM_ERRO,
            "resultados_todos_modelos": resultados,
        }, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Modelo salvo em '{ARQUIVO_MODELO}'.")
    print("✅ Colunas do modelo salvas em 'colunas_modelo.pkl'.")
    print("✅ Métricas salvas em 'metricas_modelo.json'.")


if __name__ == "__main__":
    main()