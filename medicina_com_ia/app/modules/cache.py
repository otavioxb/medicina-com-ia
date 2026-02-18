from app.db.database import get_db_connection, release_db_connection
import json


def salvar_dados_paciente(sessao_id: str, patient_id: str, dados: dict):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute('''
            INSERT INTO dados_paciente (sessao_id, patient_id, dados)
            VALUES (%s, %s, %s)
            ON CONFLICT (sessao_id, patient_id) DO UPDATE
            SET dados = EXCLUDED.dados,
                data_cache = CURRENT_TIMESTAMP;
        ''', (sessao_id, patient_id, json.dumps(dados)))
        connection.commit()
    finally:
        cursor.close()
        release_db_connection(connection)


def buscar_dados_paciente(sessao_id: str, patient_id: str) -> dict | None:
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute('''
            SELECT dados FROM dados_paciente
            WHERE sessao_id = %s AND patient_id = %s;
        ''', (sessao_id, patient_id))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()
        release_db_connection(connection)


def deletar_dados_paciente(sessao_id: str, patient_id: str):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute('''
            DELETE FROM dados_paciente
            WHERE sessao_id = %s AND patient_id = %s;
        ''', (sessao_id, patient_id))
        connection.commit()
    finally:
        cursor.close()
        release_db_connection(connection)
