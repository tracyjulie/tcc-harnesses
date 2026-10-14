#!/usr/bin/env python3
"""Prova qual PROVEDOR atende cada modelo (Relace, OpenAI, Anthropic).

Faz N chamadas minimas por modelo pelo 9router e, para cada uma, mostra o
provedor que de fato respondeu. Substitui o laco com `curl | jq` (que quebrava
quando o 9router devolvia a resposta em formato de stream).

Chaves (nunca digite no comando):
  - 9router:    arquivo ~/.tcc-segredos/9router.key
  - OpenRouter: variavel OPENROUTER_API_KEY ou arquivo ~/.tcc-segredos/openrouter.key
                (opcional; sem ela o script mostra o provedor que veio na propria
                resposta, se houver, e o id da geracao para conferir no painel)

Uso:
    python3 scripts/verificar_provedor.py            # 3 chamadas por modelo
    python3 scripts/verificar_provedor.py --n 5 --url http://127.0.0.1:20128

Custo: centavos (max_tokens=8). Resultado esperado: DeepSeek -> Relace,
GPT-6 Luna -> OpenAI, Claude Haiku 5.5 -> Anthropic, em TODAS as chamadas.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODELOS = {
    "openrouter/deepseek/deepseek-v4.1-flash": "Relace",
    "openrouter/openai/gpt-6-luna": "OpenAI",
    "openrouter/anthropic/claude-haiku-5.5": "Anthropic",
}


def ler_chave(env, arquivo):
    if os.environ.get(env):
        return os.environ[env].strip()
    caminho = Path(arquivo).expanduser()
    return caminho.read_text(encoding="utf-8").strip() if caminho.exists() else None


def interpretar(corpo):
    """Aceita JSON puro OU stream (linhas `data: {...}`); devolve o ultimo objeto com id."""
    texto = corpo.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    achado = None
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha.startswith("data:"):
            carga = linha[5:].strip()
            if carga and carga != "[DONE]":
                try:
                    obj = json.loads(carga)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and (obj.get("id") or obj.get("provider")):
                    achado = {**(achado or {}), **{k: v for k, v in obj.items() if v is not None}}
    return achado


def chamar(url, chave, modelo):
    req = urllib.request.Request(
        f"{url}/v1/chat/completions",
        data=json.dumps({"model": modelo, "stream": False, "max_tokens": 8,
                         "messages": [{"role": "user", "content": "Responda apenas: OK"}]}).encode(),
        headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")


def provedor_no_openrouter(chave_or, gen_id):
    req = urllib.request.Request(f"https://openrouter.ai/api/v1/generation?id={gen_id}",
                                 headers={"Authorization": f"Bearer {chave_or}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            dados = json.loads(resp.read().decode("utf-8")).get("data", {})
        return dados.get("provider_name")
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:20128")
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    chave = ler_chave("ROUTER_KEY", "~/.tcc-segredos/9router.key")
    if not chave:
        sys.exit("falta a chave do 9router em ~/.tcc-segredos/9router.key")
    chave_or = ler_chave("OPENROUTER_API_KEY", "~/.tcc-segredos/openrouter.key")
    if not chave_or:
        print("(sem chave do OpenRouter: so vale o provedor que vier na resposta;"
              " confira o resto na pagina Activity do OpenRouter)\n")

    falhas = 0
    for modelo, esperado in MODELOS.items():
        for i in range(1, a.n + 1):
            try:
                bruto = chamar(a.url, chave, modelo)
            except Exception as e:  # noqa: BLE001
                print(f"{modelo} #{i}: ERRO na chamada: {e}")
                falhas += 1
                continue
            obj = interpretar(bruto)
            if not obj:
                print(f"{modelo} #{i}: resposta nao reconhecida; primeiros 200 caracteres:\n   {bruto[:200]!r}")
                falhas += 1
                continue
            gen_id = obj.get("id")
            prov = obj.get("provider")  # o OpenRouter costuma devolver o provedor no corpo
            origem = "resposta"
            if not prov and chave_or and gen_id:
                prov, origem = provedor_no_openrouter(chave_or, gen_id), "OpenRouter /generation"
            if not prov:
                print(f"{modelo} #{i}: provedor NAO identificado (id={gen_id}); confira na pagina Activity")
                falhas += 1
                continue
            ok = prov.lower() == esperado.lower()
            falhas += 0 if ok else 1
            print(f"{modelo} #{i}: {prov} (via {origem}) {'OK' if ok else 'DIFERENTE do esperado: ' + esperado}")
    print("\nRESULTADO:", "tudo confere" if not falhas else f"{falhas} problema(s)")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
