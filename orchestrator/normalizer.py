#!/usr/bin/env python3
"""Normalizador de eventos dos harnesses (plano v2, secao 11).

Converte o JSON nativo de cada harness para os conceitos comuns
(`tool_call`, `file_change`, `command_execution`, `usage`, `run_finished`),
preservando integralmente o evento bruto em `raw`. Campo nao observado
recebe `null`, nunca zero.

Parsers: OpenCode (`part.type == "tool"`), Claude Code (`tool_use` em
`message.content`) e Codex (`item.completed` com `command_execution` ou
`file_change`). Os formatos do Codex e do Claude Code devem ser conferidos com
eventos reais no piloto (veja os testes em orchestrator/tests). A extracao de
uso varre o evento por nomes de chave conhecidos, de modo a funcionar mesmo
que o schema mude de posicao.

Uso:
    python orchestrator/normalizer.py <run_id> [...]   # normaliza eventos
    python orchestrator/normalizer.py --all            # todas as pastas em runs/
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUNS = RAIZ / "runs"

CAMPOS_COMUNS = (
    "tool_call",
    "file_change",
    "command_execution",
    "usage",
    "run_finished",
)

# Nomes de chave observados em respostas de modelos para uso e custo.
CHAVES_ENTRADA = ("input_tokens", "prompt_tokens", "inputTokenCount")
CHAVES_SAIDA = ("output_tokens", "completion_tokens", "outputTokenCount")
CHAVES_CACHE = ("cache_read_input_tokens", "cached_input_tokens", "cached_tokens", "cache_read_tokens")
CHAVES_CUSTO = ("total_cost_usd", "cost_usd", "cost")

NOMES_FERRAMENTA_EDICAO = {"edit", "write", "multiedit", "apply_patch", "patch"}
NOMES_FERRAMENTA_COMANDO = {"bash", "shell", "run", "exec", "command"}


def _vazio():
    return {campo: None for campo in CAMPOS_COMUNS}


def _varrer(obj, chaves):
    """Procura recursivamente o primeiro valor nao nulo para qualquer chave."""
    if isinstance(obj, dict):
        for chave in chaves:
            valor = obj.get(chave)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                return valor
        for valor in obj.values():
            achado = _varrer(valor, chaves)
            if achado is not None:
                return achado
    elif isinstance(obj, list):
        for item in obj:
            achado = _varrer(item, chaves)
            if achado is not None:
                return achado
    return None


def extrair_uso(raw):
    """Extrai tokens e custo de um evento, quando presentes."""
    entrada = _varrer(raw, CHAVES_ENTRADA)
    saida = _varrer(raw, CHAVES_SAIDA)
    cache = _varrer(raw, CHAVES_CACHE)
    custo = _varrer(raw, CHAVES_CUSTO)
    if entrada is None and saida is None and cache is None and custo is None:
        return None
    return {
        "input_tokens": entrada,
        "output_tokens": saida,
        "cached_tokens": cache,
        "cost_usd": custo,
    }


def extrair_uso_opencode(raw):
    """Uso dos eventos do OpenCode (part.tokens no step_finish)."""
    part = raw.get("part") if isinstance(raw, dict) else None
    tokens = part.get("tokens") if isinstance(part, dict) else None
    if not isinstance(tokens, dict):
        return None
    if tokens.get("input") is None and tokens.get("output") is None:
        return None
    cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
    return {
        "input_tokens": tokens.get("input"),
        "output_tokens": tokens.get("output"),
        "cached_tokens": cache.get("read"),
        "cost_usd": part.get("cost"),
    }


def _ferramenta(raw, harness=None):
    """Detecta uma chamada de ferramenta e classifica edicao/comando."""
    if not isinstance(raw, dict):
        return None, None, None

    nome = None
    entrada = None

    if harness == "opencode":
        part = raw.get("part")
        if isinstance(part, dict) and part.get("type") == "tool":
            nome = part.get("tool")
            estado = part.get("state")
            entrada = estado.get("input") if isinstance(estado, dict) else None
    else:
        # Codex (`codex exec --json`): ferramentas aparecem como itens concluidos
        # {"type":"item.completed","item":{"type":"command_execution"|"file_change"|...}}.
        # So `item.completed` conta (item.started repetiria a mesma chamada).
        item = raw.get("item") if isinstance(raw.get("item"), dict) else None
        if item is not None and raw.get("type") == "item.completed":
            tipo_item = item.get("type")
            if tipo_item == "command_execution":
                nome, entrada = "bash", {"command": item.get("command")}
            elif tipo_item == "file_change":
                mudancas = item.get("changes")
                caminho_item = mudancas[0].get("path") if isinstance(mudancas, list) and mudancas \
                    and isinstance(mudancas[0], dict) else None
                nome, entrada = "edit", {"path": caminho_item}
            elif tipo_item in ("mcp_tool_call", "web_search"):
                nome, entrada = tipo_item, item.get("arguments") or item.get("query")

    if nome is None and harness != "opencode":
        bloco = raw.get("tool_use") or raw.get("tool") or raw.get("tool_call")
        if isinstance(bloco, dict):
            nome = bloco.get("name") or bloco.get("tool")
            entrada = bloco.get("input") or bloco.get("arguments") or bloco.get("args")

        if nome is None and isinstance(raw.get("message"), dict):
            conteudo = raw["message"].get("content")
            if isinstance(conteudo, list):
                for item in conteudo:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        nome = item.get("name")
                        entrada = item.get("input")
                        break

        if nome is None and raw.get("type") in ("tool_use", "tool_call", "tool"):
            nome = raw.get("name")
            entrada = raw.get("input") or raw.get("arguments")

    if not isinstance(nome, str):
        return None, None, None

    nome_norm = nome.lower()
    tool_call = {"name": nome, "input": entrada}
    file_change = None
    command_execution = None

    if nome_norm in NOMES_FERRAMENTA_EDICAO or "edit" in nome_norm or "write" in nome_norm:
        caminho = None
        if isinstance(entrada, dict):
            caminho = (
                entrada.get("file_path")
                or entrada.get("filePath")
                or entrada.get("path")
                or entrada.get("filename")
            )
        file_change = {"tool": nome, "path": caminho}
    elif nome_norm in NOMES_FERRAMENTA_COMANDO or "bash" in nome_norm:
        comando = None
        if isinstance(entrada, dict):
            comando = entrada.get("command") or entrada.get("cmd")
        command_execution = {"tool": nome, "command": comando}

    return tool_call, file_change, command_execution


def _run_finished(raw):
    if not isinstance(raw, dict):
        return None
    tipo = str(raw.get("type", ""))
    subtipo = str(raw.get("subtype", ""))
    if tipo == "result" or "finished" in tipo or "completed" in tipo:
        return {
            "type": tipo or None,
            "subtype": subtipo or None,
            "is_error": raw.get("is_error"),
            "result": raw.get("result"),
        }
    return None


def normalizar_evento(raw, harness=None):
    """Converte um evento bruto no dicionario de campos comuns."""
    comum = _vazio()
    tool_call, file_change, command_execution = _ferramenta(raw, harness)
    comum["tool_call"] = tool_call
    comum["file_change"] = file_change
    comum["command_execution"] = command_execution
    if harness == "opencode":
        comum["usage"] = extrair_uso_opencode(raw) or extrair_uso(raw)
    else:
        comum["usage"] = extrair_uso(raw)
    comum["run_finished"] = _run_finished(raw)
    comum["raw"] = raw
    return comum


def normalizar_arquivo(events_path, saida_path, harness=None):
    """Normaliza um events.jsonl preservando os brutos; devolve a lista."""
    eventos = []
    linhas_invalidas = 0
    if events_path.exists():
        with events_path.open("r", encoding="utf-8", errors="replace") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    raw = json.loads(linha)
                except json.JSONDecodeError:
                    linhas_invalidas += 1
                    continue
                eventos.append(normalizar_evento(raw, harness))

    with saida_path.open("w", encoding="utf-8") as f:
        for evento in eventos:
            f.write(json.dumps(evento, ensure_ascii=False) + "\n")

    return eventos, linhas_invalidas


def agregar(eventos):
    """Resume os eventos normalizados para o summary.json."""
    tool_calls = 0
    testes_do_agente = 0
    palavras_teste = ("vitest", "playwright", "npm test", "npm run test", "tsc", "eslint", "node test")

    uso_total = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
    uso_visto = {"input_tokens": False, "output_tokens": False, "cached_tokens": False}
    custo_total = 0.0
    custo_visto = False

    for evento in eventos:
        if evento["tool_call"]:
            tool_calls += 1
            if evento["command_execution"]:
                comando = (evento["command_execution"] or {}).get("command") or ""
                if any(p in comando.lower() for p in palavras_teste):
                    testes_do_agente += 1
        uso = evento["usage"]
        if uso:
            for campo in uso_total:
                if uso.get(campo) is not None:
                    uso_total[campo] += uso[campo]
                    uso_visto[campo] = True
            if uso.get("cost_usd") is not None:
                custo_total += uso["cost_usd"]
                custo_visto = True

    def _ou_none(valor, visto):
        return valor if visto else None

    return {
        "tool_calls": tool_calls,
        "test_executions_by_agent": testes_do_agente,
        "input_tokens": _ou_none(uso_total["input_tokens"], uso_visto["input_tokens"]),
        "output_tokens": _ou_none(uso_total["output_tokens"], uso_visto["output_tokens"]),
        "cached_tokens": _ou_none(uso_total["cached_tokens"], uso_visto["cached_tokens"]),
        "cost_usd": round(custo_total, 6) if custo_visto else None,
    }


def normalizar_run(run_dir):
    """Normaliza uma pasta de rodada e devolve o agregado (ou None)."""
    events_path = run_dir / "events.jsonl"
    saida_path = run_dir / "normalizados.jsonl"
    harness = None
    manifest = run_dir / "manifest.json"
    if manifest.exists():
        try:
            harness = json.loads(manifest.read_text(encoding="utf-8")).get("harness")
        except (json.JSONDecodeError, OSError):
            harness = None
    eventos, invalidas = normalizar_arquivo(events_path, saida_path, harness)
    agregado = agregar(eventos)
    agregado["eventos_lidos"] = len(eventos)
    agregado["linhas_invalidas"] = invalidas
    return agregado


def _runs_alvo(argumentos):
    if argumentos and argumentos[0] == "--all":
        if not RUNS.exists():
            return []
        return sorted(p for p in RUNS.iterdir() if p.is_dir())
    return [RUNS / run_id for run_id in argumentos]


def main():
    argumentos = sys.argv[1:]
    if not argumentos:
        sys.exit(__doc__)

    alvos = _runs_alvo(argumentos)
    if not alvos:
        sys.exit("nenhuma pasta de rodada encontrada")

    for run_dir in alvos:
        if not run_dir.exists():
            print(f"[ausente] {run_dir.name}")
            continue
        agregado = normalizar_run(run_dir)
        print(
            f"[ok] {run_dir.name}: {agregado['eventos_lidos']} eventos, "
            f"{agregado['tool_calls']} chamadas de ferramenta, "
            f"{agregado['linhas_invalidas']} linhas invalidas"
        )


if __name__ == "__main__":
    main()
