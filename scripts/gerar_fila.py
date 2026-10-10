import csv
import random
from pathlib import Path

SEMENTE = 20261009
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "plano_162_execucoes.csv"

CENARIOS = [("site", "SITE"), ("jogo", "JOGO"), ("app", "APP")]
HARNESSES = [("opencode", "OPENCODE"), ("codex", "CODEX"), ("claude-code", "CLAUDE")]
MODELOS = [
    ("GPT-6 Luna", "LUNA", "gpt-6-luna", "openai"),
    ("Claude Haiku 5.5", "HAIKU", "claude-haiku-5-5", "anthropic"),
    ("DeepSeek V4.1 Flash", "DEEPSEEK", "deepseek-v4.1-flash", "relace"),
]
PROMPTS = [1, 2, 3]

ETAPAS = [
    (1, "site", 1, "R1"),
    (2, "jogo", 1, "R1"),
    (3, "app", 1, "R1"),
    (4, "site", 2, "R2"),
    (5, "jogo", 2, "R2"),
    (6, "app", 2, "R2"),
]


def bloco(cenario_chave, cenario_rotulo, repeticao):
    linhas = []
    for h, h_rot in HARNESSES:
        for _, m_rot, m_id, prov in MODELOS:
            for p in PROMPTS:
                linhas.append({
                    "cenario": cenario_chave,
                    "harness": h,
                    "modelo_rotulo": m_rot,
                    "modelo_id": m_id,
                    "provedor": prov,
                    "prompt": p,
                    "repeticao": repeticao,
                    "run_id": f"{cenario_rotulo.upper()}-{h_rot}-{m_rot}-P{p}-R{repeticao:02d}",
                })
    assert len(linhas) == 27
    return linhas


def main():
    rng = random.Random(SEMENTE)
    cenario_rotulo = dict(CENARIOS)
    saida = []
    ordem = 0
    for etapa, cen, rep, rotulo_rep in ETAPAS:
        linhas = bloco(cen, cenario_rotulo[cen], rep)
        rng.shuffle(linhas)
        condicional = "nao" if rotulo_rep == "R1" else "sim"
        for linha in linhas:
            ordem += 1
            linha.update({
                "ordem": ordem,
                "etapa": etapa,
                "condicional": condicional,
                "status": "planejada",
            })
            saida.append(linha)

    assert len(saida) == 162
    assert len({r["run_id"] for r in saida}) == 162

    campos = ["ordem", "etapa", "condicional", "run_id", "cenario", "harness",
              "modelo_rotulo", "modelo_id", "provedor", "prompt", "repeticao", "status"]
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(saida)
    print(f"{len(saida)} linhas -> {SAIDA}")


if __name__ == "__main__":
    main()
