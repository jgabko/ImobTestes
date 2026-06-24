import json
import re
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator

# --- Funções Auxiliares de Limpeza ---

def limpar_moeda(valor: Optional[str]) -> float:
    if not valor:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).replace("R$", "").replace("/mês", "").replace(".", "").strip()
    texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0

def extrair_inteiro(valor: Optional[str]) -> int:
    if valor is None:
        return 0
    if isinstance(valor, int):
        return valor
    busca = re.search(r'\d+', str(valor))
    if busca:
        return int(busca.group())
    return 0


# --- Modelo Pydantic com Filtro Nativo de Cidade ---

class ImovelCuritibaSchema(BaseModel):
    titulo: str
    preco: float
    condominio: float
    iptu: float
    bairro: Optional[str] = None
    cidade: str
    estado: str
    cep: str
    metragem: int
    quartos: int
    banheiros: int
    vagas: int
    caracteristicas_imovel: List[str] = Field(default_factory=list)
    caracteristicas_condominio: List[str] = Field(default_factory=list)
    descricao: str
    url: str

    # 1. O Filtro de Cidade roda ANTES de tudo
    @model_validator(mode="before")
    @classmethod
    def filtrar_apenas_curitiba(cls, data: Any) -> Any:
        if isinstance(data, dict):
            cidade = data.get("cidade")
            # Se a cidade não for Curitiba (ignorando maiúsculas/minúsculas), levanta um erro
            if not cidade or str(cidade).strip().lower() != "curitiba":
                raise ValueError("Ignorado: Imóvel fora da região de Curitiba.")
        return data

    # 2. Validadores de campo rodam se a cidade for aceita
    @field_validator("preco", "condominio", "iptu", mode="before")
    @classmethod
    def validar_e_limpar_moedas(cls, v):
        return limpar_moeda(v)

    @field_validator("metragem", "quartos", "banheiros", "vagas", mode="before")
    @classmethod
    def validar_e_limpar_numeros(cls, v):
        return extrair_inteiro(v)

    @field_validator("bairro", mode="before")
    @classmethod
    def tratar_bairro_nulo(cls, v):
        return v if v else "Não Informado"


# --- Script de Execução (Pipeline) ---

def limpar_dados_json():
    arquivo_entrada = "imoveis_sucesso.json" # O arquivo que seu scraper gerou
    arquivo_saida = "imoveis_curitiba_limpos.json" # O JSON final limpo
    
    try:
        # 1. Carrega os dados brutos
        with open(arquivo_entrada, "r", encoding="utf-8") as f:
            dados_brutos = json.load(f)
    except FileNotFoundError:
        print(f"Erro: O arquivo '{arquivo_entrada}' não foi encontrado.")
        return

    imoveis_limpos = []
    itens_ignorados = 0

    # 2. Processa item por item
    for item in dados_brutos:
        try:
            # O Pydantic aplica a limpeza e tenta validar. 
            # Se a cidade não for Curitiba, o @model_validator levanta um ValueError
            modelo_validado = ImovelCuritibaSchema.model_validate(item)
            
            # Se passou, transforma de volta num dicionário e adiciona à lista final
            imoveis_limpos.append(modelo_validado.model_dump())
        except ValueError:
            # Cai aqui se a cidade for diferente ou o dado for muito inválido
            itens_ignorados += 1

    # 3. Salva apenas os de Curitiba no JSON final
    with open(arquivo_saida, "w", encoding="utf-8") as f:
        json.dump(imoveis_limpos, f, indent=2, ensure_ascii=False)

    print(f"Limpeza concluída com sucesso!")
    print(f"- Total de imóveis limpos em Curitiba: {len(imoveis_limpos)}")
    print(f"- Imóveis ignorados (outras cidades ou erros): {itens_ignorados}")
    print(f"- Arquivo salvo como: {arquivo_saida}")

# Executa a função quando você rodar `python limpar.py` no terminal
if __name__ == "__main__":
    limpar_dados_json()