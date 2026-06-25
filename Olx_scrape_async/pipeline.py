import asyncio
from scraping.olx_async import rodar_scraper
from scraping.supabase_db import salvar_no_supabase

def executar_pipeline_completo():
    print("="*50)
    print(" INICIANDO PIPELINE DE DADOS - OLX -> SUPABASE ")
    print("="*50)

    # Passo 1: Executa o Scraper (que já faz a limpeza/validação via Pydantic)
    print("\n>>> PASSO 1: Iniciando o Robô de Extração...")
    
    # Roda a função assíncrona do scraper e aguarda o resultado
    dados_extraidos = asyncio.run(rodar_scraper())

    # Passo 2: Salvar os dados no Supabase
    print("\n>>> PASSO 2: Iniciando o envio para o Banco de Dados...")
    
    if dados_extraidos:
        # Passa os dados limpos diretamente para a função do banco
        salvar_no_supabase(dados_extraidos, nome_tabela="imoveis")
    else:
        print("⚠️ A extração não retornou nenhum dado válido. O envio foi cancelado.")

    print("\n" + "="*50)
    print(" PIPELINE FINALIZADO COM SUCESSO! ")
    print("="*50)

if __name__ == "__main__":
    executar_pipeline_completo()