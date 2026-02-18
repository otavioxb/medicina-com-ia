from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import StreamingResponse
from app.modules.cache import buscar_dados_paciente
from app.modules.relatorio import preparar_download_relatorio_editado
from app.db.database import get_db_connection, release_db_connection
from app.modules.utils import add_log
from app.celery_app.tasks import atualizar_status_relatorio
from app.modules.utils import add_log
from io import BytesIO
from werkzeug.utils import secure_filename
import datetime

router = APIRouter()

@router.get("/download_relatorio")
async def download_relatorio(
    sessao_id: str = Query(...),
    patient_id: str = Query(...),
    necessidade: str = Query(...)
):
    dados_paciente = buscar_dados_paciente(sessao_id,patient_id)

    
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT relatorio, status 
            FROM complete_transcriptions 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, (sessao_id, patient_id, necessidade))

        result = cursor.fetchone()
        if not dados_paciente:
            add_log("Dados do paciente não encontrados", "warning", patient_id=patient_id)
            raise HTTPException(status_code=404, detail="Dados do paciente não encontrados.")
        
        if not result:
            add_log(
                "Tentativa de download: relatório não encontrado",
                "warning",
                sessao_id=sessao_id,
                patient_id=patient_id,
                necessidade=necessidade
            )
            raise HTTPException(status_code=404, detail="Nenhum relatório disponível para download.")

        relatorio_final, status_atual = result

        if status_atual != 'relatório finalizado':
            add_log(
                "Tentativa de download: relatório não finalizado",
                "warning",
                sessao_id=sessao_id,
                patient_id=patient_id,
                necessidade=necessidade,
                status=status_atual
            )
            raise HTTPException(status_code=400, detail="O relatório ainda não está pronto para download.")

        if not relatorio_final.strip():
            add_log(
                "Relatório finalizado está vazio",
                "warning",
                sessao_id=sessao_id,
                patient_id=patient_id,
                necessidade=necessidade
            )
            raise HTTPException(status_code=400, detail="Relatório indisponível.")
        
        
        nome_paciente = dados_paciente["nome"] if dados_paciente else "Paciente"

        data_corrente = datetime.date.today().strftime("%d_%m_%Y")
        nome_base = f"{necessidade}_{nome_paciente}_{data_corrente}.docx"
        nome_arquivo = secure_filename(nome_base)

        word_buffer: BytesIO = preparar_download_relatorio_editado(relatorio_final, nome_paciente)

        # Atualiza status da transcrição
        atualizar_status_relatorio.delay(sessao_id, patient_id, necessidade, 'relatório baixado')

        add_log(
            "Download de relatório realizado com sucesso",
            "info",
            sessao_id=sessao_id,
            patient_id=patient_id,
            necessidade=necessidade,
            nome_arquivo=nome_arquivo
        )

        return StreamingResponse(
            word_buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"}
        )

    except Exception as e:
        add_log(
            "Erro técnico ao gerar ou entregar relatório final",
            "error",
            erro=str(e),
            sessao_id=sessao_id,
            patient_id=patient_id,
            necessidade=necessidade
        )
        raise HTTPException(status_code=500, detail="Erro interno ao gerar relatório.")

    finally:
        cursor.close()
        release_db_connection(connection)