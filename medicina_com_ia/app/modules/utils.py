# app/modules/utils.py
import audioop
from app.db.database import get_db_connection, release_db_connection
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from loguru import logger
import json
from io import BytesIO

log_list = []

def add_log(message: str, level: str = "info", **context):
        # Construa a mensagem com contexto
    context_str = f" | Contexto: {context}" if context else ""
    final_msg = f"{message}{context_str}"

    # Grava no arquivo
    if level == "debug":
        logger.debug(final_msg)
    elif level == "info":
        logger.info(final_msg)
    elif level == "warning":
        logger.warning(final_msg)
    elif level == "error":
        logger.error(final_msg)
    elif level == "critical":
        logger.critical(final_msg)

    print(final_msg)
    log_list.append(final_msg)

    # Grava no banco (context pode ser vazio)
    save_log_to_db(level, message, context or {})


def is_silent(audio_data: bytes) -> bool:
    try:
        audio = AudioSegment.from_file(BytesIO(audio_data), format="webm")  # tente "ogg" se necessário
        non_silent = detect_nonsilent(audio, min_silence_len=500, silence_thresh=-45)
        # add_log(f"[Pydub] Segmentos não silenciosos: {non_silent}", "debug")
        return len(non_silent) == 0
    except Exception as e:
        # Se não conseguimos decodificar o chunk (webm), não dá para inferir silêncio de forma confiável.
        # Preferimos NÃO bloquear a transcrição (retorna False = não é silêncio).
        add_log(f"Falha ao calcular silêncio (decode): {e}", level="warning")
        return False

def formatar_duracao(segundos: int) -> str:
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segundos = segundos % 60
    return f"{int(horas):02}:{int(minutos):02}:{int(segundos):02}"

def save_log_to_db(level: str, message: str, context: dict = None):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO logs (level, message, context)
            VALUES (%s, %s, %s)
        """, (level.upper(), message, json.dumps(context or {})))
        connection.commit()
    except Exception as e:
        print(f"[LOGGING FALHOU] Não foi possível salvar log no banco: {e}")
    finally:
        try:
            cursor.close()
            release_db_connection(connection)
        except:
            pass


def marcar_sessao_como_inativa(sessao_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE sessions SET session_status = FALSE
            WHERE sessao_id = %s
        """, (sessao_id,))
        conn.commit()
        add_log("Sessão marcada como inativa após desconexão websocket", "info", sessao_id=sessao_id)
    except Exception as e:
        conn.rollback()
        add_log("Erro ao marcar sessão como inativa", "error", sessao_id=sessao_id, erro=str(e))
    finally:
        cursor.close()
        release_db_connection(conn)