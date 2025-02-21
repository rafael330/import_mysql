import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import errorcode
import os

# Configuração da página
st.set_page_config(page_title="Upload de Dados para MySQL", page_icon="📊")
st.title("Upload de Dados para MySQL")

# Função para carregar o arquivo e selecionar a aba (se for Excel)
def load_file(file_path, file_type, sheet_name=None):
    if file_type == "xlsx":
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    elif file_type == "txt":
        df = pd.read_csv(file_path, delimiter='\t')
    return df

# Função para conectar ao MySQL
def connect_to_mysql(db_name=None):
    return mysql.connector.connect(
        user='root',  # Substitua pelo usuário do MySQL
        password='@Kaclju2125.',  # Substitua pela senha do MySQL
        host='0.tcp.sa.ngrok.io',  # Endereço público gerado pelo Ngrok
        port=10352,  # Porta gerada pelo Ngrok
        database=db_name,  # Banco de dados dinâmico
        unix_socket=None  # Força a conexão TCP/IP
    )

# Função principal para upload de dados
def upload_data(file_path, file_type, sheet_name, db_name, table_name):
    if not file_path or not os.path.exists(file_path):
        st.error("Caminho do arquivo inválido ou arquivo não encontrado.")
        return

    if file_type not in ["xlsx", "txt"]:
        st.error("Tipo de arquivo inválido. Use 'xlsx' ou 'txt'.")
        return

    if not db_name or not table_name:
        st.error("Nome do banco de dados e da tabela são obrigatórios.")
        return

    cursor = None
    cnx = None
    try:
        # Conectar ao MySQL
        cnx = connect_to_mysql()
        cursor = cnx.cursor()

        # Verificar e criar banco de dados se não existir
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.execute(f"USE {db_name}")

        # Verificar se a tabela já existe
        cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        table_exists = cursor.fetchone()

        # Se a tabela existir, excluí-la
        if table_exists:
            cursor.execute(f"DROP TABLE `{table_name}`")
            st.info(f"Tabela '{table_name}' existente foi excluída para substituição.")

        # Ler dados do arquivo
        df = load_file(file_path, file_type, sheet_name)

        # Verificar se o DataFrame está vazio
        if df.empty:
            st.warning("O arquivo está vazio ou não contém dados.")
            return

        # Adicionar coluna 'id' se não existir
        if 'id' not in df.columns:
            df.insert(0, 'id', None)  # Adiciona a coluna 'id' no início do DataFrame

        # Definir tipos de colunas dinamicamente
        columns_with_types = []
        for col in df.columns:
            if col == 'id':
                columns_with_types.append('`id` INT AUTO_INCREMENT PRIMARY KEY')  # Coluna 'id' como chave primária
            else:
                max_length = df[col].apply(lambda x: len(str(x)) if x else 0).max()
                if max_length <= 255:
                    columns_with_types.append(f'`{col}` VARCHAR(255)')
                else:
                    columns_with_types.append(f'`{col}` TEXT')

        # Criar a tabela com a nova estrutura
        cursor.execute(f"""
            CREATE TABLE `{table_name}` (
                {', '.join(columns_with_types)}
            )
        """)

        # Inserir ou substituir dados na tabela
        for _, row in df.iterrows():
            # Substituir NaN por None (NULL no MySQL)
            row = [None if pd.isna(value) else value for value in row]
            # Remover o valor da coluna 'id' para permitir auto-incremento
            if 'id' in df.columns:
                row = row[1:]  # Remove o valor da coluna 'id'
            placeholders = ', '.join(['%s'] * len(row))
            columns = ', '.join([f'`{col}`' for col in df.columns if col != 'id'])
            values = tuple(row)
            cursor.execute(f"""
                INSERT INTO `{table_name}` ({columns}) 
                VALUES ({placeholders})
            """, values)

        cnx.commit()
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

# Interface do Streamlit
uploaded_file = st.file_uploader("Selecione o arquivo (.xlsx ou .txt)", type=["xlsx", "txt"])

if uploaded_file:
    file_path = uploaded_file.name
    file_type = "xlsx" if file_path.endswith(".xlsx") else "txt"

    # Salvar o arquivo temporariamente
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Selecionar a aba (se for Excel)
    sheet_name = None
    if file_type == "xlsx":
        workbook = pd.ExcelFile(file_path)
        sheet_names = workbook.sheet_names
        sheet_name = st.selectbox("Selecione a aba", sheet_names)

    # Nome do banco de dados e da tabela
    db_name = st.text_input("Nome do Banco de Dados")
    table_name = st.text_input("Nome da Tabela")

    # Botão para upload
    if st.button("Upload"):
        upload_data(file_path, file_type, sheet_name, db_name, table_name)

    # Remover o arquivo temporário após o uso
    os.remove(file_path)
