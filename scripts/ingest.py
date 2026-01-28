import os
import sys
# O import correto para a versão nova:
from langchain_pinecone import PineconeVectorStore 
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter # <-- ADICIONE ESTA LINHA
from langchain_pinecone import PineconeVectorStore
from app.core.config import settings

# Adiciona a raiz do projeto ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def ingest_hierarchical_knowledge():
    print("🚀 Iniciando ingestão hierárquica por Administradora...")
    os.environ["PINECONE_API_KEY"] = settings.PINECONE_API_KEY
    
    # Caminho raiz: \base_conhecimento\Administradoras
    base_dir = "base_conhecimento/Administradoras"
    all_chunks = []

    # 1. Percorre as pastas das Administradoras (Ademicon, Porto Seguro, etc.)
    for admin_name in os.listdir(base_dir):
        admin_path = os.path.join(base_dir, admin_name)
        
        if os.path.isdir(admin_path):
            print(f"📁 Processando Administradora: {admin_name}")
            
            # 2. Carrega arquivos da RAIZ da pasta (Institucional)
            # Usamos glob="*" para pegar arquivos direto na pasta da admin
            root_loader = DirectoryLoader(admin_path, glob="./*.pdf", loader_cls=PyPDFLoader)
            root_docs = root_loader.load()
            
            for doc in root_docs:
                doc.metadata["administradora"] = admin_name
                doc.metadata["categoria"] = "Institucional"
            
            # 3. Carrega arquivos da pasta TABELAS
            tables_path = os.path.join(admin_path, "Tabelas")
            if os.path.exists(tables_path):
                print(f"   📊 Carregando tabelas de {admin_name}...")
                tables_loader = DirectoryLoader(tables_path, glob="**/*.pdf", loader_cls=PyPDFLoader)
                table_docs = tables_loader.load()
                
                for doc in table_docs:
                    doc.metadata["administradora"] = admin_name
                    doc.metadata["categoria"] = "Tabela de Preços"
                    # Captura se é Imóvel, Automóvel, etc (pela subpasta de Tabelas)
                    subcat = os.path.basename(os.path.dirname(doc.metadata.get("source", "")))
                    doc.metadata["subcategoria"] = subcat if subcat != "Tabelas" else "Geral"

                root_docs.extend(table_docs)

            # 4. Quebrar em Chunks e adicionar ao lote final
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
            chunks = text_splitter.split_documents(root_docs)
            all_chunks.extend(chunks)

    # 5. Enviar para o Pinecone
    if all_chunks:
        
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.OPENAI_API_KEY
        )
        print(f"📡 Enviando {len(all_chunks)} blocos para o Pinecone...")
        PineconeVectorStore.from_documents(
            all_chunks, 
            embeddings, 
            index_name="barcelona-index"
        )
        print("✅ Base de conhecimento atualizada com sucesso!")

if __name__ == "__main__":
    ingest_hierarchical_knowledge()