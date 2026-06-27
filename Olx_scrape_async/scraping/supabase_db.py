import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def get_supabase_client() -> Client:
    """
    Inicializa e retorna o cliente do Supabase.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("As credenciais do Supabase não foram encontradas. Verifique o seu arquivo .env.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def salvar_no_supabase(dados: list[dict], nome_tabela: str = "imoveis_raw"):
    """
    Recebe uma lista de dicionários e realiza um UPSERT na tabela do Supabase.
    Ignora registros que já possuam a mesma URL cadastrada (evita duplicatas).
    """
    if not dados:
        print("Aviso: Nenhum dado disponível para enviar ao Supabase.")
        return None

    supabase = get_supabase_client()
    
    try:
        print(f"\n[BANCO DE DADOS] Tentando inserir {len(dados)} imóveis na tabela '{nome_tabela}'...")
        
        # O método UPSERT verifica a coluna 'url'. 
        # Se a url já existir, 'ignore_duplicates=True' faz ele pular e não dar erro.
        resposta = supabase.table(nome_tabela).upsert(
            dados, 
            on_conflict="url", 
            ignore_duplicates=True
        ).execute()
        
        print(f"✅ Processamento concluído! Registros novos salvos no banco. (Duplicatas ignoradas).")
        return resposta.data
        
    except Exception as e:
        print(f"❌ Erro ao inserir dados no Supabase: {e}")
        return None