import pandas as pd
import ast
import numpy as np

def limpar_dados_imoveis(caminho_arquivo):
    # Carregar o dataset original
    df = pd.read_csv(caminho_arquivo)

    # 1. Mapeamento das características do imóvel
    # Termos originais do CSV apontando APENAS para os 10 itens permitidos
    MAP_IMOVEL = {
        'GYM': 'Academia',
        'AIR_CONDITIONING': 'Ar condicionado',
        'KITCHEN_CABINETS': 'Armários na cozinha',
        'BUILTIN_WARDROBE': 'Armários no quarto',
        'CLOSET': 'Armários no quarto',
        'BARBECUE_GRILL': 'Churrasqueira',
        'FURNISHED': 'Mobiliado',
        'POOL': 'Piscina',
        'CONCIERGE_24H': 'Porteiro 24h',
        'BALCONY': 'Varanda',
        'GOURMET_BALCONY': 'Varanda',
        'BARBECUE_BALCONY': 'Varanda',
        'SERVICE_AREA': 'Área de serviço',
        'LAUNDRY': 'Área de serviço'
    }

    # 2. Mapeamento das características do condomínio
    # Termos originais do CSV apontando APENAS para os 9 itens permitidos
    MAP_CONDOMINIO = {
        'GYM': 'Academia',
        'GATED_COMMUNITY': 'Condomínio fechado',
        'ELEVATOR': 'Elevador',
        'PETS_ALLOWED': 'Permitido animais',
        'POOL': 'Piscina',
        'CONCIERGE_24H': 'Portaria',
        'ELECTRONIC_GATE': 'Portão eletrônico',
        'PARTY_HALL': 'Salão de festas',
        'SECURITY_24_HOURS': 'Segurança 24h',
        'SAFETY_CIRCUIT': 'Segurança 24h',
    }

    # Função auxiliar para ler as strings de lista do CSV e traduzir
    def parse_amenities(amenities_str, mapping):
        if pd.isna(amenities_str):
            return []
        try:
            # Converte a string "['ITEM1', 'ITEM2']" em uma lista real do Python
            amenities_list = ast.literal_eval(amenities_str)
            # Traduz os termos e ignora os que não estão no mapeamento
            mapped = [mapping[am] for am in amenities_list if am in mapping]
            # set() remove duplicatas caso dois itens em inglês mapeiem para o mesmo em português (ex: Balcony e Gourmet Balcony)
            return list(set(mapped)) 
        except:
            return []

    # Extraindo e filtrando as características
    caracteristicas_imovel = df['amenities'].apply(lambda x: parse_amenities(x, MAP_IMOVEL))
    caracteristicas_condominio = df['amenities'].apply(lambda x: parse_amenities(x, MAP_CONDOMINIO))

    # 3. Montando o novo DataFrame com o schema exigido
    df_clean = pd.DataFrame()
    
    # Valores numéricos 
    df_clean['preco'] = df['price'].astype(float)
    df_clean['condominio'] = df['monthlyCondoFee'].fillna(0.0).astype(float)
    df_clean['iptu'] = df['yearlyIptu'].fillna(0.0).astype(float)
    
    # Endereço
    df_clean['bairro'] = df['neighborhood'].where(pd.notnull(df['neighborhood']), None)
    df_clean['cidade'] = 'Curitiba' # A base é especificamente de Curitiba
    df_clean['estado'] = 'PR'
    # Trata o CEP para remover a terminação '.0' caso tenha sido lido como float
    df_clean['cep'] = df['zipCode'].astype(str).str.replace(r'\.0$', '', regex=True) 
    
    # Estrutura (Substitui valores vazios por 0 e converte para inteiro)
    df_clean['metragem'] = df['usableAreas'].fillna(0).astype(int)
    df_clean['quartos'] = df['bedrooms'].fillna(0).astype(int)
    df_clean['banheiros'] = df['bathrooms'].fillna(0).astype(int)
    df_clean['vagas'] = df['parkingSpaces'].fillna(0).astype(int)
    
    # Listas
    df_clean['caracteristicas_imovel'] = caracteristicas_imovel
    df_clean['caracteristicas_condominio'] = caracteristicas_condominio

    return df_clean

# Executando a limpeza
tabela_limpa = limpar_dados_imoveis('/home/JGMK/Documents/ImobTestes/ML_IMOB_CWB/curitiba_apartment_real_estate_data.csv')

# Exportando para testar
tabela_limpa.to_csv('imoveis_limpos.csv', index=False)
print("Sucesso! O arquivo 'imoveis_limpos.csv' foi gerado.")