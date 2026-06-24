import re
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator

# --- Funções Auxiliares de Limpeza (Data Cleaning) ---

def limpar_moeda(valor: Optional[str]) -> float:
    """Remove 'R$', pontos de milhar, espaços e sufixos como '/mês'."""
    if not valor:
        return 0.0
    
    # Se já vier como número por algum motivo, apenas converte
    if isinstance(valor, (int, float)):
        return float(valor)
        
    texto = str(valor)
    texto = texto.replace("R$", "").replace("/mês", "").replace(".", "").strip()
    texto = texto.replace(",", ".")  # Garante padrão float americano se houver centavos
    
    try:
        return float(texto)
    except ValueError:
        return 0.0

def extrair_inteiro(valor: Optional[str]) -> int:
    """Extrai apenas os dígitos numéricos de uma string (ex: '5 ou mais' -> 5, '75m²' -> 75)."""
    if valor is None:
        return 0
    if isinstance(valor, int):
        return valor
        
    texto = str(valor)
    busca = re.search(r'\d+', texto)
    if busca:
        return int(busca.group())
    return 0


# --- Modelo Pydantic para Validação e Higienização ---

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

    # 1. Filtro de Cidade: Roda ANTES de validar os outros campos
    @model_validator(mode="before")
    @classmethod
    def filtrar_apenas_curitiba(cls, data: Any) -> Any:
        # Garante que estamos a lidar com um dicionário
        if isinstance(data, dict):
            cidade = data.get("cidade")
            # Se a cidade não for Curitiba (tratando espaços e maiúsculas/minúsculas), barra o item
            if not cidade or str(cidade).strip().lower() != "curitiba":
                raise ValueError("Ignorado: Imóvel fora da região de Curitiba.")
        return data

    # 2. Limpeza de campos: Rodam logo em seguida se a cidade for aceite
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