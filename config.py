import os
class Config:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    # Substitua 'seu_usuario', 'sua_senha' e 'nome_do_seu_banco_de_dados'
    # pelo que você configurou no MySQL.
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:senai@localhost/mathmagic'
    SQLALCHEMY_TRACK_MODIFICATIONS = False