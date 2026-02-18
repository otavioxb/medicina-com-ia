# app/db/schemas.py

from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    nome: str
    cpf: str
    email: EmailStr
    senha: str
    data_nascimento: date
    profissao: str
    empresa: str | None = None


class UserResponse(BaseModel):
    uid: UUID
    nome: str
    email: EmailStr
    profissao: str
    empresa: str | None = None


# class CartaoCreate(BaseModel):
#     numero_mascarado: str
#     validade: str
#     nome_cartao: str
#     token_gateway: str


class CadastroRequest(BaseModel):
    usuario: UserCreate
    # cartao: CartaoCreate
    token: str


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class SessionResponse(BaseModel):
    sessao_id: UUID
    timestamp: datetime
    message: str
    nome: str
    profissao: str


class CompleteTranscriptionResponse(BaseModel):
    sessao_id: UUID
    patient_id: UUID
    necessidade: str
    status: str
    resumo: str | None = None
    relatorio: str | None = None


class TranscriptionResponse(BaseModel):
    pacote_id: int
    transcription: str
    timestamp: datetime


class TranscriptionNotifyPayload(BaseModel):
    pacote_id: int
    status: str


class DuracaoTranscricaoResponse(BaseModel):
    sessao_id: UUID
    patient_id: UUID
    necessidade: str
    duracao_transcricao: str
    data: date
    status: str
