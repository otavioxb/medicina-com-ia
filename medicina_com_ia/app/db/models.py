# app/db/models.py

# app/db/models.py

from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, EmailStr


class UserInDB(BaseModel):
    uid: UUID
    nome: str
    cpf: str
    email: EmailStr
    senha: str
    data_nascimento: date
    profissao: str
    empresa: str | None = None
    data_criacao: date


class SessionInDB(BaseModel):
    sessao_id: UUID
    uid: UUID
    timestamp: datetime


class CompleteTranscription(BaseModel):
    sessao_id: UUID
    patient_id: UUID
    necessidade: str
    transcricao_completa: str = ""
    resumo: str | None = None
    relatorio: str | None = None
    status: str = "pendente"
    updated_at: datetime


class Transcription(BaseModel):
    pacote_id: int
    sessao_id: UUID
    patient_id: UUID
    necessidade: str
    status: str = "pendente"
    transcription: str | None = None
    timestamp: datetime


# class CartaoCredito(BaseModel):
#     id: UUID
#     uid: UUID
#     numero_ultimos4: str
#     validade: date
#     nome_impresso: str
#     token_gateway: str
#     ativo: bool = True
#     criado_em: datetime


class DuracaoTranscricao(BaseModel):
    id: int
    sessao_id: UUID
    patient_id: UUID
    necessidade: str
    duracao_transcricao: str  # formato HH:MM:SS
    data: date
    status: str = "pendente"


class DuracaoTranscricaoCreate(BaseModel):
    sessao_id: UUID
    patient_id: UUID
    necessidade: str
    duracao_transcricao: str  # formato HH:MM:SS