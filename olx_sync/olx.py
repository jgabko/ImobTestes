from playwright.sync_api import sync_playwright
from collections import deque
import json

def get_olx_page_links(page):
    # 1. Aguarda que o corpo da página ou a lista principal carregue no DOM
        page.wait_for_selector("main")

        # 2. Cria um locator resiliente para capturar os links que contêm o padrão de imóveis
        # Usamos o seletor CSS para tags 'a' cujo atributo 'href' contém '/imoveis/'
        links_locator = page.locator('a[href*="/imoveis/"]')
        
        # 3. Transforma o locator numa lista de elementos iteráveis
        elementos = links_locator.all()

        urls_anuncios = []
        
        # 4. Loop para extrair e filtrar as URLs
        for elemento in elementos:
            href = elemento.get_attribute("href")
            
            if href:
                # Vamos verificar se o link parece um anúncio real usando o padrão que você encontrou:
                # 1. Precisa ter um código de listagem (?lis=) OU
                # 2. Terminar com um número longo (ID do anúncio) antes de qualquer "?"
                
                # Pega a última parte da URL ignorando parâmetros (ex: o slug e o ID)
                caminho_base = href.split("?")[0]
                ultima_parte = caminho_base.split("/")[-1]
                
                # Verifica se a última parte contém traços e termina com números (padrão OLX)
                # ou se tem o parâmetro listing
                tem_padrao_id = "-" in ultima_parte and ultima_parte.split("-")[-1].isdigit()
                tem_parametro_lis = "?lis=" in href
                
                if (tem_padrao_id or tem_parametro_lis) and href not in urls_anuncios:
                    urls_anuncios.append(href)
      
        print(f"Elementos encontrados pelo seletor: {len(elementos)}")
        
        
       
        
        
        return urls_anuncios
#Estudar esse metodo depois..
def extrair_dados_do_anuncio(page, url):
    """
    Extrai minuciosamente todos os dados brutos do anúncio com base no DOM real fornecido.
    """
    page.goto(url)
    
    # Âncora de carregamento global da página interna
    page.wait_for_selector("#description-title", timeout=15000)
    
    # 1. Título e Descrição (Anexos 4 e 5)
    titulo = page.locator("#description-title").inner_text().strip()
    
    desc_locator = page.locator('div[data-section="description"]')
    descricao = desc_locator.inner_text().strip() if desc_locator.count() > 0 else "N/A"
    
    # 2. Preço Principal (Anexo 7)
    preco_locator = page.locator("#price-box-container p").first
    preco = preco_locator.inner_text().strip() if preco_locator.count() > 0 else "Preço não informado"
        
    # 3. Taxa de Condomínio (Anexo 7 - Varredura por texto descritivo na tabela de valores)
    condo_locator = page.locator('div:has-text("Condomínio") >> text=/R\$/').last
    condominio_taxa = condo_locator.inner_text().strip() if condo_locator.count() > 0 else "Não informado"

    # 4. Localização: Bairro, Cidade, Estado e CEP (Anexo 3)
    loc_container = page.locator("div:has(> svg#building-icon)")
    
    bairro = "N/A"
    cidade, estado, cep = "N/A", "N/A", "N/A"
    
    if loc_container.count() > 0:
        spans_localizacao = loc_container.locator("span").all()
        if len(spans_localizacao) >= 1:
            bairro = spans_localizacao[0].inner_text().strip()
        if len(spans_localizacao) >= 2:
            # Captura a string combinada (Ex: "Curitiba, PR, 82840140")
            string_localidade = spans_localizacao[1].inner_text()
            partes = [p.strip() for p in string_localidade.split(",")]
            
            if len(partes) >= 1: cidade = partes[0]
            if len(partes) >= 2: estado = partes[1]
            if len(partes) >= 3: cep = partes[2]

    # 5. Detalhes estruturais: Metragem e Quartos (Anexo 6)
    metragem_locator = page.locator('li:has-text("m²")').first
    metragem = metragem_locator.inner_text().replace("•", "").strip() if metragem_locator.count() > 0 else "N/A"

    quartos_locator = page.locator('li:has-text("Quarto")').first
    quartos = quartos_locator.inner_text().replace("•", "").strip() if quartos_locator.count() > 0 else "N/A"

    # 6. Características do Imóvel e do Condomínio (Anexos 1 e 8)
    # Buscamos as Badges específicas de cada bloco conceitual usando o token do Design System
    caract_imovel_locator = page.locator('div:has(> span:has-text("Características do imóvel")) >> span[data-ds-component="DS-Badge"]')
    caracteristicas_imovel = [texto.strip() for texto in caract_imovel_locator.all_inner_texts() if "Características" not in texto]
    
    caract_condo_locator = page.locator('div:has(> span:has-text("Características do condomínio")) >> span[data-ds-component="DS-Badge"]')
    caracteristicas_condominio = [texto.strip() for texto in caract_condo_locator.all_inner_texts() if "Características" not in texto]

    # Retorno do dicionário robusto pronto para o Pydantic
    return {
        "titulo": titulo,
        "preco": preco,
        "condominio": condominio_taxa,
        "bairro": bairro,
        "cidade": cidade,
        "estado": estado,
        "cep": cep,
        "metragem": metragem,
        "quartos": quartos,
        "caracteristicas_imovel": caracteristicas_imovel,
        "caracteristicas_condominio": caracteristicas_condominio,
        "descricao": descricao,
        "url": url
    }
        
def extrair_dados_do_anuncio(page, url):
    """
    Extrai minuciosamente todos os dados brutos do anúncio com base no DOM real fornecido.
    """
    page.goto(url)
    
    # Âncora de carregamento global da página interna
    page.wait_for_selector("#description-title", timeout=15000)
    
    # 1. Título e Descrição (Anexos 4 e 5)
    titulo = page.locator("#description-title").inner_text().strip()
    
    desc_locator = page.locator('div[data-section="description"]')
    descricao = desc_locator.inner_text().strip() if desc_locator.count() > 0 else "N/A"
    
    # 2. Preço Principal (Anexo 7)
    preco_locator = page.locator("#price-box-container p").first
    preco = preco_locator.inner_text().strip() if preco_locator.count() > 0 else "Preço não informado"
        
    # 3. Taxa de Condomínio (Anexo 7 - Varredura por texto descritivo na tabela de valores)
    condo_locator = page.locator('div:has-text("Condomínio") >> text=/R\$/').last
    condominio_taxa = condo_locator.inner_text().strip() if condo_locator.count() > 0 else "Não informado"

    # 4. Localização: Bairro, Cidade, Estado e CEP (Anexo 3)
    loc_container = page.locator("div:has(> svg#building-icon)")
    
    bairro = "N/A"
    cidade, estado, cep = "N/A", "N/A", "N/A"
    
    if loc_container.count() > 0:
        spans_localizacao = loc_container.locator("span").all()
        if len(spans_localizacao) >= 1:
            bairro = spans_localizacao[0].inner_text().strip()
        if len(spans_localizacao) >= 2:
            # Captura a string combinada (Ex: "Curitiba, PR, 82840140")
            string_localidade = spans_localizacao[1].inner_text()
            partes = [p.strip() for p in string_localidade.split(",")]
            
            if len(partes) >= 1: cidade = partes[0]
            if len(partes) >= 2: estado = partes[1]
            if len(partes) >= 3: cep = partes[2]

    # 5. Detalhes estruturais: Metragem e Quartos (Anexo 6)
    metragem_locator = page.locator('li:has-text("m²")').first
    metragem = metragem_locator.inner_text().replace("•", "").strip() if metragem_locator.count() > 0 else "N/A"

    quartos_locator = page.locator('li:has-text("Quarto")').first
    quartos = quartos_locator.inner_text().replace("•", "").strip() if quartos_locator.count() > 0 else "N/A"

    # 6. Características do Imóvel e do Condomínio (Anexos 1 e 8)
    # Buscamos as Badges específicas de cada bloco conceitual usando o token do Design System
    caract_imovel_locator = page.locator('div:has(> span:has-text("Características do imóvel")) >> span[data-ds-component="DS-Badge"]')
    caracteristicas_imovel = [texto.strip() for texto in caract_imovel_locator.all_inner_texts() if "Características" not in texto]
    
    caract_condo_locator = page.locator('div:has(> span:has-text("Características do condomínio")) >> span[data-ds-component="DS-Badge"]')
    caracteristicas_condominio = [texto.strip() for texto in caract_condo_locator.all_inner_texts() if "Características" not in texto]

    # Retorno do dicionário robusto pronto para o Pydantic
    return {
        "titulo": titulo,
        "preco": preco,
        "condominio": condominio_taxa,
        "bairro": bairro,
        "cidade": cidade,
        "estado": estado,
        "cep": cep,
        "metragem": metragem,
        "quartos": quartos,
        "caracteristicas_imovel": caracteristicas_imovel,
        "caracteristicas_condominio": caracteristicas_condominio,
        "descricao": descricao,
        "url": url
    }
def scraper_olx():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)
        context=browser.new_context()

        page=context.new_page()

        url_base = "https://www.olx.com.br/imoveis/estado-pr/regiao-de-curitiba"

        print(f"Acessando: {url_base}")
        page.goto(url_base)

        # Usamos um 'set' para armazenar globalmente, evitando duplicatas entre páginas
        # O set usa uma lógica matemática nos bastidores (chamada Hash Table) que permite a ele saber se um link já existe quase instantaneamente, 
        # não importa se você tem 10 links ou 1 milhão.
        todas_urls_anuncios = set()
        
        # Vamos definir a raspagem das 3 primeiras páginas para teste
        numero_de_paginas = 5

        for i in range(1, numero_de_paginas + 1):
            print(f"\n--- Navegando para a página {i} ---")

            # Monta a URL baseada na página atual
            if i == 1:
                url_atual = url_base
            else:
                url_atual = f"{url_base}?o={i}"

            print(f"Acessando: {url_atual}")
            page.goto(url_atual)

            links_extraidos = get_olx_page_links(page)
            print(f"Encontrados {len(links_extraidos)} links válidos nesta página.")

            # O método .update() adiciona os itens novos ao set, ignorando os que já existem lá
            todas_urls_anuncios.update(links_extraidos)

            page.wait_for_timeout(2500)


        print("\n=== RESUMO DA COLETA ===")
        print(f"Total de anúncios únicos extraídos: {len(todas_urls_anuncios)}")
        
        # print("Amostra dos 5 primeiros links globais:")
        # for i, url in enumerate(list(todas_urls_anuncios)[:5], 1):
        #     print(f"{i}: {url}")

       # CONSUMO SEGURO DA FILA
        queue_urls_anuncio = deque(todas_urls_anuncios)
        total_links = len(queue_urls_anuncio)
        contador = 1
        dados_imoveis = []

        print("\n=== Processando os links ===")
        while queue_urls_anuncio:
            url = queue_urls_anuncio.popleft()
            print(f"[{contador}/{total_links}] Extraindo: {url}")
            
            try:
                dados = extrair_dados_do_anuncio(page, url)
                dados_imoveis.append(dados)
                print(f" -> Sucesso: {dados['titulo'][:30]}...")
            except Exception as e:
                print(f" -> Pulo: Página fora do ar ou bloqueio.")
            
            contador += 1
            page.wait_for_timeout(2500)
            
        print(f"\nColeta finalizada! {len(dados_imoveis)} anúncios extraídos com sucesso.")
        
        # ARMAZENAMENTO ESTRUTURADO EM JSON
        if dados_imoveis:
            nome_arquivo = "imoveis_olx_brutos.json"
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                json.dump(dados_imoveis, f, ensure_ascii=False, indent=4)
            print(f"=== SUCESSO! Dados salvos em {nome_arquivo} ===")
            print("Pronto para ser consumido pelo Pydantic!")
        
        
        
        #urls_anuncios=get_olx_page_links(page)

        # print(f"\n--- Sucesso! Extraídas {len(urls_anuncios)} URLs de anúncios únicos ---")
        # for i, url in enumerate(urls_anuncios[:5], 1):
        #     print(f"{i}: {url}")
        
        
        print("Fechando o navegador.")
        browser.close()
        

if __name__ == "__main__":
    scraper_olx()
        

        