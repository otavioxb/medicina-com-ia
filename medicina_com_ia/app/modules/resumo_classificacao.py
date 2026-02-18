# app/modules/resumo_classificacao.py

from openai import OpenAI
from dotenv import load_dotenv
import os
import yaml
from app.modules.utils import add_log

load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def carregar_prompts(caminho_arquivo='app/modules/prompts.yaml'):
    with open(caminho_arquivo, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def resumir_classificar(texto: str, profissao: str, necessidade: str) -> str:
    prompts = carregar_prompts()
    prompt_profissao = prompts.get(profissao, {})
    prompt_especialidade = prompt_profissao.get(necessidade)

    if not prompt_especialidade:
        add_log("Prompt não encontrado", "warning", profissao=profissao, necessidade=necessidade)
        return f"Erro: área '{necessidade}' não encontrada para a profissão '{profissao}' no arquivo de prompts."

    prompt = prompt_especialidade.replace('{texto}', texto)

    try:
        add_log("Iniciando resumo/classificação", "info", profissao=profissao, necessidade=necessidade)
        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um assistente médico útil."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        resultado = resposta.choices[0].message.content.strip()
        add_log("Resumo e classificação concluídos", "info", tamanho=len(resultado))
        return resultado
    except Exception as e:
        add_log("Erro no resumo/classificação", "error", erro=str(e), profissao=profissao, necessidade=necessidade)
        return f"Erro ao resumir e classificar a consulta: {e}"