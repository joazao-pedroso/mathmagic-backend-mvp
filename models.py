from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Aluno(db.Model):
    __tablename__ = 'Aluno'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False, name='senha')  # Hash da senha

    def __repr__(self):
        return f'<Aluno {self.nome}>'

    @property
    def senha(self):
        raise AttributeError('senha: campo de leitura negada')

    @senha.setter
    def senha(self, senha_texto_puro):
        self.senha_hash = generate_password_hash(senha_texto_puro)

    def verificar_senha(self, senha_texto_puro):
        return check_password_hash(self.senha_hash, senha_texto_puro)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'email': self.email
        }

class Trilha(db.Model):
    __tablename__ = 'Trilha'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.Text)
    
    jogos = db.relationship('Jogo', backref='trilha', lazy=True)

    def __repr__(self):
        return f'<Trilha {self.nome}>'

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao
        }

class Jogo(db.Model):
    __tablename__ = 'Jogo'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.Text)
    trilha_id = db.Column(db.Integer, db.ForeignKey('Trilha.id'), nullable=False)
    
    desempenhos = db.relationship('DesempenhoJogo', backref='jogo', lazy=True)

    def __repr__(self):
        return f'<Jogo {self.nome}>'

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'trilha_id': self.trilha_id
        }

class DesempenhoJogo(db.Model):
    __tablename__ = 'DesempenhoJogo'
    id = db.Column(db.Integer, primary_key=True)
    
    aluno_id = db.Column(db.Integer, db.ForeignKey('Aluno.id'), nullable=False)
    aluno = db.relationship('Aluno', backref='desempenhos', lazy=True)
    
    jogo_id = db.Column(db.Integer, db.ForeignKey('Jogo.id'), nullable=False)
    trilha_id = db.Column(db.Integer, db.ForeignKey('Trilha.id'), nullable=False)
    
    data_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    passou = db.Column(db.Boolean, nullable=False)
    acertos = db.Column(db.JSON, nullable=True)
    erros = db.Column(db.JSON, nullable=True)
    
    trilha = db.relationship('Trilha', foreign_keys=[trilha_id], backref='desempenhos_trilha', lazy=True)

    def __repr__(self):
        return f'<DesempenhoJogo Aluno: {self.aluno_id}, Jogo: {self.jogo_id}, Trilha: {self.trilha_id}, Passou: {self.passou}>'

    def to_dict(self):
        return {
            'id': self.id,
            'aluno_id': self.aluno_id,
            'jogo_id': self.jogo_id,
            'trilha_id': self.trilha_id,
            'data_hora': self.data_hora.isoformat() if self.data_hora else None,
            'passou': self.passou,
            'acertos': self.acertos,
            'erros': self.erros
        }
