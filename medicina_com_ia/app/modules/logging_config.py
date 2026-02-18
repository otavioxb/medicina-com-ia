# app/modules/logging_config.py
from loguru import logger
from pathlib import Path
import os

# Diretório absoluto da aplicação (funciona no host e no container)
base_dir = Path(__file__).resolve().parent.parent  # <- Isso vai até /app
log_dir = base_dir / "logs"
log_dir.mkdir(exist_ok=True)

# Remove handlers anteriores
logger.remove()

# Adiciona log com fuso horário de Brasília
logger.add(
    log_dir / "app.log",  # agora é /app/logs/app.log com base_dir explícito
    rotation="1 day",
    retention="30 days",
    level="INFO",
    serialize=True,
    backtrace=True,
    diagnose=True,
    enqueue=True,
    timezone="America/Sao_Paulo"
)

# Exporta logger
app_logger = logger