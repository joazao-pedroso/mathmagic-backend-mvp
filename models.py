from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Tabela de junção para a relação muitos-para-muitos entre Sala e Trilha
sala_trilha_association = db.Table('sala_trilha',
    db.Column('sala_id', db.Integer, db.ForeignKey('sala.id')),
    db.Column('trilha_id', db.Integer, db.ForeignKey('trilha.id'))
)

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False, name='senha')

    def __repr__(self):
        return f'<Admin {self.nome}>'

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

class Aluno(db.Model):
    __tablename__ = 'aluno'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False, name='senha')
    sala_id = db.Column(db.Integer, db.ForeignKey('sala.id', ondelete='CASCADE'), nullable=False)

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
        # CORREÇÃO: Retornar o email correto
        return {
            'id': self.id,
            'nome': self.nome,
            'email': self.email
        }
    
class Professor(db.Model):
    __tablename__ = 'professor'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False, name='senha')
    salas = db.relationship('Sala', backref='professor', lazy=True)

    def __repr__(self):
        return f'<Professor {self.nome}>'

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

class Sala(db.Model):
    __tablename__ = 'sala'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    professor_id = db.Column(db.Integer, db.ForeignKey('professor.id'), nullable=False)
    alunos = db.relationship('Aluno', backref='sala', lazy='dynamic', cascade="all, delete-orphan")
    trilhas = db.relationship('Trilha', secondary=sala_trilha_association, back_populates='salas', lazy='dynamic')
      
    def to_dict(self):
        sala_dict = {
            "id": self.id,
            "nome": self.nome,
            "professor_id": self.professor_id,
            "alunos": [aluno.to_dict() for aluno in self.alunos]
        }
        sala_dict["trilhas"] = [trilha.to_dict() for trilha in self.trilhas]
        return sala_dict

class Trilha(db.Model):
    __tablename__ = 'trilha'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.Text)
    salas = db.relationship('Sala', secondary=sala_trilha_association, back_populates='trilhas', lazy='dynamic')
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
    __tablename__ = 'jogo'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.Text)
    trilha_id = db.Column(db.Integer, db.ForeignKey('trilha.id'), nullable=False)
    
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
    __tablename__ = 'desempenho_jogo'
    id = db.Column(db.Integer, primary_key=True)
    
    aluno_id = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)
    jogo_id = db.Column(db.Integer, db.ForeignKey('jogo.id'), nullable=False)
    trilha_id = db.Column(db.Integer, db.ForeignKey('trilha.id'), nullable=False)
    sala_id = db.Column(db.Integer, db.ForeignKey('sala.id'), nullable=False)
    
    data_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    passou = db.Column(db.Boolean, nullable=False)
    acertos = db.Column(db.JSON, nullable=True)
    erros = db.Column(db.JSON, nullable=True)
    
    def __repr__(self):
        return f'<DesempenhoJogo Aluno: {self.aluno_id}, Jogo: {self.jogo_id}, Trilha: {self.trilha_id}, Passou: {self.passou}>'

    def to_dict(self):
        return {
            'id': self.id,
            'aluno_id': self.aluno_id,
            'sala_id': self.sala_id,
            'jogo_id': self.jogo_id,
            'trilha_id': self.trilha_id,
            'data_hora': self.data_hora.isoformat() if self.data_hora else None,
            'passou': self.passou,
            'acertos': self.acertos,
            'erros': self.erros
        }