# Dockerfile - imagem base do experimento
# Usada tanto para as rodadas do agente quanto como contêiner do avaliador
# independente (Node 22 + libs do Chromium para o Playwright).
FROM python:3.10.10-slim

# ferramentas minimas de sistema que os harnesses costumam precisar
RUN echo "deb http://archive.debian.org/debian bullseye main" > /etc/apt/sources.list && \
    apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends \
        git curl ca-certificates \
        libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libdbus-1-3 libxcb1 libxkbcommon0 libx11-6 \
        libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 \
        libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 libxshmfence1 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Node 22 (NodeSource). ATENCAO: setup_22.x instala a 22.x mais recente do dia do build,
# entao o patch do Node NAO e fixado aqui. A imagem tcc-harnesses:v1 (id em VERSOES.txt) e a
# fonte da verdade (Node v22.23.3): nao reconstrua durante a coleta.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs

# --- instalacao dos tres harnesses (versoes pinadas, ver VERSOES.txt) ---
RUN npm install -g @anthropic-ai/claude-code@2.1.197
RUN npm install -g @openai/codex@0.160.0
RUN npm install -g opencode-ai@1.18.34

# usuario nao-root; o HOME real do agente e um diretorio descartavel por rodada
# (montado pelo runner em /home/executor)
RUN useradd -m executor
USER executor
WORKDIR /home/executor

# ponto de entrada: o container fica pronto para receber comandos
CMD ["/bin/bash"]
