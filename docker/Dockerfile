# Dockerfile - imagem base do experimento
FROM python:3.10.10-slim

# ferramentas minimas de sistema que os harnesses costumam precisar
RUN echo "deb http://archive.debian.org/debian bullseye main" > /etc/apt/sources.list && \
    apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# instala o gerenciador de pacotes Node, necessario para alguns harnesses de CLI
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs

# --- instalacao dos tres harnesses (ajuste para o comando oficial de cada um) ---
RUN npm install -g @anthropic-ai/claude-code@2.1.197
RUN npm install -g @openai/codex@0.160.0
RUN npm install -g opencode-ai@1.18.34

# usuario nao-root, HOME descartavel (ver Passo 6)
RUN useradd -m executor
USER executor
WORKDIR /home/executor

# ponto de entrada: o container fica pronto para receber comandos
CMD ["/bin/bash"]
