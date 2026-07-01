"""
Lógica de engenharia de features compartilhada entre o treino (treinar_modelo.py)
e a inferência (pipeline_precificacao.py).

É CRÍTICO que treino e inferência gerem as colunas binárias (características do
imóvel/condomínio) exatamente da mesma forma — por isso essa lógica vive em um
único lugar e é importada nos dois scripts, em vez de duplicada.
"""
import ast
import re

import pandas as pd

FEATURES_NUMERICAS = ["condominio", "iptu", "metragem", "quartos", "banheiros", "vagas"]
FEATURES_CATEGORICAS = ["bairro"]


def converter_para_lista(texto):
    """Converte a representação em string de uma lista (vinda do CSV ou do
    Supabase, que pode devolver a coluna já como list/JSON) para uma lista
    Python de verdade. Retorna [] se falhar."""
    if isinstance(texto, list):
        return texto
    if texto is None:
        return []
    if isinstance(texto, float) and pd.isna(texto):
        return []
    if not isinstance(texto, str):
        return []
    try:
        return ast.literal_eval(texto)
    except (ValueError, SyntaxError):
        return []


def sanitizar_nome_coluna(nome: str) -> str:
    """XGBoost/LightGBM não aceitam [ ] < > { } em nomes de coluna."""
    return re.sub(r"[\[\]<>{}]", "", str(nome))


def montar_features_binarias(df: pd.DataFrame) -> pd.DataFrame:
    """A partir das colunas de texto 'caracteristicas_imovel' e
    'caracteristicas_condominio', gera uma coluna binária (0/1) para cada
    característica encontrada. Funciona tanto para um DataFrame grande
    (treino) quanto para poucas linhas vindas do Supabase (inferência)."""
    df = df.copy()
    for col in ("caracteristicas_imovel", "caracteristicas_condominio"):
        if col not in df.columns:
            df[col] = [[] for _ in range(len(df))]
        else:
            df[col] = df[col].apply(converter_para_lista)

    def extrair(row):
        feats = {
            sanitizar_nome_coluna(f"imovel_{f.lower().replace(' ', '_')}"): 1
            for f in row["caracteristicas_imovel"]
        }
        feats.update({
            sanitizar_nome_coluna(f"condo_{f.lower().replace(' ', '_')}"): 1
            for f in row["caracteristicas_condominio"]
        })
        return feats

    registros = df.apply(extrair, axis=1).tolist()
    extras = pd.DataFrame(registros, index=df.index)
    if not extras.empty:
        extras = extras.fillna(0).astype(int)

    return pd.concat([df, extras], axis=1)


def preparar_X(df: pd.DataFrame, colunas_modelo=None) -> pd.DataFrame:
    """Monta o DataFrame final de features (X), pronto para .predict()/.fit().

    Se `colunas_modelo` for passado (lista de colunas vista no treino), o
    resultado é alinhado a ela via reindex: colunas que faltarem são criadas
    com 0, colunas extras (características nunca vistas no treino) são
    descartadas. Isso é o que torna a inferência segura mesmo quando aparecem
    características novas nos imóveis raspados.
    """
    df_completo = montar_features_binarias(df)
    binarias = [c for c in df_completo.columns if c.startswith("imovel_") or c.startswith("condo_")]

    if colunas_modelo is not None:
        return df_completo.reindex(columns=list(colunas_modelo), fill_value=0)

    return df_completo[FEATURES_NUMERICAS + FEATURES_CATEGORICAS + binarias]