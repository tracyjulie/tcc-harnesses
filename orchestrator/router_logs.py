#!/usr/bin/env python3
"""Leitura do ponto unico de instrumentacao (9router) para custo, tokens e
parametros efetivos por rodada (plano v2, secoes 6.3, 7.10 item 7, 7.11 e 8.2).

O 9router grava cada chamada em `~/.9router/db/data.sqlite` (ou no diretorio
apontado por `TCC_LOGS_ROUTER`). A tabela `usageHistory` tem, por chamada:
timestamp, provider, model, endpoint, promptTokens, completionTokens, cost
(USD) e um JSON `tokens` com cached_tokens e reasoning_tokens.

Este modulo:
- agrega as chamadas dentro da janela [inicio, fim] da rodada;
- separa por modelo (para detectar contaminacao de outra rodada);
- devolve custo e tokens medidos, e o metodo do custo.

Regra de ouro: campo nao observado = `null`, nunca zero. Se o banco nao existir
ou a leitura falhar, devolve `null` sem interromper a rodada.
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

MARGEM_SEGUNDOS = 20
MODELOS_JSON = Path(__file__).resolve().parent / "modelos.json"
PROVEDOR_ROTULO = {"openai": "OpenAI", "anthropic": "Anthropic", "relace": "Relace"}
COST_METHOD = "medido (usageHistory do 9router)"


def caminho_banco():
    raiz = os.environ.get("TCC_LOGS_ROUTER")
    if raiz:
        return Path(raiz) / "data.sqlite"
    return Path.home() / ".9router" / "db" / "data.sqlite"


def _parse_iso(texto):
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


def _modelo_esperado(provedor, modelo_id):
    """Modelo como o 9router registra em usageHistory: <org>/<slug>.

    O slug vem de `orchestrator/modelos.json` (ex.: `anthropic/claude-haiku-5.5`,
    com ponto), nao do `modelo_id` do plano (`claude-haiku-5-5`, com hifen).
    Montar o nome a partir do `modelo_id` fazia todo o uso do Haiku ser
    descartado como se fosse de outro modelo.
    """
    tabela = {}
    if MODELOS_JSON.exists():
        try:
            tabela = json.loads(MODELOS_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            tabela = {}
    sufixo = f":{provedor}:{modelo_id}"
    for chave, rota in tabela.items():
        if chave.endswith(sufixo) and isinstance(rota, str) and "openrouter/" in rota:
            return rota.split("openrouter/", 1)[1]
    org = {"openai": "openai", "anthropic": "anthropic", "relace": "deepseek"}.get(
        provedor, provedor)
    return f"{org}/{modelo_id}"


def _vazio(modelo_esperado):
    return {
        "input_tokens": None,
        "output_tokens": None,
        "cached_tokens": None,
        "reasoning_tokens": None,
        "cost_usd": None,
        "cost_method": None,
        "router_requests": None,
        "router_models": None,
        "router_endpoints": None,
        "router_provider": None,
        "provedor_efetivo": None,
        "modelo_esperado": modelo_esperado,
    }


def custo_desde(inicio_iso, provedor, modelo_id):
    """Custo (USD) acumulado desde `inicio_iso` para o modelo esperado.

    Usado pelo vigia do teto de custo durante a rodada. Sem margem de tempo.
    Devolve None se o banco nao existir ou nao houver custo registrado.
    """
    inicio = _parse_iso(inicio_iso)
    banco = caminho_banco()
    if inicio is None or not banco.exists():
        return None
    esperado = _modelo_esperado(provedor, modelo_id)
    corte = inicio.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True, timeout=5)
        cur = con.cursor()
        cur.execute(
            "SELECT cost FROM usageHistory WHERE model = ? AND substr(timestamp,1,19) >= ?",
            (esperado, corte))
        valores = [c for (c,) in cur.fetchall() if c is not None]
        con.close()
    except sqlite3.Error:
        return None
    return round(sum(valores), 6) if valores else None


def provedor_efetivo(inicio_iso, fim_iso, esperado_modelo):
    """Tenta ler o provedor que de fato atendeu (ex.: Relace) em requestDetails.

    O OpenRouter devolve `"provider": "<Nome>"` no corpo da resposta. Se o
    9router guarda esse corpo em `requestDetails`, o nome aparece la. A busca e
    tolerante: se a tabela, as colunas ou o campo nao existirem, devolve None
    (nunca inventa). Retorna {provedor: contagem}.
    """
    banco = caminho_banco()
    inicio, fim = _parse_iso(inicio_iso), _parse_iso(fim_iso)
    if inicio is None or fim is None or not banco.exists():
        return None
    ini = (inicio - timedelta(seconds=MARGEM_SEGUNDOS)).strftime("%Y-%m-%dT%H:%M:%S")
    fi = (fim + timedelta(seconds=MARGEM_SEGUNDOS)).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True, timeout=5)
        cur = con.cursor()
        colunas = [c[1] for c in cur.execute("PRAGMA table_info(requestDetails)").fetchall()]
        if not colunas:
            con.close()
            return None
        col_tempo = next((c for c in colunas if c.lower() in ("timestamp", "createdat", "created_at")), None)
        consulta = "SELECT * FROM requestDetails"
        params = ()
        if col_tempo:
            consulta += f" WHERE substr({col_tempo},1,19) BETWEEN ? AND ?"
            params = (ini, fi)
        linhas = cur.execute(consulta, params).fetchall()
        con.close()
    except sqlite3.Error:
        return None
    padrao = re.compile(r'"provider(?:_name)?"\s*:\s*"([^"]+)"')
    contagem = {}
    for linha in linhas:
        texto = " ".join(str(v) for v in linha if isinstance(v, (str, bytes)) and v)
        if esperado_modelo and esperado_modelo not in texto:
            continue
        for nome in padrao.findall(texto):
            if nome.lower() in ("openrouter", "9router"):
                continue
            contagem[nome] = contagem.get(nome, 0) + 1
    return contagem or None


def agregar_janela(inicio_iso, fim_iso, provedor, modelo_id):
    """Agrega o uso do 9router na janela da rodada.

    `inicio_iso`/`fim_iso` no formato do manifesto (UTC, ate segundos). Se o
    banco nao existir ou nao houver chamadas, todos os campos ficam `null`.
    """
    esperado = _modelo_esperado(provedor, modelo_id)
    vazio = _vazio(esperado)
    inicio = _parse_iso(inicio_iso)
    fim = _parse_iso(fim_iso)
    if inicio is None or fim is None:
        return vazio
    inicio = (inicio - timedelta(seconds=MARGEM_SEGUNDOS)).strftime("%Y-%m-%dT%H:%M:%S")
    fim = (fim + timedelta(seconds=MARGEM_SEGUNDOS)).strftime("%Y-%m-%dT%H:%M:%S")

    banco = caminho_banco()
    if not banco.exists():
        return vazio

    try:
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    except sqlite3.Error:
        return vazio

    try:
        cur = con.cursor()
        cur.execute(
            "SELECT provider, model, endpoint, promptTokens, completionTokens, "
            "cost, tokens FROM usageHistory "
            "WHERE substr(timestamp,1,19) BETWEEN ? AND ?",
            (inicio, fim),
        )
        linhas = cur.fetchall()
    except sqlite3.Error:
        con.close()
        return vazio
    con.close()

    if not linhas:
        return vazio

    # Detecta contaminacao: modelos vistos na janela que nao o esperado.
    modelos = {}
    endpoints = {}
    providers = {}
    usados = {"input": 0, "output": 0, "cache": 0, "reasoning": 0}
    visto = {"input": False, "output": False, "cache": False, "reasoning": False}
    custo = 0.0
    custo_visto = False

    for provider, model, endpoint, ptok, ctok, cost, tokens in linhas:
        modelos[model] = modelos.get(model, 0) + 1
        if endpoint:
            endpoints[endpoint] = endpoints.get(endpoint, 0) + 1
        if provider:
            providers[provider] = providers.get(provider, 0) + 1
        if model != esperado:
            continue
        if ptok is not None:
            usados["input"] += ptok
            visto["input"] = True
        if ctok is not None:
            usados["output"] += ctok
            visto["output"] = True
        if cost is not None:
            custo += cost
            custo_visto = True
        try:
            extra = json.loads(tokens) if tokens else {}
        except (json.JSONDecodeError, TypeError):
            extra = {}
        if isinstance(extra, dict):
            if extra.get("cached_tokens") is not None:
                usados["cache"] += extra["cached_tokens"]
                visto["cache"] = True
            if extra.get("reasoning_tokens") is not None:
                usados["reasoning"] += extra["reasoning_tokens"]
                visto["reasoning"] = True

    def _ou_none(valor, flag):
        return valor if flag else None

    return {
        "input_tokens": _ou_none(usados["input"], visto["input"]),
        "output_tokens": _ou_none(usados["output"], visto["output"]),
        "cached_tokens": _ou_none(usados["cache"], visto["cache"]),
        "reasoning_tokens": _ou_none(usados["reasoning"], visto["reasoning"]),
        "cost_usd": round(custo, 6) if custo_visto else None,
        "cost_method": COST_METHOD if custo_visto else None,
        "router_requests": len(linhas),
        "router_models": modelos,
        "router_endpoints": endpoints,
        "router_provider": providers,
        "provedor_efetivo": provedor_efetivo(inicio_iso, fim_iso, esperado),
        "modelo_esperado": esperado,
        "contaminacao": sorted(m for m in modelos if m != esperado),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 5:
        sys.exit("uso: python orchestrator/router_logs.py inicio_iso fim_iso provedor modelo_id")
    print(json.dumps(agregar_janela(*sys.argv[1:]), ensure_ascii=False, indent=2))
