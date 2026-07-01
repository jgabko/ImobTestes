import pandas as pd
import joblib
import ast
import re
from Supabase_itens import fetch_imoveis_sem_preco, salvar_preco_previsto

def converter_para_lista(texto):
    """Converte strings do DB para listas Python, retornando lista vazia se falhar."""
    try:
        return ast.literal_eval(texto) if pd.notna(texto) else []
    except:
        return []

def preparar_dados_para_modelo(df, modelo):
    """Reconstrói colunas binárias e alinha o dataframe para o formato exato do modelo."""
    
    # 1. Converte as colunas de texto para listas
    for col in ['caracteristicas_imovel', 'caracteristicas_condominio']:
        df[col] = df.get(col, '').apply(converter_para_lista)

    # 2. Extrai as features binárias usando list comprehension (mais rápido que iterrows)
    def extrair_features(row):
        feats = {re.sub(r'[\[\]<>{}]', '', f"imovel_{f.lower().replace(' ', '_')}"): 1 for f in row['caracteristicas_imovel']}
        feats.update({re.sub(r'[\[\]<>{}]', '', f"condo_{f.lower().replace(' ', '_')}"): 1 for f in row['caracteristicas_condominio']})
        return feats

    # 3. Junta tudo em um DataFrame
    df_extras = pd.DataFrame(df.apply(extrair_features, axis=1).tolist())
    df_completo = pd.concat([df.reset_index(drop=True), df_extras], axis=1)
    
    # 4. A Mágica do Pandas: reindex cria colunas faltantes com 0 e remove as que sobram de uma vez só!
    return df_completo.reindex(columns=modelo.feature_names_in_, fill_value=0)

def executar_pipeline_de_precificacao():
    print("=== Iniciando Pipeline de Precificação ===")
    
    try:
        modelo_rf = joblib.load('/home/JGMK/Documents/ImobTestes/rf_modelo_definitivo.pkl')
    except Exception as e:
        return print(f"[Erro] Falha ao carregar o modelo: {e}")

    dados_imoveis = fetch_imoveis_sem_preco()
    if not dados_imoveis:
        return print("[Status] Nenhum imóvel pendente. Encerrando.")
        
    df_imoveis = pd.DataFrame(dados_imoveis)
    X_pred = preparar_dados_para_modelo(df_imoveis, modelo_rf)
    
    print("[ML] Realizando predições...")
    previsoes = modelo_rf.predict(X_pred)
    
    print("=== Salvando Resultados no Banco ===")
    col_id = 'id' if 'id' in df_imoveis.columns else 'uuid'
    
    # Usando zip para iterar id e preco simultaneamente (muito mais limpo e rápido)
    for imovel_uuid, preco_calculado in zip(df_imoveis[col_id], previsoes):
        salvar_preco_previsto(imovel_uuid, preco_calculado)
        
    print("=== Processo Finalizado com Sucesso ===")

if __name__ == "__main__":
    executar_pipeline_de_precificacao()