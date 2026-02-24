import pandas as pd

# 1. Configuração do Teste
ARQUIVO_CSV = 'C:/Users/z3xai/Downloads/produto/tabelas_consorcio_202602231827.csv' # Certifique-se que o arquivo está na mesma pasta

# 2. O Mapa de Categorias (Exatamente como no seu tools.py)
mapa = {
    "veiculo": "AUTO", "veículo": "AUTO", "veiculos": "AUTO", "veículos": "AUTO",
    "carro": "AUTO", "auto": "AUTO", "automovel": "AUTO", "automóvel": "AUTO",
    "caminhao": "PESADOS", "caminhão": "PESADOS", "pesados": "PESADOS", "pesado": "PESADOS",
    "imovel": "IMOVEIS", "imóvel": "IMOVEIS", "imoveis": "IMOVEIS", "imóveis": "IMOVEIS",
    "casa": "IMOVEIS", "apartamento": "IMOVEIS",
    "moto": "MOTO", "motos": "MOTO", "motocicleta": "MOTO",
    "geral": "GERAL", "todos": "GERAL"
}

def simular_get_table_pricing(produto_input, valor_input):
    print(f"\n🔍 SIMULANDO: {produto_input} de R$ {valor_input:,.2f}")
    
    # Carrega o CSV
    df = pd.read_csv(ARQUIVO_CSV)
    
    # Normalização
    termo_ia = str(produto_input).strip().lower()
    categoria_banco = mapa.get(termo_ia, termo_ia.upper())
    
    # Simula o SQL: WHERE UPPER(TRIM(produto)) = %s
    # Isso limpa espaços invisíveis que podem vir do CSV
    filtro = df[df['produto'].str.strip().str.upper() == categoria_banco.strip().upper()].copy()
    
    if filtro.empty:
        return f"❌ ERRO: Produto '{categoria_banco}' não encontrado no banco."
    
    # Simula o ORDER BY ABS(credito - valor) LIMIT 3
    filtro['distancia'] = (filtro['credito'] - valor_input).abs()
    resultados = filtro.sort_values(by='distancia').head(3)
    
    # Formatação da Mensagem
    msg = f"--- RESULTADO PARA {categoria_banco} ---\n"
    for _, row in resultados.iterrows():
        credito = f"R$ {row['credito']:,.2f}"
        parcela = f"R$ {row['parcela_inteira']:,.2f}"
        msg += f"• Crédito: {credito} | Parcela: {parcela} em {row['prazo']} meses\n"
    
    return msg

# --- ÁREA DE TESTES ---
if __name__ == "__main__":
    # Teste 1: Imóvel de 1 Milhão (O que estava falhando)
    print(simular_get_table_pricing("imovel", 1000000))
    
    # Teste 2: Carro de 180 mil
    print(simular_get_table_pricing("carro", 180000))
    
    # Teste 3: Caminhão (Pesados)
    print(simular_get_table_pricing("caminhão", 450000))