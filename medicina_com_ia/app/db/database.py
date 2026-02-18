import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DB_MIN_CONN = int(os.getenv("DB_MIN_CONN", "1"))
DB_MAX_CONN = int(os.getenv("DB_MAX_CONN", "10"))

if DATABASE_URL:
    db_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=DB_MIN_CONN,
        maxconn=DB_MAX_CONN,
        dsn=DATABASE_URL
    )
else:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", os.getenv("PGDATABASE", "transcricao"))
    DB_USER = os.getenv("DB_USER", os.getenv("PGUSER", "postgres"))
    DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("PGPASSWORD", "postgres"))
    DB_PORT = os.getenv("DB_PORT", os.getenv("PGPORT", "5432"))

    db_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=DB_MIN_CONN,
        maxconn=DB_MAX_CONN,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

def get_db_connection():
    try:
        conn = db_pool.getconn()
        return conn
    except Exception as e:
        raise RuntimeError(f"Erro ao obter conexão com o banco: {e}")

def release_db_connection(conn):
    if conn:
        db_pool.putconn(conn)

def close_all_connections():
    db_pool.closeall()
