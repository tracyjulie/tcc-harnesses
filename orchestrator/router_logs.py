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
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

MARGEM_SEGUNDOS = 20
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
    """Modelo como o 9router registra: <org>/<slug> (sem o prefixo openrouter/)."""
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
        "modelo_esperado": modelo_esperado,
    }


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
        "modelo_esperado": esperado,
        "contaminacao": sorted(m for m in modelos if m != esperado),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 5:
        sys.exit("uso: python orchestrator/router_logs.py inicio_iso fim_iso provedor modelo_id")
    print(json.dumps(agregar_janela(*sys.argv[1:]), ensure_ascii=False, indent=2))
