import asyncio
import json
import random
import re
import unicodedata
from html import unescape

from playwright.async_api import async_playwright


# ──────────────────────────────────────────────
# LIMPEZA DE DADOS
# ──────────────────────────────────────────────

_VALORES_VAZIOS = {"n/a", "não informado", "nao informado", "sem informação", ""}


def _normalizar_string(texto: str) -> str | None:
    texto = texto.strip()
    texto = re.sub(r"[^\S\n]+", " ", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Cc" or c in "\n\t")
    return texto or None


def _limpar_valor(valor):
    if isinstance(valor, str):
        norm = _normalizar_string(valor)
        if norm is None or norm.lower() in _VALORES_VAZIOS:
            return None
        return norm
    return valor


def _limpar_lista(lista: list) -> list:
    vistos: set = set()
    resultado = []
    for item in lista:
        item_limpo = _limpar_valor(item)
        if item_limpo is not None and item_limpo not in vistos:
            vistos.add(item_limpo)
            resultado.append(item_limpo)
    return resultado


def _limpar_registro(registro: dict) -> dict:
    limpo = {}
    for chave, valor in registro.items():
        if isinstance(valor, list):
            limpo[chave] = _limpar_lista(valor)
        else:
            limpo[chave] = _limpar_valor(valor)
    return limpo


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
# EXTRAÇÃO DE DADOS DO ANÚNCIO
# ──────────────────────────────────────────────

async def extrair_dados_do_anuncio(page, url: str) -> dict:
    await page.goto(url)

    # state="attached": <script type="text/plain"> nunca é "visible" no DOM,
    # mas está presente — o padrão "visible" causava timeout em 100% dos casos.
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
    print(f"  Salvo: {nome_arquivo}  ({len(dados)} registros)")


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

        # ── Etapa 2: extrair dados ─────────────────────────────────────────────
        dados_sucesso: list[dict] = []
        dados_erros:   list[dict] = []

        for i, url in enumerate(todas_urls, 1):
            prefixo = f"[{i}/{len(todas_urls)}]"
            try:
                if page.is_closed():
                    page = await context.new_page()

                dados = await extrair_dados_do_anuncio(page, url)
                dados_sucesso.append(dados)
                print(f"{prefixo} OK  {(dados['titulo'] or url)[:70]}")

            except Exception as exc:
                tipo = type(exc).__name__
                # primeira linha do erro (sem stack trace / call log do Playwright)
                primeira_linha = str(exc).split("\n")[0]
                dados_erros.append({"url": url, "erro": primeira_linha})
                print(f"{prefixo} ERR [{tipo}] {primeira_linha[:80]}")

                if page.is_closed():
                    page = await context.new_page()

            if not page.is_closed():
                await page.wait_for_timeout(random.randint(2_000, 5_000))

        await browser.close()

        # ── Etapa 3: limpeza e gravação ────────────────────────────────────────
        print(f"\nSucesso: {len(dados_sucesso)}  |  Erros: {len(dados_erros)}")

        if dados_sucesso:
            _salvar_json("imoveis_sucesso.json", [_limpar_registro(d) for d in dados_sucesso])

        if dados_erros:
            _salvar_json("imoveis_erros.json", dados_erros)


if __name__ == "__main__":
    asyncio.run(rodar_scraper())