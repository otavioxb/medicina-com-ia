from fastapi import APIRouter, Query, HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse
from app.db.database import get_db_connection, release_db_connection
from app.modules.utils import add_log
from app.db.schemas import TranscriptionNotifyPayload  # ✅ Agora importado corretamente

router = APIRouter()

@router.get("/transcriptions/{sessao_id}")
async def get_transcriptions(request: Request, sessao_id: str, patient_id: str = Query(...), necessidade: str = Query(...)):
    # Fonte primária para UI (Scale A): Redis (parcial), fallback Postgres
    if not (patient_id and necessidade):
        raise HTTPException(status_code=400, detail="Dados incompletos na solicitação.")

    redis_key = f"transcricao:{sessao_id}:{patient_id}:{necessidade}:partial_text"
    try:
        r = request.app.state.redis
        cached = await r.get(redis_key)
        if cached:
            return {"transcription": cached.strip()}
    except Exception as e:
        add_log("Erro ao ler transcrição parcial do Redis", "warning", erro=str(e), sessao_id=sessao_id, patient_id=patient_id)

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT transcription FROM transcriptions WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s AND status = 'concluída' ORDER BY timestamp DESC LIMIT 1",
            (sessao_id, patient_id, necessidade)
        )
        result = cursor.fetchone()
        if result and result[0]:
            return {"transcription": result[0]}
        return {"transcription": ""}

    except Exception as e:
        add_log("Erro ao recuperar transcrição", "error", erro=str(e), sessao_id=sessao_id, patient_id=patient_id)
        raise HTTPException(status_code=500, detail="Erro ao recuperar transcrição")

    finally:
        cursor.close()
        release_db_connection(connection)


@router.post("/notify_transcription_done")
async def notify_transcription_done(payload: TranscriptionNotifyPayload):
    pacote_id = payload.pacote_id
    status = payload.status

    # add_log("Transcrição finalizada notificada", "info", pacote_id=pacote_id, status=status)
    return JSONResponse(content={"ok": True})