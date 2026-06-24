"""
Script de DIAGNÓSTICO - roda localmente (onde você tem acesso ao OLX)
Objetivo: capturar o HTML real das seções problemáticas (Localização, Valores, Detalhes)
para identificarmos os seletores certos com precisão.

Roda no seu ambiente, gera um arquivo "diagnostico_olx.html" e imprime no console
os trechos relevantes. Depois me cole o conteúdo impresso no console (ou o arquivo)
e eu ajusto os seletores definitivos no scraper principal.
"""
import asyncio
from playwright.async_api import async_playwright

URL_TESTE = "https://pr.olx.com.br/regiao-de-londrina/imoveis/apartamento-edificio-diplomata-centro-1492294153"


async def diagnosticar():
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
        await page.goto(URL_TESTE)
        await page.wait_for_selector("#description-title", timeout=15000)
        await page.wait_for_timeout(2000)  # garante que tudo renderizou

        # Salva o HTML completo da página para inspeção manual se precisar
        html_completo = await page.content()
        with open("diagnostico_olx.html", "w", encoding="utf-8") as f:
            f.write(html_completo)
        print("HTML completo salvo em diagnostico_olx.html\n")

        print("=" * 70)
        print("BLOCO 1: Procurando por 'Localização'")
        print("=" * 70)
        # Acha o elemento que contém o texto "Localização" e imprime o outerHTML
        # do container pai (subindo alguns níveis) para vermos a estrutura
        loc_elements = await page.locator("text=Localização").all()
        for i, el in enumerate(loc_elements):
            try:
                outer = await el.evaluate(
                    "node => node.closest('section, div')?.outerHTML?.slice(0, 1500) "
                    "?? node.outerHTML"
                )
                print(f"--- Match {i} ---")
                print(outer)
                print()
            except Exception as e:
                print(f"Erro no match {i}: {e}")

        print("=" * 70)
        print("BLOCO 2: Procurando por 'Condomínio' (seção Valores)")
        print("=" * 70)
        condo_elements = await page.locator("text=Condomínio").all()
        for i, el in enumerate(condo_elements):
            try:
                outer = await el.evaluate(
                    "node => node.closest('section, div')?.outerHTML?.slice(0, 1000) "
                    "?? node.outerHTML"
                )
                print(f"--- Match {i} ---")
                print(outer)
                print()
            except Exception as e:
                print(f"Erro no match {i}: {e}")

        print("=" * 70)
        print("BLOCO 3: Procurando por 'Detalhes' (Área útil, Quartos, etc)")
        print("=" * 70)
        detalhes_elements = await page.locator("text=Detalhes").all()
        for i, el in enumerate(detalhes_elements):
            try:
                outer = await el.evaluate(
                    "node => node.closest('section, div')?.outerHTML?.slice(0, 2000) "
                    "?? node.outerHTML"
                )
                print(f"--- Match {i} ---")
                print(outer)
                print()
            except Exception as e:
                print(f"Erro no match {i}: {e}")

        print("=" * 70)
        print("BLOCO 4: Título real (h1 da página)")
        print("=" * 70)
        h1_elements = await page.locator("h1").all()
        for i, el in enumerate(h1_elements):
            try:
                outer = await el.evaluate("node => node.outerHTML")
                print(f"--- H1 #{i} ---")
                print(outer)
                print()
            except Exception as e:
                print(f"Erro no H1 #{i}: {e}")

        await page.wait_for_timeout(60000)  # mantém o navegador aberto 60s para você inspecionar manualmente
        await browser.close()


if __name__ == "__main__":
    asyncio.run(diagnosticar())