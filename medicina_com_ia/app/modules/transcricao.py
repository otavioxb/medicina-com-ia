from io import BytesIO
from openai import OpenAI
import io
from dotenv import load_dotenv
from app.modules.utils import add_log


# Carrega variáveis de ambiente (chave da OpenAI, etc.)
load_dotenv()

client = OpenAI()

# Função para transcrever áudio de cada pacote individualmente
def transcrever_audio(audio_data, pacote_id, sessao_id=None, patient_id=None, necessidade=None):
    try:
        add_log("Iniciando transcrição", "info", pacote_id=pacote_id, sessao_id=sessao_id, patient_id = patient_id,necessidade=necessidade)
        audio_file = io.BytesIO(audio_data)
        audio_file.name = f"audio_{pacote_id}.wav"

        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            temperature=0,
            language="pt"
        )

        transcricao = response.text
        add_log("Transcrição concluída", "info", pacote_id=pacote_id, tamanho=len(transcricao), sessao_id=sessao_id)
        return transcricao

    except Exception as e:
        add_log("Erro na transcrição", "error", pacote_id=pacote_id, erro=str(e), sessao_id=sessao_id)
        return "Erro na transcrição do pacote"