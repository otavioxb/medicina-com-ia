import asyncio
from fastapi import APIRouter, Query, HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
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


@router.get("/transcriptions/stream/{sessao_id}")
async def stream_transcriptions(request: Request, sessao_id: str, patient_id: str = Query(...), necessidade: str = Query(...)):
    # Server-Sent Events: envia o texto concatenado conforme o Redis muda.
    if not (patient_id and necessidade):
        raise HTTPException(status_code=400, detail="Dados incompletos na solicitação.")

    r = request.app.state.redis
    base = f"transcricao:{sessao_id}:{patient_id}:{necessidade}"
    key_text = f"{base}:partial_text"
    key_last = f"{base}:last_update"

    async def event_gen():
        last_sent = None
        last_keepalive = 0.0
        while True:
            if await request.is_disconnected():
                break

            try:
                lu = await r.get(key_last)
                if lu and lu != last_sent:
                    txt = await r.get(key_text) or ""
                    last_sent = lu
                    safe = txt.replace("\\", "\\\\").replace("\n", "\\n")
                    yield f"event: transcription\ndata: {safe}\n\n"
                else:
                    now = asyncio.get_event_loop().time()
                    if now - last_keepalive > 15:
                        last_keepalive = now
                        yield "event: ping\ndata: ok\n\n"
            except Exception as e:
                add_log("Erro no stream SSE", "warning", erro=str(e), sessao_id=sessao_id, patient_id=patient_id)
                yield "event: ping\ndata: ok\n\n"

            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/notify_transcription_done")
async def notify_transcription_done(payload: TranscriptionNotifyPayload):
    pacote_id = payload.pacote_id
    status = payload.status

    # add_log("Transcrição finalizada notificada", "info", pacote_id=pacote_id, status=status)
    return JSONResponse(content={"ok": True})