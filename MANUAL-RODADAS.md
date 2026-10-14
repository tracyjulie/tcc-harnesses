# Manual de rodadas

Procedimento para o piloto e para a coleta definitiva, conforme o plano v2 (§7.8 a §7.14). Registro de 12/10/2026. Siga na ordem. Nenhuma etapa começa sem a anterior estar auditada. Tudo o que está decidido fica em `protocolo/preregistro.md`; as versões, em `VERSOES.txt`.

## 1. Preparação da máquina

1. Ubuntu Server com Docker. Imagem fixa (já construída; não reconstruir durante a coleta):
   ```
   docker build -t tcc-harnesses:v1 -f docker/Dockerfile .
   ```
2. Conferir as versões dentro da imagem contra `VERSOES.txt`:
   ```
   docker run --rm tcc-harnesses:v1 bash -lc "python3 --version; node --version; npm --version; claude --version; codex --version; opencode --version"
   ```
3. Rede isolada, sem saída para a internet:
   ```
   docker network create --internal rede-experimento
   docker network inspect rede-experimento -f 'internal={{.Internal}} gateway={{(index .IPAM.Config 0).Gateway}}'
   ```
   Esperado: `internal=true`. Se a rede for recriada, o IP do gateway muda; o runner o descobre sozinho.
4. 9router (v0.5.95), em `tmux`, **somente em 127.0.0.1**, com logs de requisição:
   ```
   HOSTNAME=127.0.0.1 PORT=20128 ENABLE_REQUEST_LOGS=true 9router
   ```
5. Proxy que expõe só `/v1/` para a rede do experimento (o painel do 9router fica inacessível ao agente):
   ```
   sudo apt install -y nginx
   echo 'net.ipv4.ip_nonlocal_bind=1' | sudo tee /etc/sysctl.d/99-tcc.conf && sudo sysctl --system
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo tee /etc/nginx/conf.d/tcc-gateway.conf >/dev/null <<'CONF'
   server {
     listen 172.18.0.1:20129;
     location /v1/ {
       proxy_pass http://127.0.0.1:20128;
       proxy_http_version 1.1;
       proxy_set_header Connection "";
       proxy_buffering off;
       proxy_read_timeout 1800s;
     }
     location / { return 404; }
   }
   CONF
   sudo nginx -t && sudo systemctl restart nginx
   export TCC_GATEWAY_PORT=20129     # o runner passa a usar a porta do proxy
   ```
   Teste (de dentro de um contêiner do experimento): `/v1/models` com a chave responde 200; `/` responde 404; a porta 20128 do gateway recusa a conexão.
6. Desligar em `Dashboard → Endpoint → Token Saver/Ponytail` os recursos que alteram o corpo da requisição (RTK, Caveman, Ponytail, Headroom) e guardar a captura em `protocolo/evidencias/`.
7. Provar o provedor de cada modelo: `python3 scripts/verificar_provedor.py` (esperado: DeepSeek → Relace, GPT-6 Luna → OpenAI, Haiku → Anthropic, em todas as chamadas). Guardar a saída em `protocolo/evidencias/provedor-<data>.txt`.
8. Rodar os testes do orquestrador: `python3 -m unittest discover -s orchestrator/tests -v` (esperado: `OK`).
9. Gerar o congelamento do ambiente (uma vez, com tudo validado): `python3 orchestrator/preflight.py --gerar-congelamento`. Depois, antes de qualquer sessão de coleta: `python3 orchestrator/preflight.py --verificar-ambiente` (esperado: todas as linhas `OK`).

## 2. Piloto de compatibilidade (bloqueante)

O piloto não entra nos resultados finais. Usa tarefas mínimas próprias, não os starters nem os nove prompts (§7.12). Comando: `python3 orchestrator/runner.py --pilot` (opções `--pilot-harness` e `--pilot-model`). Cada par roda cinco verificações, **com evidência**:

| # | Verificação | Passa quando |
|---|---|---|
| 1 | Consulta simples | saída 0, a resposta `OK` aparece nos eventos e o 9router mostra uso do modelo-alvo |
| 2 | Leitura | o conteúdo do README (`Projeto piloto`) aparece nos eventos |
| 3 | Edição | `saida.txt` contém exatamente `PILOTO` |
| 4 | Execução e autocorreção | o agente rodou `node test.mjs`, corrigiu `soma.mjs` e o teste passa |
| 5 | Eventos e uso | há eventos, tokens no 9router e chamadas de ferramenta reconhecidas (> 0) |

Cada verificação usa uma pasta própria (`runs/PILOTO-<harness>-<modelo>-<n>`) e suas evidências são copiadas para `protocolo/evidencias/piloto/`. O resultado vai para `protocolo/compatibilidade-piloto.csv` (inclui `tipo_integracao`, modelo e provedor efetivos, endpoint e o motivo de cada falha).

Depois do piloto:
- Pares que passam nas cinco: `compativel`. Pares que falham: `protocol_incompatible`, documentado; nunca viram nota zero.
- Decidir Plano A ou B (§7.12) e registrar em `protocolo/preregistro.md` antes da Etapa 1.
- Registrar o consumo de tokens do piloto.
- Se a verificação 5 reprovar para um harness por "chamadas de ferramenta = 0", o parser do normalizador não reconhece o formato real: guarde o `events.jsonl` em `orchestrator/tests/amostras/` e corrija `normalizer.py`.

## 3. Fila de execução

A fila fica em `dados/plano_162_execucoes.csv`, gerada por `scripts/gerar_fila.py` com semente `20261009`. Não editar a fila à mão (só o runner atualiza a coluna `status`). Regenerar produz o mesmo arquivo.

Colunas: `ordem`, `etapa`, `condicional`, `run_id`, `cenario`, `harness`, `modelo_rotulo`, `modelo_id`, `provedor`, `prompt`, `repeticao`, `status`.

| Etapa | Escopo | Linhas | Condição para iniciar |
|---|---|---|---|
| 1 | R1 · site | 27 | Piloto concluído, protocolo congelado |
| — | Verificação 1 | | Etapa 1 auditada |
| 2 | R1 · jogo | 27 | Verificação 1 aprovada |
| — | Verificação 2 | | Etapa 2 auditada |
| 3 | R1 · app | 27 | Verificação 2 aprovada |
| — | Verificação 3 | | 81 execuções R1 completas e auditadas |
| 4 | R2 · site | 27 | Verificação 3 + saldo suficiente |
| 5 | R2 · jogo | 27 | Verificação 4 + saldo suficiente |
| 6 | R2 · app | 27 | Verificação 5 + saldo suficiente |

A ordem dentro de cada etapa é sorteada e registrada. Não altere a ordem à mão.

## 4. O que o runner faz em cada rodada

`python3 orchestrator/runner.py --etapa N` repete, para cada linha da fila:

1. Prepara o workspace novo a partir de `fixtures/<cenario>-base/` (nunca reaproveita) e instala as dependências (`npm ci`, único passo com internet).
2. Cria o HOME descartável da rodada (sem `.claude`, `.codex`, `CLAUDE.md`).
3. **Pré-voo** (`orchestrator/preflight.py`): imagem e versões iguais ao congelamento, HOME limpo, workspace igual ao starter, lockfile e prompt congelados, rede interna e sem internet, roteador respondendo com a rota do modelo, nenhum contêiner `tcc-*` ativo, repositório sem alterações soltas, espaço em disco. Se algo reprovar, a fila **para** sem gastar nada.
4. Grava `manifest.json` (horário UTC, versões lidas do contêiner, id da imagem, hashes, limites, política de rede).
5. Executa o harness em contêiner novo (rede isolada, 2 CPUs, 4 GB, `--cap-drop ALL`), com **tempo máximo de 1200 s** e **teto de custo de US$ 2,00** vigiado a cada 15 s. Ao estourar, o contêiner é encerrado (`docker kill`) e o desfecho é `timeout`.
6. Congela o `source-snapshot/`, troca a chave do roteador por `***` nos artefatos e calcula o hash.
7. Classifica o desfecho (`runtime_status`).
8. Só roda o avaliador se há artefato: o agente terminou ou estourou o limite, ou o snapshot difere do starter. Falha de integração sem artefato fica com as notas `null` e `avaliado=false`.
9. Normaliza os eventos, lê custo e tokens do 9router e grava `summary.json` e a linha em `dados/resultados.csv`.

Não intervir durante a rodada. Pedidos de orientação do agente são registrados, não respondidos.

## 5. Capturas por rodada

```
runs/<run_id>/
├── manifest.json
├── preflight.json
├── prompt.txt
├── events.jsonl
├── stderr.log
├── normalizados.jsonl
├── source-snapshot/
├── source-snapshot.sha256
├── avaliacao-resultados/ · avaliacao.log
├── test-results.json            (ausente quando a rodada não foi avaliada)
└── summary.json
```

Dado não observado é `null`. Nunca preencher com zero. O banco do 9router (`~/.9router/db/data.sqlite`) é a única fonte de custo e fica fora do Git: **copie-o ao fim de cada etapa** para um backup.

## 6. Classificação do desfecho

`runtime_status`: `completed` (o agente encerrou, código 0), `timeout` (tempo ou custo; motivo em `notes`: `time_limit` ou `cost_limit`; censurado, nunca sucesso), `provider_error` (erro de API, só quando o código de saída != 0), `harness_error` (falha do ambiente ou do harness), `protocol_incompatible`, `aborted` (inclui `credit_exhausted`).

Falhas de integração não são evidência de qualidade e vão para série própria. Interrupção por crédito: registrar `aborted/credit_exhausted`, preservar o workspace parcial e reexecutar do zero (`--run-id <ID> --force`; a tentativa original vira `summary.attempt1.json`) ou declarar não executada.

## 7. Verificações entre etapas

Ao fim de cada etapa, registrar em `protocolo/checkpoints.md`:
1. **Consumo observado:** tokens e custo da etapa, por modelo, contra o saldo restante.
2. **Projeção da próxima etapa:** a complexidade crescente aumenta tokens por rodada; use a razão observada entre cenários e a margem de 20%.
3. **Integridade:** todas as 27 execuções têm manifesto, logs, snapshot e `summary.json`. Falhas classificadas.
4. **Decisão:** prosseguir, ajustar ou encerrar, com data e justificativa.

Comando de auditoria (exemplo da etapa 1; não deve imprimir nada):
```
for id in $(awk -F, 'NR>1 && $2==1 {print $4}' dados/plano_162_execucoes.csv); do
  for f in manifest.json prompt.txt events.jsonl stderr.log source-snapshot summary.json; do
    [ -e runs/$id/$f ] || echo "FALTA $id/$f"; done; done
```

## 8. Integridade antes de analisar

- Cada `run_id` da fila tem uma pasta em `runs/`.
- Nenhuma célula de R2 é tratada como R1. A estabilidade só existe onde há R1 e R2. Reportar `n` real por célula.
- Provedor divergente do fixado (`provider_mismatch`) é sinalizado e entra na análise de sensibilidade.
- `criterios_nao_observados` alto (jogo e app) é reportado por célula; sempre mostrar a nota observada e a conservadora.
