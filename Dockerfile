# Usa uma imagem leve e estável do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /home/site/wwwroot

# Instala dependências do sistema necessárias para pacotes de IA
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas o requirements primeiro (para otimizar o cache)
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o restante do seu código para dentro do container
COPY . .

# Expõe a porta que o Azure usa
EXPOSE 8000

# Comando definitivo para rodar o Gunicorn + Uvicorn
# O --chdir garante que o Python ache a pasta 'app'
CMD ["gunicorn", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "600", "--chdir", "/home/site/wwwroot", "app.main:app"]