# app/celery_app/tasks.py

from celery import Celery
import os
import time
import requests
from app.db.database import get_db_connection, release_db_connection
from app.modules.transcricao import transcrever_audio
from app.modules.utils import add_log, is_silent
from redis import Redis


# def make_celery(app_name=__name__):
#     redis_url = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0")
#     celery = Celery(app_name, broker=redis_url, backend=redis_url)
#     celery.conf.update({
#         'broker_connection_retry_on_startup': True
#     })
#     return celery
def make_celery(app_name=__name__):
    redis_url = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0")
    celery = Celery(app_name, broker=redis_url, backend=redis_url)
    celery.conf.update({
        'broker_connection_retry_on_startup': True,
        'task_cls': 'celery.app.task:Task',
        'beat_schedule': {
            'sync_expired_sessions': {
                'task': 'app.celery_app.tasks.sync_expired_sessions',
                'schedule': 300.0,
            },
        },
        'task_serializer': 'json',
        'result_serializer': 'json',
        'accept_content': ['json'],
    })
    return celery

celery = make_celery()


@celery.task
def delay_download(segundos: int):
    add_log(f"Atrasando o download por {segundos} segundos.")
    time.sleep(segundos)
    return "Atraso concluído"


@celery.task
def atualizar_status_relatorio(sessao_id, patient_id, necessidade, novo_status):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE complete_transcriptions 
            SET status = %s 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, (novo_status, sessao_id, patient_id, necessidade))
        connection.commit()
        add_log(f"Status atualizado para '{novo_status}'")
    except Exception as e:
        connection.rollback()
        add_log(f"Erro ao atualizar status para '{novo_status}': {e}", level="error")
    finally:
        cursor.close()
        release_db_connection(connection)


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def transcrever_audio_task(self, audio_data, pacote_id, sessao_id, patient_id, necessidade):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Marca como processando
        cursor.execute("""
            UPDATE transcriptions 
            SET status = %s 
            WHERE pacote_id = %s
        """, ('processando', pacote_id))
        connection.commit()

        if is_silent(audio_data):
            cursor.execute("""
                UPDATE transcriptions 
                SET status = %s 
                WHERE pacote_id = %s
            """, ('silencio', pacote_id))
            connection.commit()
            
            add_log(
                "Pacote ignorado por conter silêncio",
                "info",
                pacote_id=pacote_id,
                sessao_id=sessao_id,
                patient_id=patient_id,
                necessidade=necessidade
            )
            return

        # Transcreve com Whisper
        transcricao_parcial = transcrever_audio(audio_data, pacote_id,sessao_id, patient_id, necessidade)

        if transcricao_parcial and "Erro na transcrição" not in transcricao_parcial:
            cursor.execute("""
                UPDATE transcriptions 
                SET status = %s, transcription = %s 
                WHERE pacote_id = %s
            """, ('concluída', transcricao_parcial, pacote_id))

            # Atualiza transcrição completa
            cursor.execute("""
                UPDATE complete_transcriptions 
                SET transcricao_completa = COALESCE(transcricao_completa, '') || %s
                WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
            """, (transcricao_parcial + " ", sessao_id, patient_id, necessidade))

            # === Scale A (Fase 1): transcrição parcial em Redis ===
            # Cache volátil para UI; não pode quebrar o processamento.
            try:
                redis_url = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0")
                r = Redis.from_url(redis_url, decode_responses=True)
                redis_key = f"transcricao:{sessao_id}:{patient_id}:{necessidade}:partial_text"
                r.append(redis_key, transcricao_parcial + " ")
                r.expire(redis_key, 60 * 60 * 24)  # 24h
                r.setex(f"transcricao:{sessao_id}:{patient_id}:{necessidade}:last_update", 60 * 60 * 24, str(time.time()))
            except Exception as _e:
                add_log("Falha ao escrever transcrição parcial no Redis", "warning", erro=str(_e), sessao_id=sessao_id, pacote_id=pacote_id)

        else:
            cursor.execute("""
                UPDATE transcriptions 
                SET status = %s 
                WHERE pacote_id = %s
            """, ('erro_fila', pacote_id))
            add_log(
                "Erro durante transcrição do pacote",
                "warning",
                pacote_id=pacote_id,
                sessao_id=sessao_id,
                status="erro_fila"
            )

        connection.commit()
    except Exception as e:
        connection.rollback()
        add_log(
            "Erro crítico ao processar pacote de transcrição",
            "error",
            erro=str(e),
            pacote_id=pacote_id,
            sessao_id=sessao_id,
            necessidade=necessidade
        )
        raise
    finally:
        cursor.close()
        release_db_connection(connection)
        del audio_data



@celery.task(bind=True, ignore_result=True)
def sync_session_status(self, sessao_id: str, status: bool):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE sessions 
            SET session_status = %s 
            WHERE sessao_id = %s
        """, (status, sessao_id))
        connection.commit()
        add_log(f"Sessão {sessao_id} atualizada para status={status} no banco", "info", sessao_id=sessao_id)
        return {"status": "success", "sessao_id": sessao_id, "session_status": status}
    except Exception as e:
        connection.rollback()
        add_log(f"Erro ao atualizar session_status no banco", "error", erro=str(e), sessao_id=sessao_id)
        raise
    finally:
        cursor.close()
        release_db_connection(connection)

# app/celery_app/tasks.py
from redis import Redis  # <- sync

@celery.task(bind=True, ignore_result=True)
def sync_expired_sessions(self):
    redis = Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", "6379")), decode_responses=True)
    try:
        # Use SCAN no lugar de KEYS para não bloquear:
        cursor = 0
        connection = get_db_connection()
        cursor_db = connection.cursor()
        processed = 0
        try:
            while True:
                cursor, keys = redis.scan(cursor=cursor, match="session:*", count=500)
                for key in keys:
                    sessao_id = key.split(":", 1)[1]
                    session_data = redis.hgetall(key)
                    ttl = redis.ttl(key)
                    if ttl <= 0 or session_data.get("session_status") != "true":
                        cursor_db.execute("""
                            UPDATE sessions 
                            SET session_status = FALSE 
                            WHERE sessao_id = %s AND session_status = TRUE
                        """, (sessao_id,))
                        connection.commit()
                        add_log("Sessão marcada como inativa no banco (expirada/inativa no Redis)",
                                "info", sessao_id=sessao_id)
                        processed += 1
                if cursor == 0:
                    break
            return {"status": "success", "sessions_processed": processed}
        except Exception as e:
            connection.rollback()
            add_log("Erro ao sincronizar sessões expiradas", "error", erro=str(e))
            raise
        finally:
            cursor_db.close()
            release_db_connection(connection)
    except Exception as e:
        add_log("Erro ao acessar Redis para sincronizar sessões expiradas", "error", erro=str(e))
        raise