"""Testes do orquestrador. Nao usam Docker de verdade e nao gastam credito.

Rodar (na raiz do repositorio):
    python3 -m unittest discover -s orchestrator/tests -v

Cada teste cobre uma correcao (B1..B4, I1..I3 do plano de contingencia).
"""
import csv
import http.server
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
sys.path.insert(0, str(RAIZ / "orchestrator"))

import preflight  # noqa: E402
import router_logs  # noqa: E402
import runner  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tcc-teste-"))
        bindir = self.tmp / "bin"
        bindir.mkdir()
        (bindir / "docker").symlink_to(AQUI / "docker_falso.py")
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{bindir}:{self.old_path}"
        os.environ["FAKE_DOCKER_STATE"] = str(self.tmp / "estado")
        for v in ("FAKE_RUN_RC", "FAKE_EGRESS_OK", "FAKE_NET_INTERNAL", "FAKE_IMAGE_ID"):
            os.environ.pop(v, None)

    def tearDown(self):
        # derruba qualquer "conteiner" que sobrou
        runner._matar_conteiner("x")
        for f in (self.tmp / "estado").glob("*.pid"):
            runner._matar_conteiner(f.stem)
        os.environ["PATH"] = self.old_path
        shutil.rmtree(self.tmp, ignore_errors=True)

    def args(self, *extra):
        return runner.montar_parser().parse_args(list(extra))

    def vivos(self):
        saida = runner.subprocess.run(["docker", "ps", "--filter", "name=tcc-", "-q"],
                                      capture_output=True, text=True).stdout
        return saida.split()


class TestB1Timeout(Base):
    def test_timeout_mata_o_conteiner(self):
        (self.tmp / "ws").mkdir(); (self.tmp / "home").mkdir(); (self.tmp / "run").mkdir()
        a = self.args("--time-limit", "3")
        res = runner.executar_no_container(a, self.tmp / "ws", self.tmp / "home",
                                           "sleep 600", self.tmp / "run")
        self.assertTrue(res["timed_out"])
        time.sleep(0.5)
        self.assertEqual(self.vivos(), [], "o conteiner sobreviveu ao timeout")


class TestB2TetoDeCusto(Base):
    def banco(self):
        d = self.tmp / "router"; d.mkdir()
        con = sqlite3.connect(d / "data.sqlite")
        con.execute("create table usageHistory(timestamp text, provider text, model text, endpoint text,"
                    " promptTokens int, completionTokens int, cost real, status text, tokens text)")
        con.commit()
        os.environ["TCC_LOGS_ROUTER"] = str(d)
        return con

    def test_padrao_do_preregistro(self):
        a = self.args()
        self.assertEqual(a.cost_limit, 2.0)
        self.assertEqual(a.time_limit, 1200)

    def test_vigia_mata_ao_passar_do_teto(self):
        self.banco().close()
        (self.tmp / "ws").mkdir(); (self.tmp / "home").mkdir(); (self.tmp / "run").mkdir()
        a = self.args("--time-limit", "60", "--cost-poll", "1")
        inicio = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        def gastar():
            time.sleep(2)
            ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
            c2 = sqlite3.connect(os.environ["TCC_LOGS_ROUTER"] + "/data.sqlite")
            c2.execute("insert into usageHistory values(?,?,?,?,?,?,?,?,?)",
                       (ts, "openrouter", "deepseek/deepseek-v4.1-flash", "/v1/chat/completions",
                        100, 100, 2.5, "ok", "{}"))
            c2.commit(); c2.close()
        threading.Thread(target=gastar, daemon=True).start()
        t0 = time.monotonic()
        res = runner.executar_no_container(
            a, self.tmp / "ws", self.tmp / "home", "sleep 600", self.tmp / "run",
            cost_watch={"inicio": inicio, "provedor": "relace",
                        "modelo_id": "deepseek-v4.1-flash", "limite": 2.0})
        self.assertEqual(res["limit_reason"], "cost_limit")
        self.assertLess(time.monotonic() - t0, 30)
        time.sleep(0.5)
        self.assertEqual(self.vivos(), [])
        self.assertEqual(runner.classificar_status(res, "", "")[0:2], ("timeout", "cost_limit"))


class TestB3Haiku(Base):
    def test_custo_do_haiku_nao_some(self):
        d = self.tmp / "router"; d.mkdir()
        con = sqlite3.connect(d / "data.sqlite")
        con.execute("create table usageHistory(timestamp text, provider text, model text, endpoint text,"
                    " promptTokens int, completionTokens int, cost real, status text, tokens text)")
        con.execute("insert into usageHistory values('2026-10-12T12:00:10.000Z','openrouter',"
                    "'anthropic/claude-haiku-5.5','/v1/messages',1000,200,0.01,'ok','{}')")
        con.commit(); con.close()
        os.environ["TCC_LOGS_ROUTER"] = str(d)
        o = router_logs.agregar_janela("2026-10-12T12:00:00Z", "2026-10-12T12:01:00Z",
                                       "anthropic", "claude-haiku-5-5")
        self.assertEqual(o["modelo_esperado"], "anthropic/claude-haiku-5.5")
        self.assertEqual(o["cost_usd"], 0.01)
        self.assertEqual(o["contaminacao"], [])

    def test_os_tres_modelos_resolvem(self):
        self.assertEqual(router_logs._modelo_esperado("openai", "gpt-6-luna"), "openai/gpt-6-luna")
        self.assertEqual(router_logs._modelo_esperado("relace", "deepseek-v4.1-flash"),
                         "deepseek/deepseek-v4.1-flash")


class TestI3Classificacao(Base):
    def test_casos(self):
        c = runner.classificar_status
        self.assertEqual(c({"timed_out": False, "returncode": 0}, "provider: 9router\nmodel: x"),
                         ("completed", None))
        self.assertEqual(c({"timed_out": False, "returncode": 1}, "HTTP 429 Too Many Requests"),
                         ("provider_error", None))
        self.assertEqual(c({"timed_out": False, "returncode": 1}, "insufficient credits"),
                         ("aborted", "credit_exhausted"))
        self.assertEqual(c({"timed_out": False, "returncode": 1}, "Segmentation fault"),
                         ("harness_error", None))
        self.assertEqual(c({"timed_out": True, "returncode": None}, ""), ("timeout", "time_limit"))


class TestB4SemArtefato(Base):
    """Falha de integracao sem artefato nao pode virar nota de qualidade."""

    def preparar(self):
        runner.RUNS = self.tmp / "runs"; runner.RUNS.mkdir()
        runner.RESULTADOS = self.tmp / "resultados.csv"
        runner.FILA = self.tmp / "fila.csv"
        shutil.copy(RAIZ / "dados" / "plano_162_execucoes.csv", runner.FILA)
        self.addCleanup(self.restaurar)

    def restaurar(self):
        runner.RUNS = RAIZ / "runs"
        runner.RESULTADOS = RAIZ / "dados" / "resultados.csv"
        runner.FILA = RAIZ / "dados" / "plano_162_execucoes.csv"

    def test_falha_sem_artefato_nao_e_avaliada(self):
        self.preparar()
        os.environ["FAKE_RUN_RC"] = "1"
        a = self.args("--no-gateway", "--npm-deps", "skip", "--skip-preflight")
        linha = runner.ler_fila()[0]
        runner.processar_linha(linha, a, runner.ler_versoes(), runner.carregar_modelos())
        resumo = json.loads((runner.RUNS / linha["run_id"] / "summary.json").read_text())
        self.assertEqual(resumo["runtime_status"], "harness_error")
        self.assertFalse(resumo["artefato_modificado"])
        self.assertFalse(resumo["avaliado"])
        self.assertIsNone(resumo["reference_quality"])
        self.assertIsNone(resumo["prompt_adherence"])
        self.assertEqual(resumo["etapa"], 1)
        self.assertEqual(resumo["tipo_integracao"], "rota_esperada")

    def test_resultados_csv_identifica_a_rodada_e_usa_lf(self):
        self.preparar()
        a = self.args("--no-gateway", "--npm-deps", "skip", "--skip-preflight")
        linha = runner.ler_fila()[0]
        runner.processar_linha(linha, a, runner.ler_versoes(), runner.carregar_modelos())
        bruto = runner.RESULTADOS.read_bytes()
        self.assertNotIn(b"\r\n", bruto)
        with runner.RESULTADOS.open(newline="", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
        self.assertEqual(linhas[0]["scenario"], "site")
        self.assertEqual(linhas[0]["harness"], "opencode")
        self.assertEqual(linhas[0]["model_label"], "LUNA")
        self.assertEqual(linhas[0]["prompt_level"], "2")
        # a fila tambem continua com LF
        self.assertNotIn(b"\r\n", runner.FILA.read_bytes())

    def test_chave_nao_fica_nos_artefatos(self):
        d = self.tmp / "x"; d.mkdir()
        (d / "a.json").write_text('{"k": "SEGREDO123"}')
        (d / "b.log").write_text("sem nada")
        self.assertEqual(runner.redigir_chave(d, "SEGREDO123"), 1)
        self.assertNotIn("SEGREDO123", (d / "a.json").read_text())


class TestPreflight(Base):
    def setUp(self):
        super().setUp()
        preflight.CONGELAMENTO = self.tmp / "congelamento.json"
        self.a = self.args()
        self.info = {"image_id": "sha256:imagemfalsa",
                     "versoes": {"node": "v22.23.3", "claude-code": "2.1.197 (Claude Code)",
                                 "codex": "codex-cli 0.160.0", "opencode": "1.18.34"}}
        preflight.gerar_congelamento(self.a, self.info)
        self.srv = self.sobe_gateway()
        self.a.gateway_url = f"http://127.0.0.1:{self.srv.server_port}"
        self.a.api_key = "k"
        self.linha = {"cenario": "site", "prompt": "1"}
        self.ws = self.tmp / "ws"; shutil.copytree(RAIZ / "fixtures" / "site-base", self.ws)
        self.home = self.tmp / "home"; self.home.mkdir()
        (self.home / "opencode.json").write_text("{}")
        self.modelo = "9router/openrouter/openai/gpt-6-luna"
        self.prompt = RAIZ / "prompts" / "site-p1.txt"

    def tearDown(self):
        self.srv.shutdown()
        super().tearDown()

    def sobe_gateway(self):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                corpo = json.dumps({"data": [{"id": "openrouter/openai/gpt-6-luna"}]}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(corpo)))
                self.end_headers(); self.wfile.write(corpo)
            def log_message(self, *a): pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv

    def rodar(self):
        r = preflight.verificar(self.a, self.linha, self.ws, self.home, self.prompt,
                                self.modelo, self.info)
        return {i["item"]: i for i in r}

    def falhas(self, r):
        # o item de git depende do estado do seu repositorio durante o desenvolvimento
        return [n for n, i in r.items() if not i["ok"] and not n.startswith("repositorio")]

    def test_ambiente_correto_passa(self):
        self.assertEqual(self.falhas(self.rodar()), [])

    def test_home_com_claude_md_reprova(self):
        (self.home / "CLAUDE.md").write_text("regra pessoal")
        self.assertIn("HOME da rodada limpo", self.falhas(self.rodar()))

    def test_internet_acessivel_reprova(self):
        os.environ["FAKE_EGRESS_OK"] = "1"
        self.assertIn("sem saida para a internet", self.falhas(self.rodar()))

    def test_imagem_diferente_reprova(self):
        self.info = dict(self.info, image_id="sha256:outra")
        self.assertIn("imagem (id)", self.falhas(self.rodar()))

    def test_workspace_alterado_reprova(self):
        (self.ws / "src" / "extra.ts").write_text("// sobra de outra rodada")
        self.assertIn("workspace igual ao starter", self.falhas(self.rodar()))

    def test_conteiner_orfao_reprova(self):
        self.a_run = runner.subprocess.Popen(["docker", "run", "--name", "tcc-orfao", "x", "bash", "-lc", "sleep 600"])
        time.sleep(1)
        try:
            self.assertIn("nenhum conteiner tcc-* ativo", self.falhas(self.rodar()))
        finally:
            runner._matar_conteiner("tcc-orfao")
            self.a_run.wait(timeout=10)

    def test_sem_congelamento_reprova(self):
        preflight.CONGELAMENTO.unlink()
        r = preflight.verificar(self.a, self.linha, self.ws, self.home, self.prompt, self.modelo, self.info)
        self.assertFalse(r[0]["ok"])


class TestNormalizador(Base):
    """Formatos de evento conhecidos. ATENCAO: os de Codex e Claude Code abaixo foram escritos
    a partir da documentacao dos formatos; confirme com eventos REAIS no piloto
    (guarde um events.jsonl de cada harness em orchestrator/tests/amostras/)."""

    def test_codex_item_concluido_conta_uma_vez(self):
        import normalizer
        iniciado = {"type": "item.started", "item": {"type": "command_execution", "command": "node test.mjs"}}
        concluido = {"type": "item.completed", "item": {"type": "command_execution",
                     "command": "node test.mjs", "exit_code": 0}}
        edicao = {"type": "item.completed", "item": {"type": "file_change",
                  "changes": [{"path": "soma.mjs", "kind": "update"}]}}
        eventos = [normalizer.normalizar_evento(e, "codex") for e in (iniciado, concluido, edicao)]
        agregado = normalizer.agregar(eventos)
        self.assertEqual(agregado["tool_calls"], 2)
        self.assertEqual(agregado["test_executions_by_agent"], 1)

    def test_claude_code_tool_use(self):
        import normalizer
        e = {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "npm run build"}}]}}
        agregado = normalizer.agregar([normalizer.normalizar_evento(e, "claude-code")])
        self.assertEqual(agregado["tool_calls"], 1)

    def test_opencode_tool(self):
        import normalizer
        e = {"part": {"type": "tool", "tool": "edit", "state": {"input": {"filePath": "a.ts"}}}}
        agregado = normalizer.agregar([normalizer.normalizar_evento(e, "opencode")])
        self.assertEqual(agregado["tool_calls"], 1)


class TestEndurecimento(Base):
    def test_docker_run_tem_limites_e_nome(self):
        a = self.args()
        cmd = runner.montar_docker(a, Path("/w"), Path("/h"), "echo oi", "tcc-x")
        juntos = " ".join(cmd)
        for trecho in ("--name tcc-x", "--cpus 2", "--memory 4g", "--pids-limit 512",
                       "--cap-drop ALL", "--security-opt no-new-privileges"):
            self.assertIn(trecho, juntos)


if __name__ == "__main__":
    unittest.main()
