import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Credenciais do Supabase não encontradas no arquivo .env")

# Inicializa o cliente do Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_imoveis_sem_preco() -> list:
    """
    Busca na tabela 'imoveis_raw' todos os registros que não possuem o preço definido (checked = FALSE).
    """
    print("[DB] Buscando imóveis sem preço no Supabase...")
    try:
        response = supabase.table('imoveis_raw').select('*').is_('checked', 'FALSE').execute()
        
        dados = response.data
        print(f"[DB] {len(dados)} imóveis encontrados para predição.")
        return dados
    except Exception as e:
        print(f"[DB] Erro ao buscar imóveis: {e}")
        return []

def salvar_preco_previsto(imovel_uuid: str, preco_previsto):
    """
    Salva o preço previsto na tabela 'precos_previstos' e atualiza o status na 'imoveis_raw'.
    Converte o valor vindo do Machine Learning (NumPy Float) para um Inteiro Nativo do Python.
    """
    try:
        # A mágica da conversão à prova de falhas:
        # 1. float(): tira do formato do Numpy
        # 2. round(): aproxima para o valor mais justo
        # 3. int(): transforma em número inteiro puro para o banco de dados
        valor_inteiro = int(round(float(preco_previsto)))
        
        dados_insercao = {
            "imovel_id": imovel_uuid,
            "preco_previsto": valor_inteiro
        }
        
        # 1. Salva/Atualiza o preço previsto
        supabase.table('precos_previstos').upsert(dados_insercao).execute()
        print(f"[DB] Sucesso: Preço de R$ {valor_inteiro:,} salvo para UUID: {imovel_uuid}")
        
        # 2. Atualiza o status checked = True na tabela original
        # NOTA: Se a coluna primária na tabela 'imoveis_raw' não se chamar "id", mude no .eq() abaixo.
        supabase.table('imoveis_raw').update({
            "checked": True
        }).eq("id", imovel_uuid).execute()
        print(f"[DB] Sucesso: Imóvel {imovel_uuid} marcado como checked = True")
        
    except Exception as e:
        print(f"[DB] Erro ao processar o imóvel {imovel_uuid}: {e}")