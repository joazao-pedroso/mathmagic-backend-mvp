import os

class Config:
    # Substitua 'seu_usuario', 'sua_senha' e 'nome_do_seu_banco_de_dados'
    # pelo que você configurou no MySQL.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:senai@localhost/mathmagic'
    SQLALCHEMY_TRACK_MODIFICATIONS = False