import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent


def qualidade(criterios, so_observados=True):
    num = den = 0
    for c in criterios:
        p = c["passou"]
        if p is None:
            if so_observados:
                continue
            p = 0
        num += c["peso"] * p
        den += c["peso"]
    return round(100 * num / den, 2) if den else None


def main():
    if len(sys.argv) != 4:
        sys.exit("uso: python avaliacao/score.py <test-results.json> <site|jogo|app> <1|2|3>")
    caminho, cenario, prompt = sys.argv[1], sys.argv[2], sys.argv[3]
    resultado = json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))
    mapa = json.loads((RAIZ / "mapeamento-criterio-prompt.json").read_text(encoding="utf-8"))
    criterios = resultado["criterios"]
    ids_a = set(mapa["mapeamento"][cenario][prompt])
    aderencia = [c for c in criterios if c["id"] in ids_a]

    saida = {
        "cenario": cenario,
        "prompt": prompt,
        "aviso_mapeamento": mapa["status"],
        "referencia_B": {
            "observada": qualidade(criterios),
            "conservadora_nulos_como_zero": qualidade(criterios, so_observados=False),
            "nao_observados": sum(1 for c in criterios if c["passou"] is None),
            "nao_verificaveis_automaticamente": sum(1 for c in criterios if not c["verificavel"]),
        },
        "aderencia_A": {
            "observada": qualidade(aderencia),
            "conservadora_nulos_como_zero": qualidade(aderencia, so_observados=False),
            "criterios_no_denominador": len(aderencia),
            "nao_observados": sum(1 for c in aderencia if c["passou"] is None),
        },
    }
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
