"""
Camada de acesso ao Supabase usada pelo pipeline de precificação, pelo
geocode_cep.py e pelo dashboard.

Tabelas esperadas (ajuste os nomes/colunas conforme seu schema real):

  imoveis_raw
    id (pk), preco, condominio, iptu, bairro, cidade, estado, cep,
    metragem, quartos, banheiros, vagas,
    caracteristicas_imovel (text/json), caracteristicas_condominio (text/json),
    checked (bool, default false)   <- vira TRUE depois que o preço é previsto/comparado

  precos_previstos
    imovel_id (fk -> imoveis_raw.id, idealmente UNIQUE para o upsert funcionar),
    preco_real, preco_previsto, diferenca, status, criado_em (default now())

  cep_coordenadas
    cep (pk), latitude, longitude, endereco

SQL de referência para criar o que ainda não existir:

  alter table imoveis_raw add column if not exists checked boolean default false;

  create table if not exists precos_previstos (
      imovel_id   bigint primary key references imoveis_raw(id),
      preco_real      numeric,
      preco_previsto  numeric,
      diferenca       numeric,
      status          text,
      criado_em       timestamptz default now()
  );

  create table if not exists cep_coordenadas (
      cep       text primary key,
      latitude  double precision,
      longitude double precision,
      endereco  text
  );
"""
import os

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Credenciais do Supabase não encontradas no arquivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ----------------------------------------------------------------------
# Imóveis / precificação
# ----------------------------------------------------------------------
def fetch_imoveis_pendentes() -> list:
    """Imóveis que já têm preço real (raspado da OLX) mas ainda não tiveram
    o preço de mercado previsto/comparado (checked = false)."""
    print("[DB] Buscando imóveis pendentes de precificação...")
    try:
        resp = supabase.table("imoveis_raw").select("*").is_("checked", "FALSE").execute()
        dados = resp.data
        print(f"[DB] {len(dados)} imóveis encontrados.")
        return dados
    except Exception as e:
        print(f"[DB] Erro ao buscar imóveis pendentes: {e}")
        return []


def salvar_comparacao_preco(imovel_id, preco_real, preco_previsto, diferenca, status):
    """Salva a comparação (preço real x previsto) e marca o imóvel como
    processado (checked = true)."""
    try:
        registro = {
            "imovel_id": imovel_id,
            "preco_real": float(round(float(preco_real), 2)),
            "preco_previsto": int(round(float(preco_previsto))),
            "diferenca": float(round(float(diferenca), 2)),
            "status": status,
        }
        supabase.table("precos_previstos").upsert(registro, on_conflict="imovel_id").execute()
        supabase.table("imoveis_raw").update({"checked": True}).eq("id", imovel_id).execute()
        print(f"[DB] OK: imóvel {imovel_id} -> previsto R$ {registro['preco_previsto']:,} ({status})")
    except Exception as e:
        print(f"[DB] Erro ao salvar comparação do imóvel {imovel_id}: {e}")


# ----------------------------------------------------------------------
# Geocodificação de CEPs
# ----------------------------------------------------------------------
def fetch_ceps_unicos() -> list:
    """Todos os CEPs distintos presentes em imoveis_raw."""
    try:
        resp = supabase.table("imoveis_raw").select("cep").execute()
        return sorted({row["cep"] for row in resp.data if row.get("cep")})
    except Exception as e:
        print(f"[DB] Erro ao buscar CEPs: {e}")
        return []


def fetch_ceps_ja_geocodificados() -> set:
    try:
        resp = supabase.table("cep_coordenadas").select("cep").execute()
        return {row["cep"] for row in resp.data}
    except Exception as e:
        print(f"[DB] Erro ao buscar CEPs já geocodificados: {e}")
        return set()


def salvar_cep_coordenadas(cep, latitude, longitude, endereco):
    try:
        supabase.table("cep_coordenadas").upsert({
            "cep": cep,
            "latitude": latitude,
            "longitude": longitude,
            "endereco": endereco,
        }, on_conflict="cep").execute()
    except Exception as e:
        print(f"[DB] Erro ao salvar coordenadas do CEP {cep}: {e}")


# ----------------------------------------------------------------------
# Dados consolidados para o dashboard
# ----------------------------------------------------------------------
def fetch_dados_dashboard() -> pd.DataFrame:
    """Junta imoveis_raw + precos_previstos + cep_coordenadas em um único
    DataFrame, pronto para os gráficos e o mapa do dashboard."""
    imoveis = pd.DataFrame(supabase.table("imoveis_raw").select("*").execute().data)
    previstos = pd.DataFrame(supabase.table("precos_previstos").select("*").execute().data)
    coords = pd.DataFrame(supabase.table("cep_coordenadas").select("*").execute().data)

    if imoveis.empty or previstos.empty:
        return pd.DataFrame()

    df = imoveis.merge(previstos, left_on="id", right_on="imovel_id", how="inner", suffixes=("", "_prev"))
    if not coords.empty:
        df = df.merge(coords, on="cep", how="left")
    return df