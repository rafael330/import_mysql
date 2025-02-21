import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import errorcode
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import tempfile
import os

# Configuração da página
st.set_page_config(page_title="Upload de Dados do Google Sheets para MySQL", page_icon="📊")
st.title("Upload de Dados do Google Sheets para MySQL")

# Função para carregar dados do Google Sheets
def get_google_sheet_data(credentials_path, sheet_url, sheet_name):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_file(credentials_path, scopes=scope)
        client = gspread.authorize(credentials)
        spreadsheet_id = sheet_url.split('/d/')[1].split('/')[0]
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Substituir valores infinitos ou NaN
        df.replace([float('inf'), -float('inf')], None, inplace=True)
        df.fillna('', inplace=True)  # Preencher NaN com string vazia ou valor adequado

        return df
    except gspread.exceptions.APIError as api_err:
        st.error(f"Erro de API: {api_err}")
        raise
    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")
        raise

# Função para conectar ao MySQL
def connect_to_mysql(db_name=None):
    return mysql.connector.connect(
        user='root',  # Substitua pelo usuário do MySQL
        password='@Kaclju2125.',  # Substitua pela senha do MySQL
        host='0.tcp.sa.ngrok.io',  # Endereço público gerado pelo Ngrok
        port=11043,  # Porta gerada pelo Ngrok
        database=db_name,  # Banco de dados dinâmico
        unix_socket=None  # Força a conexão TCP/IP
    )

# Função para mapear tipos de dados do DataFrame para tipos do MySQL
def map_dtype(dtype):
    if dtype == 'object':
        return 'TEXT(255)'
    elif dtype.startswith('int'):
        return 'INT'
    elif dtype.startswith('float'):
        return 'FLOAT'
    else:
        return 'TEXT(255)'

# Função principal para upload de dados
def upload_data(credentials_file, sheet_url, sheet_name, db_name, table_name):
    cursor = None
    cnx = None
    try:
        # Salvar o arquivo de credenciais temporariamente
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_file:
            tmp_file.write(credentials_file.getvalue())
            credentials_path = tmp_file.name

        # Conectar ao MySQL
        cnx = connect_to_mysql()
        cursor = cnx.cursor()

        # Verificar e criar banco de dados se não existir
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.execute(f"USE {db_name}")

        # Carregar dados do Google Sheets
        df = get_google_sheet_data(credentials_path, sheet_url, sheet_name)

        # Verificar se o DataFrame está vazio
        if df.empty:
            st.warning("O arquivo está vazio ou não contém dados.")
            return

        # Adicionar coluna 'ID' se não existir
        if 'ID' not in df.columns:
            df.insert(0, 'ID', range(1, len(df) + 1))  # Cria uma coluna 'ID' com valores únicos

        # Confirmar que não há valores infinitos ou NaN nos dados
        df.replace([float('inf'), -float('inf')], None, inplace=True)
        df.fillna('', inplace=True)  # Preencher NaN com string vazia ou valor adequado

        # Remover linhas duplicadas
        df.drop_duplicates(subset=['ID'], inplace=True)  # Remove duplicatas com base na coluna 'ID'

        # Criar a tabela se não existir
        columns_with_types = ', '.join([f'{col} {map_dtype(df[col].dtype.name)}' for col in df.columns])
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {columns_with_types},
                PRIMARY KEY (ID)
            )
        """)

        # Inserir ou atualizar dados em lotes
        batch_size = 10000  # Tamanho do lote para inserção
        for i in range(0, len(df), batch_size):
            batch = df[i:i + batch_size]
            values = [tuple(row) for row in batch.to_numpy()]
            placeholders = ', '.join(['%s'] * len(df.columns))
            update_columns = ', '.join([f'{col}=VALUES({col})' for col in df.columns])
            cursor.executemany(f"""
                INSERT INTO {table_name} ({', '.join(df.columns)}) 
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE
                {update_columns}
            """, values)
            cnx.commit()
            st.info(f"Linhas {i + 1} a {i + len(batch)} inseridas/atualizadas com sucesso.")

        st.success("Dados enviados e tabela atualizada com sucesso.")
    except mysql.connector.Error as err:
        st.error(f"Erro no MySQL: {err}")
    except Exception as e:
        st.error(f"Erro inesperado: {e}")
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()
        # Remover o arquivo temporário após o uso
        if credentials_path:
            os.unlink(credentials_path)

# Interface do Streamlit
st.sidebar.header("Configurações do Google Sheets")
credentials_file = st.sidebar.file_uploader("Carregar arquivo de credenciais JSON", type=["json"])
sheet_url = st.sidebar.text_input("URL do Google Sheets")
sheet_name = st.sidebar.text_input("Nome da Aba")

st.sidebar.header("Configurações do MySQL")
db_name = st.sidebar.text_input("Nome do Banco de Dados")
table_name = st.sidebar.text_input("Nome da Tabela")

if st.sidebar.button("Upload"):
    if credentials_file and sheet_url and sheet_name and db_name and table_name:
        upload_data(credentials_file, sheet_url, sheet_name, db_name, table_name)
    else:
        st.error("Por favor, preencha todos os campos obrigatórios.")
