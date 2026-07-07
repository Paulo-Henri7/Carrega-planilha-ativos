TABELA = "ativoscomputadores.default.ativos"
TABELA_AUDITORIA = "ativoscomputadores.default.ativos_auditoria"
TABELA_BACKUP = "ativoscomputadores.default.ativos_backup"

HTTP_PATH = "/sql/1.0/warehouses/6c58b63171eb4304"

MODIFICACOES_POR_BACKUP = 10

# Todas as colunas da tabela de ativos, na ordem usada nos formulários e telas
COLUNAS = [
    "patrimonio",
    "hostname",
    "data_entrega",
    "cc",
    "unidade",
    "responsavel",
    "cargo",
    "tipo",
    "modelo",
    "status",
    "num_pedido",
    "nota_fiscal",
    "dt_compra",
    "dt_garantia",
    "gestor",
]

# Subconjunto de campos obrigatórios no cadastro, edição e upload de planilha.
# Ajuste esta lista se quiser exigir mais (ou menos) campos.
COLUNAS_OBRIGATORIAS = [
    "patrimonio",
    "tipo",
    "modelo",
    "responsavel",
]

# Colunas do tipo DATE — usadas para exibir o widget de calendário correto
# e para conversão de tipo em uploads de planilha.
COLUNAS_DATA = [
    "data_entrega",
    "dt_compra",
    "dt_garantia",
]

# Rótulos amigáveis exibidos na interface (chave = nome da coluna no banco)
ROTULOS = {
    "patrimonio": "Patrimônio",
    "hostname": "Hostname",
    "data_entrega": "Data de Entrega",
    "cc": "CC",
    "unidade": "Unidade",
    "responsavel": "Colaborador",
    "cargo": "Cargo",
    "tipo": "Tipo Equip.",
    "modelo": "Modelo",
    "status": "ST",
    "num_pedido": "Num Pedido",
    "nota_fiscal": "Nota Fiscal",
    "dt_compra": "Dt Compra",
    "dt_garantia": "Dt Garantia",
    "gestor": "Gestor",
}