from app.db.session import engine
from app.models.lead import Base

def init_db():
    print("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso!")

if __name__ == "__main__":
    init_db()
