import asyncio
import json
from playwright.async_api import async_playwright

async def extrair_links_da_pagina(page):
    await page.wait_for_selector("main")
    links_locator = page.locator('a[href*="/imoveis/"]')
    elementos = await links_locator.all()
    urls_encontradas = []
    
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

async def extrair_dados_do_anuncio(page, url):
    await page.goto(url)
    await page.wait_for_selector("#description-title", timeout=15000)
    
    titulo_locator = page.locator("#description-title")
    titulo = (await titulo_locator.inner_text()).strip()
    
    desc_locator = page.locator('div[data-section="description"]')
    descricao = (await desc_locator.inner_text()).strip() if (await desc_locator.count()) > 0 else "N/A"
    
    preco_locator = page.locator("#price-box-container p").first
    preco = (await preco_locator.inner_text()).strip() if (await preco_locator.count()) > 0 else "Preço não informado"
        
    condo_locator = page.locator('div:has-text("Condomínio") >> text=/R\$/').last
    condominio_taxa = (await condo_locator.inner_text()).strip() if (await condo_locator.count()) > 0 else "Não informado"

    loc_container = page.locator("div:has(> svg#building-icon)")
    bairro, cidade, estado, cep = "N/A", "N/A", "N/A", "N/A"
    
    if (await loc_container.count()) > 0:
        spans_localizacao = await loc_container.locator("span").all()
        if len(spans_localizacao) >= 1:
            bairro = (await spans_localizacao[0].inner_text()).strip()
        if len(spans_localizacao) >= 2:
            string_localidade = await spans_localizacao[1].inner_text()
            partes = [p.strip() for p in string_localidade.split(",")]
            if len(partes) >= 1: cidade = partes[0]
            if len(partes) >= 2: estado = partes[1]
            if len(partes) >= 3: cep = partes[2]

    metragem_locator = page.locator('li:has-text("m²")').first
    metragem = (await metragem_locator.inner_text()).replace("•", "").strip() if (await metragem_locator.count()) > 0 else "N/A"

    quartos_locator = page.locator('li:has-text("Quarto")').first
    quartos = (await quartos_locator.inner_text()).replace("•", "").strip() if (await quartos_locator.count()) > 0 else "N/A"

    caract_imovel_locator = page.locator('div:has(> span:has-text("Características do imóvel")) >> span[data-ds-component="DS-Badge"]')
    textos_imovel = await caract_imovel_locator.all_inner_texts()
    caracteristicas_imovel = [texto.strip() for texto in textos_imovel if "Características" not in texto]
    
    caract_condo_locator = page.locator('div:has(> span:has-text("Características do condomínio")) >> span[data-ds-component="DS-Badge"]')
    textos_condo = await caract_condo_locator.all_inner_texts()
    caracteristicas_condominio = [texto.strip() for texto in textos_condo if "Características" not in texto]

    return {
        "titulo": titulo, "preco": preco, "condominio": condominio_taxa,
        "bairro": bairro, "cidade": cidade, "estado": estado, "cep": cep,
        "metragem": metragem, "quartos": quartos,
        "caracteristicas_imovel": caracteristicas_imovel,
        "caracteristicas_condominio": caracteristicas_condominio,
        "descricao": descricao, "url": url
    }

async def rodar_scraper():
    async with async_playwright() as p:
        print("Iniciando o navegador...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        url_base = "https://www.olx.com.br/imoveis/estado-pr/regiao-de-curitiba"
        todas_urls_anuncios = set()
        
        print("--- ETAPA 1: Coletando URLs da listagem ---")
        await page.goto(url_base)
        todas_urls_anuncios.update(await extrair_links_da_pagina(page))
        
        dados_imoveis = []
        
        print("\n--- ETAPA 2: Extraindo dados profundos dos anúncios ---")
        urls_para_visitar = list(todas_urls_anuncios)[:2]
        
        for i, url in enumerate(urls_para_visitar, 1):
            print(f"[{i}/{len(urls_para_visitar)}] Extraindo dados de: {url}")
            try:
                dados = await extrair_dados_do_anuncio(page, url)
                dados_imoveis.append(dados)
                print(" -> Sucesso! Dados estruturados capturados.")
                print(f"    Exemplo - CEP: {dados['cep']} | Itens Imóvel: {dados['caracteristicas_imovel']}")
            except Exception as e:
                print(f" -> Erro crítico ao extrair este anúncio: {e}")
            
            await page.wait_for_timeout(3000)
            
        print("\n=== SESSÃO DE TESTE CONCLUÍDA ===")
        print(f"Dicionários gerados com sucesso: {len(dados_imoveis)}")

        if dados_imoveis:
            nome_arquivo = "imoveis_olx_brutos.json"
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                json.dump(dados_imoveis, f, ensure_ascii=False, indent=4)
            print(f"=== SUCESSO! Dados salvos em {nome_arquivo} ===")
            print("Pronto para ser consumido pelo Pydantic!")
        
        await browser.close()

if __name__ == "__main__":
    run_code = True
    asyncio.run(rodar_scraper())