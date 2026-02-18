# Dockerfile

FROM python:3.11-slim

# Instalações básicas
RUN apt-get update && apt-get install -y build-essential libpq-dev ffmpeg && apt-get clean

# Define o diretório da aplicação
WORKDIR /app

# Copia os arquivos
COPY requirements.txt .

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .
ENV PYTHONPATH=/app
# Expondo a porta
EXPOSE 8000

# Comando para iniciar a aplicação
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]