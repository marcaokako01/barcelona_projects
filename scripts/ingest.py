# scripts/ingest.py
import os
import sys

# --- HACK PARA CORRIGIR O BUG DO WINDOWS (PWD) ---
try:
    import pwd
except ImportError:
    import types
    mock_pwd = types.ModuleType('pwd')
    def getpwuid(uid): return ["mock_user"]
    mock_pwd.getpwuid = getpwuid
    sys.modules['pwd'] = mock_pwd
# -------------------------------------------------

# Adiciona a raiz do projeto ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders.text import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings
import time

def ingest_data():
    print("🚀 Iniciando ingestão de conhecimento...")

    # --- CORREÇÃO DO ERRO DE API KEY ---
    # Força a chave para as variáveis de ambiente, onde a biblioteca procura
    os.environ["PINECONE_API_KEY"] = settings.PINECONE_API_KEY
    # -----------------------------------

    # 1. Carregar o Texto
    file_path = "knowledge_base/manual_barcelona.txt"
    if not os.path.exists(file_path):
        print(f"❌ Erro: Arquivo {file_path} não encontrado.")
        return

    try:
        loader = TextLoader(file_path, encoding="utf-8")
        documents = loader.load()
    except Exception as e:
        print(f"❌ Erro ao ler o arquivo: {e}")
        return
    
    # 2. Quebrar em pedaços menores (Chunks)
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)
    print(f"📄 Documento quebrado em {len(docs)} pedaços.")

    # 3. Inicializar Pinecone
    try:
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        index_name = "barcelona-index"

        # Criar índice se não existir
        existing_indexes = [i.name for i in pc.list_indexes()]
        if index_name not in existing_indexes:
            print(f"📦 Criando índice '{index_name}' no Pinecone...")
            pc.create_index(
                name=index_name,
                dimension=1536,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=settings.PINECONE_ENV)
            )
            print("⏳ Aguardando 15 segundos para o índice estar pronto...")
            time.sleep(15) 
        else:
            print(f"✅ Índice '{index_name}' já existe.")

        # 4. Vetorizar e Salvar
        embeddings = OpenAIEmbeddings(
            api_key=settings.OPENAI_API_KEY,
            model="text-embedding-3-small"
        )

        print("📡 Enviando para o Pinecone...")
        # AQUI OCORRIA O ERRO, AGORA VAI FUNCIONAR POIS SETAMOS O ENVIRON
        PineconeVectorStore.from_documents(docs, embeddings, index_name=index_name)
        
        print("✅ SUCESSO! O conhecimento foi ingerido no Pinecone.")
        
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")

if __name__ == "__main__":
    ingest_data()