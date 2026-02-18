# app/routers/auth_routes.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates
from redis.exceptions import RedisError
from passlib.context import CryptContext
from uuid import uuid4
from datetime import datetime
from app.db.database import get_db_connection, release_db_connection
from app.db.schemas import SessionResponse, LoginRequest
from app.modules.utils import add_log
from celery import Celery
import json

router = APIRouter()
templates = Jinja2Templates(directory="app/static/html")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



import os
celery = Celery("app", broker=os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0"))

# --- ROTAS HTML ---
@router.get("/login", response_class=HTMLResponse)
def exibir_pagina_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "now": int(datetime.utcnow().timestamp())})

# @router.get("/verificar_sessao")
# def verificar_sessao(sessao_id: str):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     try:
#         cursor.execute("SELECT timestamp, session_status FROM sessions WHERE sessao_id = %s", (sessao_id,))
#         result = cursor.fetchone()
#         if not result:
#             raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")

#         timestamp, session_status = result
#         if not session_status or (datetime.utcnow() - timestamp).total_seconds() > 43200:
#             cursor.execute("UPDATE sessions SET session_status = FALSE WHERE sessao_id = %s", (sessao_id,))
#             conn.commit()
#             add_log("Sessão marcada como inativa por expiração (verificar_sessao)", "info", sessao_id=sessao_id)
#             raise HTTPException(status_code=401, detail="Sessão expirada")
        
#         return {"status": "ok"}
#     finally:
#         cursor.close()
#         release_db_connection(conn)

@router.get("/check_session")
async def check_session(request: Request, sessao_id: str):
    r = request.app.state.redis
    try:
        session_data = await r.hgetall(f"session:{sessao_id}")
        if not session_data or session_data.get("session_status") != "true":
            add_log("Sessão inválida ou expirada", "info", sessao_id=sessao_id)
            raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")

        # sliding TTL
        await r.hset(f"session:{sessao_id}", "last_active", datetime.utcnow().isoformat())
        await r.expire(f"session:{sessao_id}", 43200)
        if (uid := session_data.get("uid")):
            await r.expire(f"user:{uid}:session", 43200)
        return {"status": "ok"}

    except RedisError as e:
        # Fallback: só se o Redis estiver indisponível
        add_log("Redis indisponível; fallback para banco", "warning", erro=str(e), sessao_id=sessao_id)
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT timestamp, session_status FROM sessions WHERE sessao_id=%s", (sessao_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")
            ts, status = row
            if not status or (datetime.utcnow() - ts).total_seconds() > 43200:
                cursor.execute("UPDATE sessions SET session_status=FALSE WHERE sessao_id=%s", (sessao_id,))
                connection.commit()

                raise HTTPException(status_code=401, detail="Sessão expirada")
            return {"status": "ok"}
        finally:
            cursor.close()
            release_db_connection(connection)

# @router.post("/login", response_model=SessionResponse)
# def login_usuario(dados: LoginRequest):
#     connection = get_db_connection()
#     cursor = connection.cursor()

#     try:
#         cursor.execute("SELECT uid, senha, nome, profissao FROM users WHERE email = %s", (dados.email,))
#         result = cursor.fetchone()

#         if not result:
#             add_log("Tentativa de login com email não cadastrado", "warning", email=dados.email)
#             raise HTTPException(status_code=404, detail="Usuário não encontrado.")

#         uid, senha, nome, profissao = result
        

#         if not pwd_context.verify(dados.senha, senha):
#             add_log("Tentativa de login com senha incorreta", "warning", email=dados.email, uid=uid)
#             raise HTTPException(status_code=401, detail="Senha incorreta.")



#         # Verifica e desativa outras sessões ativas ANTES de criar nova
#         cursor.execute("""
#             SELECT COUNT(*) FROM sessions WHERE uid = %s AND session_status = TRUE
#         """, (uid,))
#         sessao_count = cursor.fetchone()[0]

#         if sessao_count > 0:
#             cursor.execute("""
#                 UPDATE sessions SET session_status = FALSE
#                 WHERE uid = %s AND session_status = TRUE
#             """, (uid,))
#             connection.commit()
#             mensagem_login = "Login realizado com sucesso! Outros dispositivos conectados foram identificados e desconectados."
#             add_log("Login realizado. Sessões anteriores foram desconectadas.", "info", email=dados.email, uid=uid)
#             add_log("Sessão marcada como inativa por login concorrente", "info", sessao_id=sessao_id)
#         else:
#             mensagem_login = "Login realizado com sucesso!"
#             add_log("Login realizado sem sessões anteriores.", "info", email=dados.email, uid=uid)

#                 # Cria nova sessão
#         sessao_id = str(uuid4())
#         timestamp = datetime.utcnow()

#         cursor.execute("""
#             INSERT INTO sessions (sessao_id, uid, timestamp, session_status)
#             VALUES (%s, %s, %s, TRUE)
#         """, (sessao_id, uid, timestamp))
#         connection.commit()

#         return SessionResponse(
#             sessao_id=sessao_id,
#             timestamp=timestamp,
#             message=mensagem_login,
#             nome=nome,
#             profissao=profissao
#         )

#     except Exception as e:
#         connection.rollback()
#         add_log("Erro técnico ao realizar login", "error", erro=str(e), email=dados.email)
#         raise HTTPException(status_code=500, detail=f"Erro ao realizar login: {e}")
#     finally:
#         cursor.close()
#         release_db_connection(connection)
@router.post("/login", response_model=SessionResponse)
async def login_usuario(request: Request, dados: LoginRequest):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT uid, senha, nome, profissao FROM users WHERE email=%s", (dados.email,))
        row = cursor.fetchone()
        if not row:
            add_log("Tentativa de login com email não cadastrado", "warning", email=dados.email)
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        uid, senha_hash, nome, profissao = row

        if not pwd_context.verify(dados.senha, senha_hash):
            add_log("Tentativa de login com senha incorreta", "warning", email=dados.email, uid=uid)
            raise HTTPException(status_code=401, detail="Senha incorreta.")

        r = request.app.state.redis
        sessao_id = str(uuid4())
        timestamp = datetime.utcnow()
        session_data = {
            "uid": uid,
            "timestamp": timestamp.isoformat(),
            "session_status": "true",
            "last_active": timestamp.isoformat(),
        }

        # ---------- PIPELINE ATÔMICO AQUI ----------
        p = r.pipeline(transaction=True)
        old = await r.get(f"user:{uid}:session")
        if old:
            p.hset(f"session:{old}", "session_status", "false")
            p.delete(f"user:{uid}:session")

        p.hset(f"session:{sessao_id}", mapping=session_data)
        p.expire(f"session:{sessao_id}", 43200)
        p.setex(f"user:{uid}:session", 43200, sessao_id)
        await p.execute()
        # ------------------------------------------

        mensagem_login = ("Login realizado com sucesso! Outros dispositivos conectados foram "
                          "identificados e desconectados.") if old else "Login realizado com sucesso!"
        if old:
            # assíncrono no banco para refletir o desligamento da sessão anterior
            celery.send_task("app.celery_app.tasks.sync_session_status", args=[old, False])

        # Persistência no histórico (verdade de longo prazo)
        cursor.execute("""
            INSERT INTO sessions (sessao_id, uid, timestamp, session_status)
            VALUES (%s, %s, %s, TRUE)
        """, (sessao_id, uid, timestamp))
        connection.commit()

        add_log("Login OK (Redis como fonte).", "info", email=dados.email, uid=uid, sessao_id=sessao_id)

        return SessionResponse(
            sessao_id=sessao_id,
            timestamp=timestamp,
            message=mensagem_login,
            nome=nome,
            profissao=profissao,
        )
    except Exception as e:
        connection.rollback()
        add_log("Erro técnico ao realizar login", "error", erro=str(e), email=dados.email)
        raise HTTPException(status_code=500, detail=f"Erro ao realizar login: {e}")
    finally:
        cursor.close()
        release_db_connection(connection)