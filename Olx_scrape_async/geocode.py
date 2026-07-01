"""
Geocodifica os CEPs de imoveis_raw que ainda não estão na tabela
cep_coordenadas, e salva o resultado direto no Supabase.

Estratégia (nessa ordem, parando na primeira que funcionar):
  1) BrasilAPI  -> agrega Correios/ViaCEP/Widenet e, para boa parte dos CEPs
     urbanos, já devolve latitude/longitude prontas. Não precisa geocodificar
     nada, é o caminho mais confiável.
  2) ViaCEP (endereço) + Nominatim/OpenStreetMap (geocodifica o endereço)
     -> usado só quando a BrasilAPI não tem coordenada para aquele CEP.
     Respeita o limite de 1 requisição/segundo do Nominatim.

Diferente da versão anterior, aqui os erros são logados com a causa real
(status HTTP, timeout, JSON inválido etc.) em vez de virarem silenciosamente
"não encontrado" — se voltar a falhar 100% das vezes, o log já mostra onde.

Só precisa ser rodado de novo quando aparecerem CEPs novos no banco — os já
resolvidos são pulados automaticamente.

Uso:
  python geocode_cep.py
"""
import time

import requests

from supabase_f import fetch_ceps_ja_geocodificados, fetch_ceps_unicos, salvar_cep_coordenadas

HEADERS_NOMINATIM = {
    "User-Agent": "ImobTestes-Curitiba/1.0 (contato@example.com)"
}


def _normalizar_cep(cep: str) -> str:
    return "".join(filter(str.isdigit, str(cep))).zfill(8)


def buscar_coordenadas_brasilapi(cep: str):
    """Retorna (lat, lon, endereco). lat/lon podem vir None se a fonte não
    tiver coordenada para esse CEP, mesmo que o endereço exista."""
    cep = _normalizar_cep(cep)
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cep/v2/{cep}", timeout=10)
        if r.status_code != 200:
            print(f"  [BrasilAPI] status HTTP {r.status_code}")
            return None, None, None

        dados = r.json()
        endereco = ", ".join(filter(None, [
            dados.get("street"), dados.get("neighborhood"), dados.get("city"), dados.get("state"),
        ])) or None

        coords = (dados.get("location") or {}).get("coordinates") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if lat and lon:
            return float(lat), float(lon), endereco
        return None, None, endereco
    except requests.RequestException as e:
        print(f"  [BrasilAPI] erro de rede: {e}")
        return None, None, None
    except (ValueError, KeyError, TypeError) as e:
        print(f"  [BrasilAPI] erro ao processar resposta: {e}")
        return None, None, None


def buscar_endereco_viacep(cep: str):
    cep = _normalizar_cep(cep)
    try:
        r = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=10)
        if r.status_code != 200:
            print(f"  [ViaCEP] status HTTP {r.status_code}")
            return None
        dados = r.json()
        if dados.get("erro"):
            return None
        partes = [dados.get("logradouro"), dados.get("bairro"), dados.get("localidade"), dados.get("uf")]
        return ", ".join(p for p in partes if p) or None
    except requests.RequestException as e:
        print(f"  [ViaCEP] erro de rede: {e}")
        return None
    except ValueError as e:
        print(f"  [ViaCEP] resposta não é JSON válido: {e}")
        return None


def geocodificar_nominatim(endereco: str):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{endereco}, Brasil", "format": "json", "limit": 1},
            headers=HEADERS_NOMINATIM,
            timeout=10,
        )
        if r.status_code != 200:
            print(f"  [Nominatim] status HTTP {r.status_code}: {r.text[:150]!r}")
            return None, None
        resultados = r.json()
        if not resultados:
            return None, None
        return float(resultados[0]["lat"]), float(resultados[0]["lon"])
    except requests.RequestException as e:
        print(f"  [Nominatim] erro de rede: {e}")
        return None, None
    except (ValueError, KeyError, IndexError) as e:
        print(f"  [Nominatim] erro ao processar resposta: {e}")
        return None, None


def resolver_cep(cep: str):
    """Retorna (lat, lon, endereco, fonte)."""
    lat, lon, endereco = buscar_coordenadas_brasilapi(cep)
    if lat and lon:
        return lat, lon, endereco, "BrasilAPI"

    if not endereco:
        endereco = buscar_endereco_viacep(cep)

    if endereco:
        time.sleep(1.1)  # respeita o limite de 1 req/s do Nominatim
        lat, lon = geocodificar_nominatim(endereco)
        if lat and lon:
            return lat, lon, endereco, "Nominatim"

    return None, None, endereco, None


def main():
    ceps_unicos = fetch_ceps_unicos()
    ja_resolvidos = fetch_ceps_ja_geocodificados()
    pendentes = [c for c in ceps_unicos if c not in ja_resolvidos]

    print(f"{len(ceps_unicos)} CEPs únicos no total, {len(pendentes)} ainda sem coordenadas.")

    encontrados = 0
    for i, cep in enumerate(pendentes, start=1):
        lat, lon, endereco, fonte = resolver_cep(cep)
        salvar_cep_coordenadas(cep, lat, lon, endereco)

        if lat and lon:
            encontrados += 1
            print(f"[{i}/{len(pendentes)}] {cep} -> ok via {fonte} ({lat:.5f}, {lon:.5f})")
        else:
            print(f"[{i}/{len(pendentes)}] {cep} -> não encontrado (endereço: {endereco!r})")

        time.sleep(0.3)  # respiro entre CEPs mesmo quando só BrasilAPI foi usada

    print(f"\nConcluído. {encontrados}/{len(pendentes)} CEPs novos resolvidos com sucesso.")


if __name__ == "__main__":
    main()