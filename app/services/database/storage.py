# app/services/database/storage.py
from azure.data.tables import TableClient
from azure.core.exceptions import ResourceExistsError
from app.core.config import settings
import uuid
from datetime import datetime
import pytz

class LeadsRepository:
    def __init__(self):
        # Conecta no Azure (ou no emulador local)
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        self.table_name = "BarcelonaLeads"
        
        try:
            self.client = TableClient.from_connection_string(
                conn_str=self.connection_string, 
                table_name=self.table_name
            )
            # Tenta criar a tabela se ela não existir
            try:
                self.client.create_table()
            except ResourceExistsError:
                pass # Tabela já existe, segue o jogo
        except Exception as e:
            print(f"⚠️ Erro ao conectar no Table Storage: {e}")
            self.client = None

    def save_lead(self, phone: str, name: str, status: str, summary: str):
        if not self.client:
            print("❌ Banco de dados offline. Lead não salvo.")
            return

        # No Table Storage, PartitionKey + RowKey é a chave primária
        entity = {
            "PartitionKey": "Leads2026", # Agrupador (pode ser o Ano ou Mês)
            "RowKey": phone,             # O telefone é único por pessoa
            "Name": name,
            "Status": status,
            "LastSummary": summary,
            "UpdatedAt": datetime.now(pytz.utc).isoformat()
        }

        # upsert_entity = Cria se não existe, Atualiza se já existe
        self.client.upsert_entity(mode="merge", entity=entity)
        print(f"💾 Lead {name} ({phone}) salvo no Azure Table Storage!")

    def get_lead(self, phone: str):
        if not self.client: return None
        try:
            return self.client.get_entity(partition_key="Leads2026", row_key=phone)
        except:
            return None # Não encontrado