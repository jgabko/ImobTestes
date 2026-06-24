"""Teste rápido da lógica de extração usando uma amostra real do initial-data."""
import json
import re
from html import unescape

# Amostra real, recortada do data-json que vimos no HTML do anúncio do Edifício Diplomata
AMOSTRA_REAL = {
    "ad": {
        "subject": "Apartamento | Edifício Diplomata | Centro",
        "body": "Código do anúncio: 6883&lt;br&gt;&lt;br&gt;Apartamento com 3 quartos a venda no Edifício Diplomata em Londrina.&lt;br&gt;Localização excelente na rua Paranaguá, no centro, próximo a mercados e comércio em geral.&lt;br&gt;&lt;br&gt;Apartamento com 03 quartos, 03 banheiros sendo 01 suíte.&lt;br&gt;Amplas salas com 02 ambientes, copa, cozinha e área de serviço.&lt;br&gt;02 vagas de garagem.&lt;br&gt;&lt;br&gt;Entre em contato e agende hoje mesmo sua visita!&lt;br&gt;&lt;br&gt;CONECTE-SE!",
        "priceValue": "R$ 750.000",
        "location": {
            "neighbourhood": "Centro",
            "municipality": "Londrina",
            "zipcode": "86020912",
            "uf": "PR",
        },
        "properties": [
            {"name": "condominio", "label": "Condomínio", "value": "R$ 1.100"},
            {"name": "iptu", "label": "IPTU", "value": "R$ 0"},
            {"name": "size", "label": "Área útil", "value": "147m²"},
            {"name": "rooms", "label": "Quartos", "value": "3"},
            {"name": "bathrooms", "label": "Banheiros", "value": "3"},
            {"name": "garage_spaces", "label": "Vagas na garagem", "value": "2"},
            {
                "name": "re_features",
                "label": "Detalhes do imóvel",
                "value": "Academia, Varanda",
            },
            {
                "name": "re_complex_features",
                "label": "Detalhes do condomínio",
                "value": "Academia, Condomínio fechado, Elevador, Permitido animais, Salão de festas",
            },
        ],
        "realEstatePriceInfo": [
            {"name": "Preço", "label": "Venda", "value": "R$ 750.000"},
            {"name": "condominio", "label": "Condomínio", "value": "R$ 1.100", "period": "mês"},
            {"name": "iptu", "label": "IPTU", "value": "R$ 0"},
        ],
    }
}


def _limpar_html_basico(texto):
    if not texto:
        return "N/A"
    texto = unescape(texto)
    texto = re.sub(r"<br\s*/?>", "\n", texto, flags=re.IGNORECASE)
    texto = re.sub(r"<[^>]+>", "", texto)
    return texto.strip()


def _extrair_valor_por_nome(properties, nome_campo):
    for prop in properties or []:
        if prop.get("name") == nome_campo:
            return prop.get("value")
    return None


def testar():
    ad = AMOSTRA_REAL["ad"]

    titulo = _limpar_html_basico(ad.get("subject", "N/A"))
    descricao = _limpar_html_basico(ad.get("description") or ad.get("body", "N/A"))
    preco = ad.get("priceValue") or ad.get("price") or "Preço não informado"

    properties = ad.get("properties", [])
    valor_condominio = _extrair_valor_por_nome(properties, "condominio")
    valor_iptu = _extrair_valor_por_nome(properties, "iptu")

    condominio_periodo = None
    for item in ad.get("realEstatePriceInfo", []) or []:
        if item.get("name") == "condominio":
            condominio_periodo = item.get("period")
            break

    condominio_taxa = (
        f"{valor_condominio}/{condominio_periodo}" if valor_condominio and condominio_periodo
        else (valor_condominio or "Não informado")
    )
    iptu = valor_iptu if valor_iptu else "Não informado"

    location = ad.get("location", {}) or {}
    bairro = location.get("neighbourhood") or "N/A"
    cidade = location.get("municipality") or "N/A"
    estado = location.get("uf") or "N/A"
    cep = location.get("zipcode") or "N/A"

    metragem = _extrair_valor_por_nome(properties, "size") or "N/A"
    quartos = _extrair_valor_por_nome(properties, "rooms") or "N/A"
    banheiros = _extrair_valor_por_nome(properties, "bathrooms") or "N/A"
    vagas = _extrair_valor_por_nome(properties, "garage_spaces") or "N/A"

    re_features_raw = _extrair_valor_por_nome(properties, "re_features")
    caracteristicas_imovel = (
        [item.strip() for item in re_features_raw.split(",") if item.strip()]
        if re_features_raw else []
    )
    re_complex_features_raw = _extrair_valor_por_nome(properties, "re_complex_features")
    caracteristicas_condominio = (
        [item.strip() for item in re_complex_features_raw.split(",") if item.strip()]
        if re_complex_features_raw else []
    )

    resultado = {
        "titulo": titulo, "preco": preco, "condominio": condominio_taxa, "iptu": iptu,
        "bairro": bairro, "cidade": cidade, "estado": estado, "cep": cep,
        "metragem": metragem, "quartos": quartos, "banheiros": banheiros, "vagas": vagas,
        "caracteristicas_imovel": caracteristicas_imovel,
        "caracteristicas_condominio": caracteristicas_condominio,
        "descricao": descricao,
    }

    print(json.dumps(resultado, ensure_ascii=False, indent=2))

    # Validações automáticas (comparando com o que sabemos ser o valor correto)
    assert resultado["titulo"] == "Apartamento | Edifício Diplomata | Centro", "Título errado!"
    assert "Código do anúncio: 6883" in resultado["descricao"], "Descrição não capturada corretamente"
    assert "CONECTE-SE!" in resultado["descricao"], "Descrição truncada"
    assert "<br>" not in resultado["descricao"] and "&lt;" not in resultado["descricao"], "HTML não foi limpo"
    assert "\nApartamento com 3 quartos" in resultado["descricao"], "Quebra de linha (\\n) não inserida corretamente"
    assert resultado["preco"] == "R$ 750.000", "Preço errado!"
    assert resultado["condominio"] == "R$ 1.100/mês", f"Condomínio errado! Veio: {resultado['condominio']}"
    assert resultado["iptu"] == "R$ 0", "IPTU errado!"
    assert resultado["bairro"] == "Centro", "Bairro errado!"
    assert resultado["cidade"] == "Londrina", "Cidade errada!"
    assert resultado["estado"] == "PR", "Estado errado!"
    assert resultado["cep"] == "86020912", "CEP errado!"
    assert resultado["metragem"] == "147m²", "Metragem errada!"
    assert resultado["quartos"] == "3", "Quartos errado!"
    assert resultado["banheiros"] == "3", "Banheiros errado!"
    assert resultado["vagas"] == "2", "Vagas errado!"
    assert resultado["caracteristicas_imovel"] == ["Academia", "Varanda"], "Características do imóvel erradas!"
    assert resultado["caracteristicas_condominio"] == [
        "Academia", "Condomínio fechado", "Elevador", "Permitido animais", "Salão de festas"
    ], "Características do condomínio erradas!"

    print("\n✅ TODOS OS TESTES PASSARAM — lógica de extração validada com dados reais do anúncio.")


if __name__ == "__main__":
    testar()