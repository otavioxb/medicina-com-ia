# app/routers/dashboard_routes.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.db.database import get_db_connection, release_db_connection
from app.modules.cache import buscar_dados_paciente,deletar_dados_paciente
from app.modules.resumo_classificacao import resumir_classificar
from app.modules.relatorio import gerar_relatorio_editavel
from app.modules.relatorio import preparar_download_relatorio_editado
from app.celery_app.tasks import atualizar_status_relatorio
from psycopg2.extras import RealDictCursor
from app.modules.utils import add_log,marcar_sessao_como_inativa
from io import BytesIO
from werkzeug.utils import secure_filename
import datetime
from pydantic import BaseModel


router = APIRouter()

@router.get("/dashboard_data")
def get_dashboard_data(sessao_id: str):
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        # Descobre o UID da sessão atual
        cursor.execute("SELECT uid FROM sessions WHERE sessao_id = %s", (sessao_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Sessão inválida ou expirada.")
        
        uid = result["uid"]


        cursor.execute("""
            SELECT
                DATE_TRUNC('month', data) AS mes,
                COUNT(*) AS total_consultas,
                COALESCE(SUM(EXTRACT(EPOCH FROM duracao_transcricao::interval) / 60), 0) AS tempo_transcrito,
                COALESCE(AVG(EXTRACT(EPOCH FROM duracao_transcricao::interval) / 60), 0) AS tempo_medio
            FROM view_analytics_transcricao
            WHERE uid = %s
            AND DATE_TRUNC('month', data) = DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY mes
        """, (uid,))
        stats = cursor.fetchone()

        # Mês com mais consultas
        
        cursor.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', data), 'MM/YY') AS mes, 
                COUNT(*) AS total
            FROM view_analytics_transcricao
            WHERE uid = %s
            GROUP BY mes
            ORDER BY total DESC
            LIMIT 1
        """, (uid,))
        mes_mais_consultas = cursor.fetchone()

        # Verifica se existe transcrição incompleta para retomar
        cursor.execute("""
            SELECT sessao_id, 
                    patient_id, 
                    necessidade, 
                    TO_CHAR(updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI') AS updated_at,
                    transcricao_completa
            FROM view_consultas_pendentes
            WHERE uid = %s 
                AND status != 'relatório baixado'
                AND transcricao_completa IS NOT NULL
                AND TRIM(transcricao_completa) <> ''
            ORDER BY updated_at DESC
        """, (uid,))
        pendencias = cursor.fetchall()
        # consulta_interrompida = cursor.fetchone()

        pendencias_result = []
        for row in pendencias:
            paciente = buscar_dados_paciente(row["sessao_id"], row["patient_id"])
            pendencias_result.append({
                "sessao_id": row["sessao_id"],
                "patient_id": row["patient_id"],
                "necessidade": row["necessidade"],
                "updated_at": row["updated_at"],
                "paciente": paciente["nome"] if paciente else "Desconhecido"
            })

        response = {
            "totalConsultas": int(stats["total_consultas"]) if stats else 0,
            "tempoTranscrito": f"{int(stats['tempo_transcrito'])} min" if stats else "0 min",
            "tempoMedio": f"{int(stats['tempo_medio'])} min" if stats else "0 min",
            "mesMaisConsultas": mes_mais_consultas["mes"].strip() if mes_mais_consultas else "--",
            "consultasPendentes": pendencias_result,
            "uid": uid
        }



        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(connection)

@router.get("/retomar_relatorio")
def retomar_relatorio(sessao_id: str, patient_id: str, necessidade: str, profissao: str):
    # profissao = 'Médico'
    

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        # Recupera transcrição
        cursor.execute("""
            SELECT transcricao_completa 
            FROM complete_transcriptions 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, (sessao_id, patient_id, necessidade))
        transcricao = cursor.fetchone()
        
        transcricao_texto = transcricao['transcricao_completa']

        resumo = resumir_classificar(transcricao_texto, profissao, necessidade)

        dados_paciente = buscar_dados_paciente(sessao_id,patient_id)

        duracao_consulta = dados_paciente.get('duracao_consulta')

        if not duracao_consulta:
            cursor.execute("""
                SELECT duracao_transcricao 
                FROM duracao_consulta 
                WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
            """, (sessao_id, patient_id, necessidade))
            resultado = cursor.fetchone()
            duracao_consulta = resultado.get('duracao_transcricao') if resultado else None


        if not duracao_consulta or str(duracao_consulta).strip() == '':
            duracao_consulta = '00:00:00'

        dados_paciente['duracao_consulta'] = duracao_consulta

        relatorio_final = gerar_relatorio_editavel(
            dados_paciente['nome'],
            dados_paciente['endereco'],
            dados_paciente['dataNascimento'],
            dados_paciente['cpf'],
            resumo,
            dados_paciente['duracao_consulta'],
            necessidade
        )              
        
        nome_paciente = dados_paciente["nome"] if dados_paciente else "Paciente"

        data_corrente = datetime.date.today().strftime("%d_%m_%Y")
        nome_base = f"{necessidade}_{nome_paciente}_{data_corrente}.docx"
        nome_arquivo = secure_filename(nome_base)

        word_buffer: BytesIO = preparar_download_relatorio_editado(relatorio_final, nome_paciente)

        # Atualiza status da transcrição
        atualizar_status_relatorio.delay(sessao_id, patient_id, necessidade, 'relatório baixado')

        add_log(
            "Download de relatório retomado realizado com sucesso",
            "info",
            sessao_id=sessao_id,
            patient_id=patient_id,
            necessidade=necessidade,
            nome_arquivo=nome_arquivo
        )
        # Limpa os dados após download
        try:
            descartar_consulta(sessao_id=sessao_id, patient_id=patient_id, necessidade=necessidade)
            add_log(
                "Dados deletados após download de relatório",
                "info",
                sessao_id=sessao_id,
                patient_id=patient_id,
                necessidade=necessidade,
            )
        except Exception as e:
            # loga erro mas não bloqueia o download
            add_log("Erro ao descartar após retomar: {e}", "error",sessao_id=sessao_id,patient_id=patient_id,necessidade=necessidade,)

        return StreamingResponse(
            word_buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"}
        )

    except Exception as e:
        import traceback
        add_log("Erro ao retomar relatório:", 
                "error",
            erro=str(e),
            sessao_id=sessao_id,
            patient_id=patient_id,
            necessidade=necessidade)
        connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        release_db_connection(connection)

@router.delete("/descartar_consulta")
def descartar_consulta(sessao_id: str, patient_id: str, necessidade: str):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Remove dados vinculados à consulta não finalizada
        cursor.execute("""
            DELETE FROM transcriptions 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, (sessao_id, patient_id, necessidade))

        cursor.execute("""
            DELETE FROM dados_paciente 
            WHERE sessao_id = %s AND patient_id = %s
        """, (sessao_id, patient_id))

        cursor.execute("""
            DELETE FROM complete_transcriptions 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, (sessao_id, patient_id ,necessidade))

        connection.commit()
        return {"message": "Consulta descartada com sucesso."}

    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        release_db_connection(connection)

class LogoutRequest(BaseModel):
    sessao_id: str


@router.post("/logout")
def logout(request: LogoutRequest):
    marcar_sessao_como_inativa(request.sessao_id)
    return {"detail": "Logout realizado com sucesso"}