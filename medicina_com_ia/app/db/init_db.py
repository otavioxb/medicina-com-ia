from app.db.database import get_db_connection, release_db_connection
from app.modules.utils import add_log
from uuid import uuid4
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_tables():
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level VARCHAR(10) NOT NULL,
                message TEXT NOT NULL,
                context JSONB
            );
        ''')

        cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                uid UUID PRIMARY KEY,
                nome TEXT NOT NULL,
                cpf VARCHAR(14) UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                data_nascimento DATE,
                profissao VARCHAR(100),
                empresa VARCHAR(18),
                data_criacao DATE DEFAULT CURRENT_DATE
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                    sessao_id UUID PRIMARY KEY,
                    uid UUID NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_status BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (uid) REFERENCES users(uid) ON DELETE CASCADE
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS complete_transcriptions (
                sessao_id UUID NOT NULL,
                patient_id UUID NOT NULL,
                necessidade VARCHAR(100) NOT NULL,
                transcricao_completa TEXT DEFAULT '',
                resumo TEXT,
                relatorio TEXT,
                status VARCHAR(50) DEFAULT 'pendente',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (sessao_id, patient_id, necessidade)
            );
        ''')

        cursor.execute('''
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
               NEW.updated_at = CURRENT_TIMESTAMP;
               RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        ''')

        cursor.execute('''
            DROP TRIGGER IF EXISTS trigger_updated_at ON complete_transcriptions;
        ''')

        cursor.execute('''
            CREATE TRIGGER trigger_updated_at
            BEFORE UPDATE ON complete_transcriptions
            FOR EACH ROW
            EXECUTE PROCEDURE update_updated_at_column();
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcriptions (
                pacote_id BIGINT NOT NULL,
                sessao_id UUID NOT NULL,
                patient_id UUID NOT NULL,
                necessidade VARCHAR(100) NOT NULL,
                status VARCHAR(50) DEFAULT 'pendente',
                transcription TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (pacote_id, sessao_id, patient_id, necessidade),
                FOREIGN KEY (sessao_id, patient_id, necessidade) 
                    REFERENCES complete_transcriptions(sessao_id, patient_id, necessidade)
                    ON DELETE CASCADE
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cartoes_credito (
                id UUID PRIMARY KEY,
                uid UUID NOT NULL,
                numero_ultimos4 VARCHAR(4) NOT NULL,
                validade DATE NOT NULL,
                nome_impresso TEXT NOT NULL,
                token_gateway TEXT NOT NULL,
                ativo BOOLEAN DEFAULT TRUE,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (uid) REFERENCES users(uid) ON DELETE CASCADE
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS duracao_consulta (
                id SERIAL PRIMARY KEY,
                sessao_id UUID NOT NULL,
                patient_id UUID NOT NULL,
                necessidade VARCHAR(255) NOT NULL,
                duracao_transcricao TEXT NOT NULL DEFAULT '00:00:00',
                data DATE NOT NULL DEFAULT CURRENT_DATE,
                status VARCHAR(50) DEFAULT 'pendente',
                FOREIGN KEY (sessao_id) REFERENCES sessions(sessao_id) ON DELETE CASCADE,
                UNIQUE (sessao_id, patient_id, necessidade)
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dados_paciente (
                sessao_id UUID NOT NULL,
                patient_id UUID NOT NULL,
                dados JSONB NOT NULL,
                data_cache TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (sessao_id, patient_id)
            );
        ''')
        senha_admin_hash = pwd_context.hash("teste1234")
        cursor.execute('''
            INSERT INTO users (uid, nome, cpf, email, senha, data_nascimento, profissao, empresa)
            VALUES (%s, %s, %s, %s, %s, CURRENT_DATE, %s, NULL)
            ON CONFLICT (email) DO NOTHING;
        ''', (
            str(uuid4()),
            "Otavio Barbosa",
            "000.000.000-00",
            "otavioxb@gmail.com",
            senha_admin_hash,
            "Administrador"
        ))

        with open("app/db/views.sql", "r") as file:
            view_sql = file.read()
            cursor.execute(view_sql)

        connection.commit()
        add_log("Criação de tabelas, views e Admin concluída com sucesso.", "info")

    except Exception as e:
        connection.rollback()
        add_log("Erro ao criar tabelas ou Admin no banco", "error", erro=str(e))
    finally:
        cursor.close()
        release_db_connection(connection)
