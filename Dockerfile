# Usa uma imagem base oficial do Python, versão slim para ser mais leve
FROM python:3.10.12-slim

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    python3-dev \
	procps \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho da aplicação
WORKDIR /usr/src/app	
	
# Copia somente o arquivo de dependências
COPY requirements.txt .

# Instala as dependências do Python de forma otimizada
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir uvicorn && \
	pip install --no-cache-dir aioredis && \
	pip install --no-cache-dir python-dotenv && \
    python -m spacy download en_core_web_sm	

# Cria um diretório para armazenar os scripts de inicialização e reinício
RUN mkdir -p /home/scripts

# Expõe as portas necessárias
EXPOSE 9000 9001 9002 9003 9004 9005

