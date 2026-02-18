# app/routers/cadastro_routes.py

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from dotenv import load_dotenv
from pydantic import BaseModel
from uuid import uuid4, UUID
from datetime import datetime, date
import hashlib
import os

from app.modules.utils import add_log
from app.db.database import get_db_connection, release_db_connection
from app.db.schemas import UserCreate  # ✅ Agora está sendo realmente usado

# ============ Configuração ============
load_dotenv()
router = APIRouter()
templates = Jinja2Templates(directory="app/static/html")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_env_variable(name, default=None):
    return os.getenv(name, default)

valid_tokens = [t.strip() for t in get_env_variable("CADASTRO_TOKENS", "").split(",")]

# ============ Helpers ============

def gerar_uid_a_partir_do_cpf(cpf: str) -> str:
    cpf_limpo = cpf.replace(".", "").replace("-", "")
    hash_bytes = hashlib.sha256(cpf_limpo.encode()).digest()
    return str(UUID(bytes=hash_bytes[:16]))

# ============ Schemas de entrada ============

# class CartaoCreate(BaseModel):
#     numero_mascarado: str
#     validade: str  # formato MM/YY
#     nome_cartao: str

class CadastroRequest(BaseModel):
    usuario: UserCreate
    # cartao: CartaoCreate
    token: str

# ============ Rotas ============

@router.get("/cadastro", response_class=HTMLResponse)
def exibir_pagina_cadastro(request: Request):
    return templates.TemplateResponse("cadastro.html", {"request": request, "now": int(datetime.utcnow().timestamp())})


@router.post("/cadastro")
def cadastrar_usuario(request: Request, payload: CadastroRequest):
    usuario_data = payload.usuario
    # cartao_data = payload.cartao
    token = payload.token

    if token not in valid_tokens:
        add_log("Tentativa de cadastro com token inválido", "warning", email=usuario_data.email, cpf=usuario_data.cpf)
        raise HTTPException(status_code=403, detail="Token inválido ou não autorizado.")

    connection = get_db_connection()
    cursor = connection.cursor()

    uid = gerar_uid_a_partir_do_cpf(usuario_data.cpf)

    try:
        # Verifica se já existe
        cursor.execute(
            "SELECT cpf, email FROM users WHERE cpf = %s OR email = %s",
            (usuario_data.cpf, usuario_data.email)
        )
        ja_existe = cursor.fetchone()
        if ja_existe:
            if ja_existe[0] == usuario_data.cpf:
                add_log("Cadastro rejeitado: CPF já cadastrado", "info", cpf=usuario_data.cpf)
                raise HTTPException(status_code=400, detail="CPF já cadastrado.")
            if ja_existe[1] == usuario_data.email:
                add_log("Cadastro rejeitado: Email já cadastrado", "info", email=usuario_data.email)
                raise HTTPException(status_code=400, detail="Email já cadastrado.")

        senha_criptografada = pwd_context.hash(usuario_data.senha)

        cursor.execute("""
            INSERT INTO users (uid, nome, cpf, email, senha, data_nascimento, profissao)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            uid,
            usuario_data.nome,
            usuario_data.cpf,
            usuario_data.email,
            senha_criptografada,
            usuario_data.data_nascimento,
            usuario_data.profissao
        ))

        # cartao_id = str(uuid4())
        # validade_formatada = f"20{cartao_data.validade[-2:]}-{cartao_data.validade[:2]}-01"

        # cursor.execute("""
        #     INSERT INTO cartoes_credito (
        #         id, uid, numero_ultimos4, validade, nome_impresso, token_gateway, ativo, criado_em
        #     )
        #     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        # """, (
        #     cartao_id,
        #     uid,
        #     cartao_data.numero_mascarado[-4:],
        #     validade_formatada,
        #     cartao_data.nome_cartao,
        #     "fake-token-placeholder",
        #     True,
        #     datetime.utcnow()
        # ))

        connection.commit()

        add_log("Cadastro realizado com sucesso", "info", uid=uid, email=usuario_data.email)
        return JSONResponse(status_code=200, content={
            "message": "Cadastro realizado com sucesso",
            "nome": usuario_data.nome,
            "redirect": "/login"
        })

    except Exception as e:
        connection.rollback()
        add_log("Erro técnico ao cadastrar usuário", "error", erro=str(e), email=usuario_data.email, cpf=usuario_data.cpf)
        raise HTTPException(status_code=500, detail=f"Erro ao cadastrar: {e}")
    finally:
        cursor.close()
        release_db_connection(connection)