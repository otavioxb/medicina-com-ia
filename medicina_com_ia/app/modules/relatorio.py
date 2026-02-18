# app/modules/relatorio.py

from io import BytesIO
from docx import Document
from datetime import datetime
from app.modules.utils import add_log

from datetime import datetime

from datetime import datetime

def gerar_relatorio_editavel(nome, endereco, dataNascimento, cpf, resumo_classificacao, duracao_consulta, necessidade):
    try:
        data_corrente = datetime.today().strftime("%d/%m/%Y")
        linhas = []

        # Helper para decidir se inclui o campo
        def valido(valor):
            return valor and valor.strip() and valor.strip().lower() != "não informado"

        # Para necessidade que contenha "consulta"
        if "consulta" in necessidade.lower():
            linhas.append(f"Data: {data_corrente}")
            if valido(nome): linhas.append(f"Nome: {nome}")
            if valido(endereco): linhas.append(f"Informações Adicionais: {endereco}")
            if valido(dataNascimento):
                try:
                    data_nasc = datetime.strptime(dataNascimento, "%Y-%m-%d")
                    linhas.append(f"Data de Nascimento: {data_nasc.strftime('%d/%m/%Y')}")
                    idade = datetime.today().year - data_nasc.year
                    linhas.append(f"Idade: {idade}")
                except ValueError:
                    linhas.append("Data de Nascimento: Formato inválido")
            if valido(cpf): linhas.append(f"CPF: {cpf}")
            if valido(duracao_consulta): linhas.append(f"Duração da Consulta: {duracao_consulta}")
            linhas.append("")  # linha em branco
            linhas.append(resumo_classificacao)

        # Para necessidade igual a "atestado" ou "exame"
        elif necessidade.lower() in ["receita", "exame"]:
            linhas.append(f"Data: {data_corrente}")
            if valido(nome): linhas.append(f"Nome: {nome}")
            linhas.append("")  # linha em branco
            linhas.append(resumo_classificacao)

        # Caso seja só "atestado" (se quiser lógica diferente pode adaptar aqui)
        elif necessidade.lower() == "atestado":
            linhas.append(f"Data: {data_corrente}")
            linhas.append("")  # linha em branco
            linhas.append(resumo_classificacao)

        else:
            # Padrão para outros casos
            linhas.append(f"Data: {data_corrente}")
            if valido(nome): linhas.append(f"Nome: {nome}")
            if valido(endereco): linhas.append(f"Informações Adicionais: {endereco}")
            if valido(cpf): linhas.append(f"CPF: {cpf}")
            linhas.append("")  # linha em branco
            linhas.append(resumo_classificacao)

        relatorio_texto = "\n".join(linhas)
        add_log("Relatório em texto gerado", "info", nome=nome, duracao=duracao_consulta)
        return relatorio_texto

    except Exception as e:
        add_log("Erro ao gerar relatório", "error", erro=str(e), nome=nome)
        raise

def preparar_download_relatorio_editado(relatorio_texto, nome):
    try:
        doc = Document()
        for line in relatorio_texto.splitlines():
            if line.strip():
                doc.add_paragraph(line.strip())

        word_buffer = BytesIO()
        doc.save(word_buffer)
        word_buffer.seek(0)
        add_log("Relatório Word preparado para download", "info", nome=nome)
        return word_buffer
    except Exception as e:
        add_log("Erro ao preparar relatório para download", "error", erro=str(e), nome=nome)
        raise