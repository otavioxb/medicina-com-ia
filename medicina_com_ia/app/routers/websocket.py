# routers/websocket.py

import json
from datetime import datetime, timedelta
import base64
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.db.database import get_db_connection,release_db_connection
from app.modules.utils import add_log, marcar_sessao_como_inativa
from app.celery_app.tasks import transcrever_audio_task
from app.modules.resumo_classificacao import resumir_classificar
from app.modules.relatorio import gerar_relatorio_editavel
# from app.celery_app.tasks import atualizar_status_relatorio
from app.modules.cache import salvar_dados_paciente, buscar_dados_paciente, deletar_dados_paciente

router = APIRouter()



templates = Jinja2Templates(directory="app/static/html")

@router.get("/", response_class=HTMLResponse)
async def exibir_pagina_principal(request: Request):
    return templates.TemplateResponse("main.html", {"request": request, "now": int(datetime.utcnow().timestamp())})

# Armazena conexões ativas por sessão
active_connections = {}

# Controle de última comunicação
ultimos_pings = {}

# Controle extra para armazenar dados necessários na hora de detectar falha
session_metadata = {}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    sessao_id = websocket.query_params.get("sessao_id")
    if not sessao_id:
        await websocket.send_json({"type": "error", "message": "sessao_id ausente na conexão"})
        await websocket.close()
        return
    
    r = websocket.scope["app"].state.redis

    # (Opcional, mais rápido) valide no Redis antes do banco:
    try:
        sdata = await r.hgetall(f"session:{sessao_id}")
        if not sdata or sdata.get("session_status") != "true":
            # fallback: valida no banco (como você já faz)
            pass
        else:
            # ok; mantém o seu fallback para o banco se preferir
            pass
    except Exception:
        pass
    # Verifica se a sessão existe no banco de dados
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT session_status FROM sessions WHERE sessao_id = %s;", (sessao_id,))
        exists = cursor.fetchone()
        if not exists:
            await websocket.close(code=1008)  # Close with Policy Violation
            add_log(f"Conexão recusada: sessão_id {sessao_id} não existe no banco","info", sessao_id=sessao_id)
            return
    finally:
        cursor.close()
        release_db_connection(connection)


    # Salva conexão por sessão
    active_connections[sessao_id] = websocket

    add_log("Cliente conectado via WebSocket", "info", sessao_id=sessao_id)

    try:
        while True:
            try:
                data = await websocket.receive_text()
                payload = json.loads(data)
                tipo = payload.get("type")
                conteudo = payload.get("payload", {})

            except WebSocketDisconnect as ws_exc:
                close_code = getattr(ws_exc, "code", None)  # sempre tem o 'code'
                add_log(
                    "Cliente desconectado do WebSocket",
                    "info",
                    sessao_id=sessao_id,
                    close_code=close_code,
                )
                break
            except Exception as e:
                import traceback
                traceback.print_exc()
                add_log("Erro ao receber ou decodificar mensagem", "error", erro=str(e), sessao_id=sessao_id)
                await safe_send_json(websocket, {"type": "error", "message": f"Erro ao processar mensagem: {e}"})
                continue  # continua aguardando próximo pacote
    
            if tipo in ["start_gravacao", "parar_gravacao", "audio_chunk"]:
                ultimos_pings[sessao_id] = datetime.now()

                if tipo == "start_gravacao":
                    # Além de ultimos_pings, armazena dados para controle de timeout
                    session_metadata[sessao_id] = {
                        "patient_id": conteudo.get("patient_id"),
                        "necessidade": conteudo.get("necessidade"),
                        "start_time_backend": datetime.now()
                    }

            if tipo == "dados_paciente":
                print("Chamando handle_dados_paciente com:")
                await handle_dados_paciente(conteudo, websocket)
            
            elif tipo == "logout":
                r = websocket.scope["app"].state.redis
                now = datetime.utcnow().isoformat()
                sess_key = f"session:{sessao_id}"

                lua = """
                local sess = KEYS[1]
                local sess_id = ARGV[1]
                local now = ARGV[2]
                local ttl_after = tonumber(ARGV[3])

                -- pega uid dessa sessão
                local uid = redis.call('HGET', sess, 'uid')
                if not uid then
                    return 0
                end

                -- se o ponteiro do usuário ainda aponta pra esta sessão, apaga
                local uptr = 'user:'..uid..':session'
                if redis.call('GET', uptr) == sess_id then
                    redis.call('DEL', uptr)
                end

                -- marca sessão como inativa e atualiza last_active
                redis.call('HSET', sess, 'session_status', 'false', 'last_active', now)

                -- opcional: expira rápido p/ limpeza (ex.: 5min)
                if ttl_after and ttl_after > 0 then
                    redis.call('EXPIRE', sess, ttl_after)
                end

                return 1
                """

                try:
                    # 300s = mantemos por 5min p/ auditoria e para o beat sincronizar (se quiser 0, remova o EXPIRE)
                    await r.eval(lua, keys=[sess_key], args=[sessao_id, now, "300"])
                except Exception as e:
                    add_log("Erro ao aplicar logout no Redis", "error", sessao_id=sessao_id, erro=str(e))

                # reflete no banco (assíncrono via celery)
                try:
                    from app.celery_app.tasks import celery
                    celery.send_task("app.celery_app.tasks.sync_session_status", args=[sessao_id, False])
                except Exception as e:
                    add_log("Erro ao enfileirar sync_session_status", "error", sessao_id=sessao_id, erro=str(e))

                await websocket.close(code=1000)
                return
            
            elif tipo == "log_frontend":
                mensagem = conteudo.get("mensagem", "")
                add_log(mensagem, level="warning", origem="frontend")

            elif tipo == "audio_chunk":
                await handle_audio_chunk(conteudo, websocket)

            # É aqui que você atualiza:
            elif tipo == "verificar_pacotes_pendentes":
                await handle_verificar_pacotes_pendentes(conteudo, websocket)

            elif tipo == "gerar_relatorio":
                await handle_gerar_relatorio(conteudo, websocket)

            elif tipo == "preparar_relatorio":
                await handle_preparar_relatorio(conteudo, websocket)

            elif tipo == "nova_consulta":
                await handle_nova_consulta(conteudo, websocket)
            
            elif tipo == "start_gravacao":
                await handle_start_gravacao(conteudo, websocket)

            elif tipo == "parar_gravacao":
                await handle_parar_gravacao(conteudo, websocket)

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Tipo de evento desconhecido: {tipo}"
                })

    
    except Exception as e:
        add_log("Erro crítico no WebSocket", "error", erro=str(e), sessao_id=sessao_id)
        try:
            safe_send_json(websocket, {"type": "error", "message": f"Erro no servidor: {e}"})
        except RuntimeError as send_error:
            add_log("WebSocket já foi fechado. Ignorando envio de erro ao cliente.", "warning", erro=str(send_error))
    finally:
        
        active_connections.pop(sessao_id, None)
        ultimos_pings.pop(sessao_id, None)
        session_metadata.pop(sessao_id, None)

async def safe_send_json(websocket, message):
    try:
        await websocket.send_json(message)
    except RuntimeError as e:
        if "websocket.send" in str(e) or "already completed" in str(e):
            add_log("Tentativa de envio em WebSocket já fechado.", "warning")
        else:
            raise

# @router.on_event("startup")
# async def startup_event():
#     asyncio.create_task(verificar_timeouts())

async def handle_dados_paciente(data: dict, websocket: WebSocket):
    try:
        # print("Recebido em handle_dados_paciente:", data)

        patient_id = data.get("patient_id")
        sessao_id = data.get("sessao_id")
        if not patient_id:
            await websocket.send_json({"type": "error", "message": "patient_id ausente."})
            return

        salvar_dados_paciente(sessao_id, patient_id, {
            "nome": data.get("nome"),
            "endereco": data.get("endereco", "Não informado"),
            "dataNascimento": data.get("dataNascimento"),
            "cpf": data.get("cpf"),
            "duracao_consulta": None
        })

        add_log("Dados do paciente recebidos", "info", patient_id=patient_id, sessao_id=sessao_id)
        await websocket.send_json({"type": "ok", "message": "Dados do paciente recebidos."})
    except Exception as e:
        erro_msg = f"Erro ao salvar dados do paciente: {e}"
        add_log("Erro ao processar dados do paciente", "error", erro=erro_msg, sessao_id=data.get("sessao_id"))
        await websocket.send_json({
            "type": "error",
            "message": erro_msg
        })

async def handle_start_gravacao(data, websocket: WebSocket):
    sessao_id = data.get("sessao_id")
    patient_id = data.get("patient_id")
    necessidade = data.get("necessidade")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Cria o registro se não existir
        cursor.execute("""
            INSERT INTO duracao_consulta (sessao_id, patient_id, necessidade)
            VALUES (%s, %s, %s)
            ON CONFLICT (sessao_id, patient_id, necessidade) DO NOTHING;
        """, (sessao_id, patient_id, necessidade))
        connection.commit()

        # Atualiza controle em memória
        session_metadata[sessao_id] = {
            "patient_id": patient_id,
            "necessidade": necessidade,
            "start_time_backend": datetime.now()  # <== Marca ou reinicia o contador
        }

        add_log("Iniciado controle de gravação", "info", sessao_id=sessao_id, patient_id=patient_id, necessidade=necessidade)
    except Exception as e:
        connection.rollback()
        add_log("Erro ao iniciar gravação", "error", erro=str(e), sessao_id=sessao_id, patient_id=patient_id)
    finally:
        cursor.close()
        release_db_connection(connection)


async def handle_audio_chunk(data, websocket: WebSocket):
    audio_data = data.get("audioData")
    pacote_id = data.get("pacote_id")
    sessao_id = data.get("sessao_id")
    patient_id = data.get("patient_id")
    necessidade = data.get("necessidade")

    # add_log(f"Pacote {pacote_id} recebido com {len(audio_data)} bytes.")


    if not all([audio_data, pacote_id, sessao_id, patient_id, necessidade]):
        await websocket.send_json({"type": "transcription_status", "pacote_id": pacote_id, "status": "erro"})
        add_log("Pacote rejeitado: dados incompletos", "warning", pacote_id=pacote_id, sessao_id=sessao_id)
        
        return

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        audio_data = base64.b64decode(audio_data)
        # Verifica status atual
        cursor.execute("""
            SELECT status FROM complete_transcriptions 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, (sessao_id, patient_id, necessidade))
        result = cursor.fetchone()

        if result:
            current_status = result[0]
            if current_status != "pendente":
                add_log("Pacote ignorado: status não é pendente", "info", pacote_id=pacote_id, status=current_status)
                await websocket.send_json({"type": "transcription_status", "pacote_id": pacote_id, "status": "ignorado"})
                return
        else:
            # Cria nova entrada em complete_transcriptions
            cursor.execute("""
                INSERT INTO complete_transcriptions (sessao_id, patient_id, necessidade, transcricao_completa, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (sessao_id, patient_id, necessidade, '', 'pendente'))
            add_log(
                "Nova transcrição iniciada",
                "info",
                sessao_id=sessao_id,
                patient_id=patient_id,
                necessidade=necessidade,
                status="pendente"
            )
        # Insere o pacote
        cursor.execute("""
            INSERT INTO transcriptions (pacote_id, sessao_id, patient_id, necessidade, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (pacote_id, sessao_id, patient_id, necessidade, 'pendente'))
        connection.commit()

        # add_log(f"Pacote {pacote_id} recebido e enfileirado.")
        # Atualiza status
        cursor.execute("""
            UPDATE transcriptions SET status = 'processando' WHERE pacote_id = %s
        """, (pacote_id,))
        connection.commit()

        # Envia para Celery
        transcrever_audio_task.delay(audio_data, pacote_id, sessao_id, patient_id, necessidade)
        await websocket.send_json({"type": "transcription_status", "pacote_id": pacote_id, "status": "enfileirado"})

    except Exception as e:
        connection.rollback()
        await websocket.send_json({"type": "transcription_status", "pacote_id": pacote_id, "status": "erro"})
        add_log("Erro ao processar pacote de áudio", "error", pacote_id=pacote_id, erro=str(e))
    finally:
        cursor.close()
        release_db_connection(connection)


async def handle_parar_gravacao(data, websocket: WebSocket):
    sessao_id = data.get("sessao_id")
    patient_id = data.get("patient_id")
    necessidade = data.get("necessidade")
    duracao_parcial = data.get("duracao_transcricao_parcial")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE duracao_consulta
            SET duracao_transcricao = %s, status = %s
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s;
        """, (duracao_parcial, 'parcial', sessao_id, patient_id, necessidade))
        connection.commit()

        add_log("Atualizada duração parcial no banco", "info", sessao_id=sessao_id, patient_id=patient_id, necessidade=necessidade)
    except Exception as e:
        connection.rollback()
        add_log("Erro ao atualizar duração parcial", "error", erro=str(e), sessao_id=sessao_id, patient_id=patient_id)
    finally:
        cursor.close()
        release_db_connection(connection)

async def handle_verificar_pacotes_pendentes(data, websocket: WebSocket):
    sessao_id = data.get("sessao_id")
    patient_id = data.get("patient_id")
    necessidade = data.get("necessidade")

    if not all([sessao_id, patient_id, necessidade]):
        await websocket.send_json({
            "type": "status_pacotes",
            "status": "error",
            "message": "Dados incompletos."
        })
        add_log(
            "Verificação de pacotes ignorada: dados incompletos",
            "warning",
            sessao_id=sessao_id,
            patient_id=patient_id,
            necessidade=necessidade
        )
        return

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        # 1. Marcar pacotes com mais de 3 segundos como erro_pendente
        cursor.execute("""
            UPDATE transcriptions 
            SET status = 'erro_pendente'
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s 
            AND status IN ('pendente', 'processando')
            AND timestamp < (NOW() - INTERVAL '3 seconds')
        """, (sessao_id, patient_id, necessidade))
        atualizados = cursor.rowcount
        if atualizados > 0:
            add_log(
                "Pacotes marcados como erro por timeout",
                "warning",
                quantidade=atualizados,
                sessao_id=sessao_id,
                necessidade=necessidade
            )

        connection.commit()

        cursor.execute("""
            SELECT COUNT(*) 
            FROM transcriptions 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s 
            AND status IN ('pendente', 'processando')
        """, (sessao_id, patient_id, necessidade))
        pendentes = cursor.fetchone()[0]

        if pendentes == 0:
            await websocket.send_json({
                "type": "status_pacotes",
                "status": "completed",
                "message": "Todos os pacotes foram processados."
            })
        else:
            await websocket.send_json({
                "type": "status_pacotes",
                "status": "pending",
                "message": f"Ainda há {pendentes} pacotes pendentes."
            })
    except Exception as e:
        await websocket.send_json({
            "type": "status_pacotes",
            "status": "error",
            "message": f"Erro: {e}"
        })
        add_log(
            "Erro ao verificar pacotes pendentes",
            "error",
            erro=str(e),
            sessao_id=sessao_id,
            patient_id=patient_id,
            necessidade=necessidade
        )
    finally:
        cursor.close()
        release_db_connection(connection)


async def handle_gerar_relatorio(data, websocket: WebSocket):
    sessao_id = data.get("sessao_id")
    patient_id = data.get("patient_id")
    necessidade = data.get("necessidade")
    profissao = data.get("profissao")
    duracao_consulta = data.get("duracaoConsulta")

    if not all([sessao_id, patient_id, necessidade, profissao]):
        await websocket.send_json({
            "type": "resumo_classificacao",
            "resumo_classificacao": "Erro nos dados enviados."
        })
        add_log("Geração de relatório cancelada: dados incompletos", "warning", sessao_id=sessao_id)
        return

    # Atualiza duração
    dados_paciente = buscar_dados_paciente(sessao_id,patient_id)
    if not dados_paciente:
        await websocket.send_json({
            "type": "resumo_classificacao",
            "resumo_classificacao": "Erro: Dados do paciente não encontrados."
        })
        add_log("Erro: dados do paciente não encontrados para relatório", "error", sessao_id=sessao_id, patient_id=patient_id)
        return

    # Atualiza duração em memória e sobrescreve no Redis
    dados_paciente["duracao_consulta"] = duracao_consulta
    salvar_dados_paciente(sessao_id, patient_id, dados_paciente)



    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        add_log("Iniciando geração de relatório", "info", sessao_id=sessao_id, patient_id=patient_id, necessidade=necessidade)


        # Atualiza status para "transcricao finalizada"
        cursor.execute("""
            UPDATE complete_transcriptions 
            SET status = %s 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, ('transcricao finalizada', sessao_id, patient_id, necessidade))
        connection.commit()

        # Recupera transcrição
        cursor.execute("""
            SELECT transcricao_completa 
            FROM complete_transcriptions 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
            AND status = 'transcricao finalizada'
        """, (sessao_id, patient_id, necessidade))
        transcricao = cursor.fetchone()
        if not transcricao:
            await websocket.send_json({
                "type": "resumo_classificacao",
                "resumo_classificacao": "Erro ao encontrar transcrição."
            })
            add_log("Erro: transcrição não encontrada para geração do relatório", "error", sessao_id=sessao_id, necessidade=necessidade)
            return

        transcricao_texto = transcricao[0]

        resumo = resumir_classificar(transcricao_texto, profissao, necessidade)

        cursor.execute("""
            UPDATE complete_transcriptions 
            SET resumo = %s, status = %s 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, (resumo, 'resumo finalizado', sessao_id, patient_id, necessidade))
        connection.commit()

        relatorio = gerar_relatorio_editavel(
            dados_paciente['nome'],
            dados_paciente['endereco'],
            dados_paciente['dataNascimento'],
            dados_paciente['cpf'],
            resumo,
            dados_paciente['duracao_consulta'],
            necessidade
        )

        cursor.execute("""
            UPDATE duracao_consulta
            SET duracao_transcricao = %s, status = %s
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s;
        """, (dados_paciente['duracao_consulta'], 'duracao final', sessao_id, patient_id, necessidade))
        connection.commit()

        cursor.execute("""
            UPDATE complete_transcriptions 
            SET relatorio = %s, status = %s 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, (relatorio, 'relatório gerado', sessao_id, patient_id, necessidade))
        connection.commit()

        add_log("Relatório gerado com sucesso", "info", sessao_id=sessao_id, patient_id=patient_id, necessidade=necessidade)

        await websocket.send_json({"type": "relatorio_editavel", "relatorio": relatorio})
        await websocket.send_json({"type": "relatorio_status", "status": "success", "message": "Relatório gerado com sucesso!"})
    except Exception as e:
        connection.rollback()
        add_log("Erro ao gerar relatório", "error", erro=str(e), sessao_id=sessao_id, patient_id=patient_id)
        await websocket.send_json({"type": "relatorio_status", "status": "error", "message": f"Erro: {e}"})
        
    finally:
        cursor.close()
        release_db_connection(connection)


async def handle_preparar_relatorio(data, websocket: WebSocket):
    sessao_id = data.get("sessao_id")
    patient_id = data.get("patient_id")
    necessidade = data.get("necessidade")
    relatorio_editado = data.get("relatorio_editado")

    if not all([sessao_id, patient_id, necessidade, relatorio_editado]):
        await websocket.send_json({"type": "baixar_relatorio_status", "status": "error", "message": "Dados incompletos."})
        add_log("Preparação do relatório falhou: dados incompletos", "warning", sessao_id=sessao_id)
        return

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE complete_transcriptions 
            SET relatorio = %s, status = %s 
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s
        """, (relatorio_editado, 'relatório finalizado', sessao_id, patient_id, necessidade))
        connection.commit()
        
        add_log("Relatório final salvo com sucesso", "info", sessao_id=sessao_id, necessidade=necessidade)
        await websocket.send_json({"type": "baixar_relatorio_status", "status": "success", "message": "Relatório salvo com sucesso."})

    except Exception as e:
        connection.rollback()
        add_log("Erro ao salvar relatório finalizado", "error", erro=str(e), sessao_id=sessao_id, necessidade=necessidade)
        await websocket.send_json({"type": "baixar_relatorio_status", "status": "error", "message": f"Erro ao salvar: {e}"})
    finally:
        cursor.close()
        release_db_connection(connection)

async def handle_nova_consulta(data, websocket: WebSocket):
    sessao_id = data.get("sessao_id")
    patient_id = data.get("patient_id")

    # Reset local
    deletar_dados_paciente(sessao_id,patient_id)

    # Limpa controle de sessão da memória
    ultimos_pings.pop(sessao_id, None)
    session_metadata.pop(sessao_id, None)

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            DELETE FROM transcriptions WHERE sessao_id = %s AND status = %s
        """, (sessao_id, 'enviado_tabela_completa'))
        cursor.execute("""
            DELETE FROM complete_transcriptions WHERE sessao_id = %s AND status = %s
        """, (sessao_id, 'relatório baixado'))
        connection.commit()
        
        await websocket.send_json({"type": "nova_consulta_status", "status": "success"})
        add_log("Nova consulta iniciada: dados antigos apagados e memória resetada", "info", sessao_id=sessao_id)
    except Exception as e:
        connection.rollback()
        add_log("Erro ao reiniciar consulta", "error", erro=str(e), sessao_id=sessao_id)
        await websocket.send_json({"type": "nova_consulta_status", "status": "error", "message": str(e)})
    finally:
        cursor.close()
        release_db_connection(connection)


async def verificar_timeouts():
    while True:
        await asyncio.sleep(5)  # Verifica a cada 5 segundos
        agora = datetime.now()
        desconectados = []

        for sessao_id, ultimo_ping in list(ultimos_pings.items()):
            if (agora - ultimo_ping) > timedelta(seconds=16):
                metadata = session_metadata.get(sessao_id)
                if metadata:
                    status = await obter_status_da_sessao(sessao_id, metadata["patient_id"], metadata["necessidade"])
                    
                    if status == 'pendente':
                        await registrar_timeout_backend(sessao_id, metadata)

                    # Independente de ser pendente ou não, desconecta da memória para limpar
                    desconectados.append(sessao_id)

        # Remove sessões desconectadas da memória
        for sessao_id in desconectados:
            ultimos_pings.pop(sessao_id, None)
            session_metadata.pop(sessao_id, None)

async def registrar_timeout_backend(sessao_id, metadata):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Calcula a duração entre o início da gravação e agora
        start_time = metadata.get("start_time_backend")
        if not start_time:
            duracao_calculada = "00:00:00"
        else:
            tempo_total = datetime.now() - start_time
            total_segundos = int(tempo_total.total_seconds())
            horas = total_segundos // 3600
            minutos = (total_segundos % 3600) // 60
            segundos = total_segundos % 60
            duracao_calculada = f"{horas:02}:{minutos:02}:{segundos:02}"

        # Atualiza a tabela duracao_consulta
        cursor.execute("""
            UPDATE duracao_consulta
            SET duracao_transcricao = %s, status = %s
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s;
        """, (
            duracao_calculada,
            'erro_frontend',
            sessao_id,
            metadata["patient_id"],
            metadata["necessidade"]
        ))
        connection.commit()
        add_log("Timeout detectado, marcada duração via backend", "warning", sessao_id=sessao_id, patient_id=metadata["patient_id"], necessidade=metadata["necessidade"])
    except Exception as e:
        connection.rollback()
        add_log("Erro ao registrar timeout backend", "error", erro=str(e), sessao_id=sessao_id)
    finally:
        cursor.close()
        release_db_connection(connection)

async def obter_status_da_sessao(sessao_id, patient_id, necessidade):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            SELECT status
            FROM duracao_consulta
            WHERE sessao_id = %s AND patient_id = %s AND necessidade = %s;
        """, (sessao_id, patient_id, necessidade))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
        return None
    except Exception as e:
        add_log("Erro ao buscar status da sessão para timeout", "error", erro=str(e), sessao_id=sessao_id)
        return None
    finally:
        cursor.close()
        release_db_connection(connection)