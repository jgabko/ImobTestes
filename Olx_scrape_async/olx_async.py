import asyncio
import json
import random
import re
from html import unescape

from playwright.async_api import async_playwright
from pydantic import ValidationError

# Importa o seu modelo de validação (certifique-se de que schemas.py está na mesma pasta)
from schemas import ImovelCuritibaSchema


# ──────────────────────────────────────────────
# HELPERS DE EXTRAÇÃO
# ──────────────────────────────────────────────

def _limpar_html_basico(texto) -> str | None:
    if not texto:
        return None
    texto = unescape(texto)
    texto = re.sub(r"<br\s*/?>", "\n", texto, flags=re.IGNORECASE)
    texto = re.sub(r"<[^>]+>", "", texto)
    return texto.strip() or None


def _extrair_valor_por_nome(properties, nome_campo):
    for prop in properties or []:
        if prop.get("name") == nome_campo:
            return prop.get("value")
    return None


# ──────────────────────────────────────────────
# COLETA DE URLs
# ──────────────────────────────────────────────

async def extrair_links_da_pagina(page) -> list[str]:
    await page.wait_for_selector("main")
    links_locator = page.locator('a[href*="/imoveis/"]')
    elementos = await links_locator.all()

    urls_encontradas: list[str] = []
    for elemento in elementos:
        href = await elemento.get_attribute("href")
        if href:
            caminho_base = href.split("?")[0]
            ultima_parte = caminho_base.split("/")[-1]
            tem_padrao_id = "-" in ultima_parte and ultima_parte.split("-")[-1].isdigit()
            tem_parametro_lis = "?lis=" in href
            if (tem_padrao_id or tem_parametro_lis) and href not in urls_encontradas:
                urls_encontradas.append(href)
    return urls_encontradas


# ──────────────────────────────────────────────
# EXTRAÇÃO DE DADOS DO ANÚNCIO (BRUTOS)
# ──────────────────────────────────────────────

async def extrair_dados_do_anuncio(page, url: str) -> dict:
    await page.goto(url)

    await page.wait_for_selector("#initial-data", state="attached", timeout=15_000)

    data_json_str = await page.locator("#initial-data").get_attribute("data-json")
    if not data_json_str:
        raise ValueError("data-json ausente em #initial-data")

    dados_brutos = json.loads(data_json_str)
    ad = dados_brutos.get("ad", {}) or {}

    titulo    = _limpar_html_basico(ad.get("subject"))
    descricao = _limpar_html_basico(ad.get("description") or ad.get("body"))
    preco     = ad.get("priceValue") or ad.get("price") or None

    properties     = ad.get("properties") or []
    valor_cond     = _extrair_valor_por_nome(properties, "condominio")
    valor_iptu     = _extrair_valor_por_nome(properties, "iptu")

    periodo_cond = None
    for item in ad.get("realEstatePriceInfo") or []:
        if item.get("name") == "condominio":
            periodo_cond = item.get("period")
            break

    if valor_cond:
        condominio = f"{valor_cond}/{periodo_cond}" if periodo_cond else valor_cond
    else:
        condominio = None

    location = ad.get("location") or {}

    re_features_raw = _extrair_valor_por_nome(properties, "re_features")
    caracteristicas_imovel = (
        [i.strip() for i in re_features_raw.split(",") if i.strip()]
        if re_features_raw else []
    )

    re_complex_raw = _extrair_valor_por_nome(properties, "re_complex_features")
    caracteristicas_condominio = (
        [i.strip() for i in re_complex_raw.split(",") if i.strip()]
        if re_complex_raw else []
    )

    # Retorna o dicionário com os dados em bruto extraídos do HTML
    return {
        "titulo":                  titulo,
        "preco":                   preco,
        "condominio":              condominio,
        "iptu":                    valor_iptu or None,
        "bairro":                  location.get("neighbourhood") or None,
        "cidade":                  location.get("municipality") or None,
        "estado":                  location.get("uf") or None,
        "cep":                     location.get("zipcode") or None,
        "metragem":                _extrair_valor_por_nome(properties, "size"),
        "quartos":                 _extrair_valor_por_nome(properties, "rooms"),
        "banheiros":               _extrair_valor_por_nome(properties, "bathrooms"),
        "vagas":                   _extrair_valor_por_nome(properties, "garage_spaces"),
        "caracteristicas_imovel":      caracteristicas_imovel,
        "caracteristicas_condominio":  caracteristicas_condominio,
        "descricao":               descricao,
        "url":                     url,
    }


# ──────────────────────────────────────────────
# ORQUESTRADOR PRINCIPAL
# ──────────────────────────────────────────────

def _salvar_json(nome_arquivo: str, dados: list) -> None:
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)
    print(f"  Salvo: {nome_arquivo}  ({len(dados)} registos)")


async def rodar_scraper() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await context.new_page()

        # ── Etapa 1: coletar URLs ──────────────────────────────────────────────
        url_base = "https://www.olx.com.br/imoveis/estado-pr/regiao-de-curitiba"
        print("Coletando URLs...")
        await page.goto(url_base)
        todas_urls = list(set(await extrair_links_da_pagina(page)))
        print(f"{len(todas_urls)} URLs encontradas.\n")

        # ── Etapa 2: extrair e validar dados em memória ────────────────────────
        dados_sucesso: list[dict] = []
        dados_erros:   list[dict] = []
        itens_ignorados = 0

        for i, url in enumerate(todas_urls, 1):
            prefixo = f"[{i}/{len(todas_urls)}]"
            try:
                if page.is_closed():
                    page = await context.new_page()

                # Extrai os dados em bruto da página
                dados_brutos = await extrair_dados_do_anuncio(page, url)

                # --- PIPELINE PYDANTIC (Validação e Filtro) ---
                try:
                    imovel_validado = ImovelCuritibaSchema.model_validate(dados_brutos)
                    dados_sucesso.append(imovel_validado.model_dump())
                    print(f"{prefixo} OK  {(imovel_validado.titulo)[:70]}")
                    
                except (ValueError, ValidationError) as validacao_erro:
                    # Captura erros de validação (ex: Cidade não é Curitiba)
                    # Não adiciona aos erros graves, apenas regista como ignorado
                    msg_erro = str(validacao_erro).split('\n')[0]
                    itens_ignorados += 1
                    print(f"{prefixo} IGNORADO (Filtro): {msg_erro[:60]}")
                # ----------------------------------------------

            except Exception as exc:
                # Captura erros reais do scraper (timeout, seletores, rede)
                tipo = type(exc).__name__
                primeira_linha = str(exc).split("\n")[0]
                dados_erros.append({"url": url, "erro": primeira_linha})
                print(f"{prefixo} ERR [{tipo}] {primeira_linha[:80]}")

                if page.is_closed():
                    page = await context.new_page()

            if not page.is_closed():
                await page.wait_for_timeout(random.randint(2_000, 5_000))

        await browser.close()

        # ── Etapa 3: gravação ──────────────────────────────────────────────────
        print(f"\nFinalizado!")
        print(f"Sucesso (Curitiba): {len(dados_sucesso)} | Ignorados (Outras Cidades/Dados Inválidos): {itens_ignorados} | Erros Scraper: {len(dados_erros)}")

        # Salva o ficheiro final limpo e validado
        if dados_sucesso:
            _salvar_json("imoveis_curitiba_limpos.json", dados_sucesso)

        if dados_erros:
            _salvar_json("imoveis_erros.json", dados_erros)


if __name__ == "__main__":
    asyncio.run(rodar_scraper())