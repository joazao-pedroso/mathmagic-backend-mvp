from dotenv import load_dotenv
load_dotenv() 

from flask import Flask, request, jsonify, session
from config import Config
from models import db, Aluno, Trilha, Jogo, DesempenhoJogo, Professor, Sala, Admin
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, create_refresh_token, JWTManager, get_jwt
from datetime import timedelta
from flask_migrate import Migrate
from flask_cors import CORS

import google.generativeai as genai
import os

genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

app.config['SECRET_KEY'] = 'grupofunction'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
jwt = JWTManager(app)

import json

db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

# ===========================ROTAS DO ADM====================================

# ROTA DE REGISTRO DO ADM QUE RETORNA COM A SENHA HASH - TESTADA E FUNCIONANDO
@app.route('/api/register_admin', methods=['POST'])
def register_admin():
    data = request.get_json()
    nome = data.get('nome')
    email = data.get('email')
    senha = data.get('senha')

    if not nome or not email or not senha:
        return jsonify({"message": "Nome, email e senha são obrigatórios para o cadastro."}), 400

    if Admin.query.filter_by(email=email).first():
        return jsonify({"message": "Email já cadastrado."}), 409
    
    try:
        novo_admin = Admin(nome=nome, email=email)
        novo_admin.senha = senha

        db.session.add(novo_admin)
        db.session.commit()

        return jsonify({"message": "Administrador cadastrado com sucesso!"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao registrar: {str(e)}"}), 500

# ROTA DE LOGIN DO ADM - TESTADA E FUNCIONANDO
@app.route('/api/login_admin', methods=['POST'])
def login_admin():

    data = request.get_json()
    email = data.get('email')
    senha = data.get('senha')

    if not email or not senha:
        return jsonify({"message": "Email e senha são obrigatórios para o login."}), 400

    admin = Admin.query.filter_by(email=email).first()

    if not admin or not admin.verificar_senha(senha):
        return jsonify({"message": "Email ou senha incorretos."}), 401

    additional_claims = {"is_admin": True}

    access_token = create_access_token(identity=str(admin.id), additional_claims=additional_claims)

    return jsonify(access_token=access_token), 200
#-------------------CRUD COM AS TRILHAS---------------------

# ROTA PARA VER AS TRILHAS - TESTADA E FUNCIONANDO
@app.route('/api/trilhas', methods=['GET'])
@jwt_required()
def get_trilhas():
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403

    trilhas = Trilha.query.all()

    if not trilhas:
        return jsonify({"message": "Nenhuma trilha encontrada."}), 404

    return jsonify([t.to_dict() for t in trilhas]), 200

# ROTA DE CRIAR TRILHA - TESTADA E FUNCIONANDO
@app.route('/api/trilhas', methods=['POST'])
@jwt_required()
def create_trilha():
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403

    data = request.get_json()
    nome = data.get('nome')
    descricao = data.get('descricao')

    if not nome:
        return jsonify({"message": "O nome da trilha é obrigatório."}), 400
    
    trilha_existente = Trilha.query.filter_by(nome=nome).first()
    if trilha_existente:
        return jsonify({"message": "Uma trilha com este nome já existe."}), 409
    
    try:
        nova_trilha = Trilha(nome=nome, descricao=descricao)
        db.session.add(nova_trilha)
        db.session.commit()
        return jsonify({"message": "Trilha criada com sucesso!", "trilha": nova_trilha.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao criar trilha: {str(e)}"}), 500

# ROTA DE EDITAR TRILHA - TESTADA E FUNCIONANDO
@app.route('/api/trilhas/<int:trilha_id>', methods=['PUT'])
@jwt_required()
def update_trilha(trilha_id):
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403

    trilha = Trilha.query.get(trilha_id)
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404

    data = request.get_json()
    
    if not data:
        return jsonify({"message": "Nenhum dado fornecido para atualização."}), 400

    if 'nome' in data and data['nome'] != trilha.nome:
        trilha_existente = Trilha.query.filter_by(nome=data['nome']).first()
        if trilha_existente:
            return jsonify({"message": "Uma trilha com este nome já existe."}), 409
    
    if 'nome' in data:
        trilha.nome = data['nome']
    if 'descricao' in data:
        trilha.descricao = data['descricao']

    try:
        db.session.commit()
        return jsonify({"message": "Trilha atualizada com sucesso!", "trilha": trilha.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao atualizar trilha: {str(e)}"}), 500

# ROTA DE DELETAR TRILHA - TESTADA E FUNCIONANDO
@app.route('/api/trilhas/<int:trilha_id>', methods=['DELETE'])
@jwt_required()
def delete_trilha(trilha_id):
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403
    
    trilha = Trilha.query.get(trilha_id)
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404
        
    try:
        db.session.delete(trilha)
        db.session.commit()
        return jsonify({"message": "Trilha deletada com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao deletar trilha: {str(e)}"}), 500

# --------------------ROTAS DE CRUD DE JOGOS-------------------

# ROTA DE VER OS JOGOS - TESTADA E FUNCIONANDO
@app.route('/api/jogos', methods=['GET'])
@jwt_required()
def get_jogos():
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403
    
    jogos = Jogo.query.all()
    
    if not jogos:
        return jsonify({"message": "Nenhum jogo encontrado."}), 404

    jogos_list = []
    for jogo in jogos:
        jogo_dict = jogo.to_dict()
        if jogo.trilha:
            jogo_dict['trilha_nome'] = jogo.trilha.nome
        jogos_list.append(jogo_dict)
        
    return jsonify(jogos_list), 200

# ROTA PARA CRIAR UM NOVO JOGO - TESTADA E FUNCIONANDO
@app.route('/api/jogos', methods=['POST'])
@jwt_required()
def create_jogo():
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403
        
    data = request.get_json()
    nome = data.get('nome')
    descricao = data.get('descricao')
    trilha_id = data.get('trilha_id')

    if not all([nome, trilha_id]):
        return jsonify({"message": "Nome do jogo e ID da trilha são obrigatórios."}), 400

    # Adicionando a validação para nome de jogo duplicado
    jogo_existente = Jogo.query.filter_by(nome=nome).first()
    if jogo_existente:
        return jsonify({"message": "Um jogo com este nome já existe."}), 409
        
    trilha = Trilha.query.get(trilha_id)
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404

    try:
        novo_jogo = Jogo(nome=nome, descricao=descricao, trilha=trilha)
        db.session.add(novo_jogo)
        db.session.commit()
        
        jogo_dict = novo_jogo.to_dict()
        jogo_dict['trilha_nome'] = trilha.nome
        return jsonify({"message": "Jogo criado com sucesso!", "jogo": jogo_dict}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao criar jogo: {str(e)}"}), 500

# ROTA PARA EDITAR UM JOGO - TESTADA E FUNCIONANDO
@app.route('/api/jogos/<int:jogo_id>', methods=['PUT'])
@jwt_required()
def update_jogo(jogo_id):
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403
    
    jogo = Jogo.query.get(jogo_id)
    if not jogo:
        return jsonify({"message": "Jogo não encontrado."}), 404

    data = request.get_json()
    
    if not data:
        return jsonify({"message": "Nenhum dado fornecido para atualização."}), 400

    if 'nome' in data and data['nome'] != jogo.nome:
        jogo_existente = Jogo.query.filter_by(nome=data['nome']).first()
        if jogo_existente:
            return jsonify({"message": "Um jogo com este nome já existe."}), 409

    if 'nome' in data:
        jogo.nome = data['nome']
    if 'descricao' in data:
        jogo.descricao = data['descricao']
    if 'trilha_id' in data:
        trilha_id = data['trilha_id']
        trilha = Trilha.query.get(trilha_id)
        if not trilha:
            return jsonify({"message": "Trilha não encontrada."}), 404
        jogo.trilha = trilha

    try:
        db.session.commit()
        
        jogo_dict = jogo.to_dict()
        jogo_dict['trilha_nome'] = jogo.trilha.nome if jogo.trilha else None
        return jsonify({"message": "Jogo atualizado com sucesso!", "jogo": jogo_dict}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao atualizar jogo: {str(e)}"}), 500

# ROTA DE DELETAR UM JOGO - TESTADA E FUNCIONANDO
@app.route('/api/jogos/<int:jogo_id>', methods=['DELETE'])
@jwt_required()
def delete_jogo(jogo_id):
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403
    
    jogo = Jogo.query.get(jogo_id)
    
    if not jogo:
        return jsonify({"message": "Jogo não encontrado."}), 404
        
    try:
        db.session.delete(jogo)
        db.session.commit()
        
        return jsonify({"message": "Jogo deletado com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao deletar jogo: {str(e)}"}), 500

# ------------------ROTAS DE CRUD DE PROFESSORES----------------

# ROTA DE VER PROFESSORES - TESTADA E FUNCIONANDO
@app.route('/api/professores', methods=['GET'])
@jwt_required()
def get_professores():
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403

    professores = Professor.query.all()
    
    if not professores:
        return jsonify({"message": "Nenhum professor encontrado."}), 404

    return jsonify([p.to_dict() for p in professores]), 200

# ROTA DE CRIAR UM NOVO PROFESSOR - TESTADA E FUNCIONANDO
@app.route('/api/professores', methods=['POST'])
@jwt_required()
def create_professor():
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403

    data = request.get_json()
    nome = data.get('nome')
    email = data.get('email')
    senha = data.get('senha')

    if not all([nome, email, senha]):
        return jsonify({"message": "Nome, email e senha são obrigatórios."}), 400

    if Professor.query.filter_by(email=email).first():
        return jsonify({"message": "Email já cadastrado."}), 409

    try:
        novo_professor = Professor(nome=nome, email=email)
        novo_professor.senha = senha # O setter do modelo faz o hash
        db.session.add(novo_professor)
        db.session.commit()
        return jsonify({"message": "Professor criado com sucesso!", "professor": novo_professor.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao criar professor: {str(e)}"}), 500

# ROTA DE EDITAR UM PROFESSOR - TESTADA E FUNCIONANDO
@app.route('/api/professores/<int:professor_id>', methods=['PUT'])
@jwt_required()
def update_professor(professor_id):
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403

    professor = Professor.query.get(professor_id)
    if not professor:
        return jsonify({"message": "Professor não encontrado."}), 404

    data = request.get_json()

    if not data:
        return jsonify({"message": "Nenhum dado fornecido para atualização."}), 400
    
    if 'nome' in data:
        professor.nome = data['nome']
    
    if 'email' in data:
        novo_email = data['email']
        if Professor.query.filter(Professor.email == novo_email, Professor.id != professor_id).first():
            return jsonify({"message": "O novo email já está em uso por outro professor."}), 409
        professor.email = novo_email

    if 'senha' in data:
        professor.senha = data['senha']
    
    try:
        db.session.commit()
        return jsonify({"message": "Professor atualizado com sucesso!", "professor": professor.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao atualizar professor: {str(e)}"}), 500

# ROTA DE DELETAR UM PROFESSOR - TESTADA E FUNCIONANDO
@app.route('/api/professores/<int:professor_id>', methods=['DELETE'])
@jwt_required()
def delete_professor(professor_id):
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({"message": "Acesso negado: Apenas administradores podem acessar esta rota."}), 403

    professor = Professor.query.get(professor_id)
    if not professor:
        return jsonify({"message": "Professor não encontrado."}), 404
        
    try:
        db.session.delete(professor)
        db.session.commit()
        return jsonify({"message": "Professor deletado com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao deletar professor: {str(e)}"}), 500
# ===========================================FIM DAS ROTAS DO ADM==================================================

#============================================ROTAS DO PROFESSOR====================================================
# ROTA DE LOGIN DO PROFESSOR - TESTADA E FUNCIONANDO
@app.route('/api/login_professor', methods=['POST'])
def login_professor():
    email = request.json.get('email', None)
    senha = request.json.get('senha', None)
    
    if not email or not senha:
        return jsonify({"message": "Email e senha são obrigatórios para o login."}), 400

    professor = Professor.query.filter_by(email=email).first()

    if not professor or not professor.verificar_senha(senha): 
        return jsonify({"message": "Email ou senha incorretos."}), 401 
    
    additional_claims = {"is_professor": True}

    access_token = create_access_token(identity=str(professor.id), additional_claims=additional_claims)
    return jsonify(access_token=access_token), 200

# -------------------------CRUD COM AS SALAS--------------------------------

# ROTA PARA VER AS SALAS - AINDA NÃO TESTADA
@app.route('/api/salas', methods=['GET'])
@jwt_required()
def get_sala():
    claims = get_jwt()
    if not claims.get('is_professor'):
        return jsonify({"message": "Acesso negado: Apenas professores podem acessar esta rota."}), 403

    professor_id = get_jwt_identity()

    salas = Sala.query.filter_by(professor_id=professor_id).all()
    
    if not salas:
        return jsonify({"message": "Nenhuma sala encontrada para este professor."}), 404

    salas_com_alunos = []
    for sala in salas:
        sala_dict = sala.to_dict()
        # Carrega os alunos da sala
        sala_dict['alunos'] = [aluno.to_dict() for aluno in sala.alunos]
        salas_com_alunos.append(sala_dict)
    
    return jsonify(salas_com_alunos), 200

# ROTA PARA CRIAR SALAS - AINDA NÃO TESTADA - VALIDAR PARA TER NO MÍNIMO 1 TRILHA
@app.route('/api/salas', methods=['POST'])
@jwt_required()
def create_sala():
    claims = get_jwt()
    if not claims.get('is_professor'):
        return jsonify({"message": "Acesso negado: Apenas professores podem acessar esta rota."}), 403
        
    professor_id = get_jwt_identity()
    data = request.get_json()
    nome_sala = data.get('nome')
    trilhas_ids = data.get('trilhas_ids', []) 

    if not nome_sala:
        return jsonify({"message": "O nome da sala é obrigatório."}), 400
    
    if not trilhas_ids:
        return jsonify({"message": "Selecione pelo menos uma trilha para a sala."}), 400

    sala_existente = Sala.query.filter_by(nome=nome_sala, professor_id=professor_id).first()
    if sala_existente:
        return jsonify({"message": "Você já tem uma sala com este nome."}), 409

    try:
        trilhas = Trilha.query.filter(Trilha.id.in_(trilhas_ids)).all()

        if len(trilhas) != len(trilhas_ids):
            return jsonify({"message": "Um ou mais IDs de trilha são inválidos."}), 400

        nova_sala = Sala(nome=nome_sala, professor_id=professor_id)
        db.session.add(nova_sala)
        db.session.commit()
        
        return jsonify({"message": "Sala criada com sucesso!", "sala": nova_sala.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao criar sala: {str(e)}"}), 500

# ROTA PARA EDITAR UMA SALA - AINDA NÃO TESTADA
@app.route('/api/salas/<int:sala_id>', methods=['PUT'])
@jwt_required()
def update_sala(sala_id):
    claims = get_jwt()
    if not claims.get('is_professor'):
        return jsonify({"message": "Acesso negado: Apenas professores podem acessar esta rota."}), 403

    professor_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return jsonify({"message": "Nenhum dado fornecido para atualização."}), 400

    novo_nome = data.get('nome')

    if not novo_nome:
        return jsonify({"message": "O nome da sala é obrigatório."}), 400
    
    sala_existente = Sala.query.filter_by(nome=novo_nome, professor_id=professor_id).first()
    if sala_existente and sala_existente.id != sala_id:
        return jsonify({"message": "Você já tem uma sala com este nome."}), 409

    sala = Sala.query.filter_by(id=sala_id, professor_id=professor_id).first()

    if not sala:
        return jsonify({"message": "Sala não encontrada ou você não tem permissão para editá-la."}), 404

    try:
        sala.nome = novo_nome
        db.session.commit()
        return jsonify({"message": "Sala atualizada com sucesso!", "sala": sala.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao atualizar sala: {str(e)}"}), 500

# ROTA PARA DELETAR UMA SALA - AINDA NÃO TESTADA - PRECISA DELETAR ALUNOS CONECTADOS
@app.route('/api/salas/<int:sala_id>', methods=['DELETE'])
@jwt_required()
def delete_sala(sala_id):
    claims = get_jwt()
    if not claims.get('is_professor'):
        return jsonify({"message": "Acesso negado: Apenas professores podem acessar esta rota."}), 403

    professor_id = get_jwt_identity()

    sala = Sala.query.filter_by(id=sala_id, professor_id=professor_id).first()

    if not sala:
        return jsonify({"message": "Sala não encontrada ou você não tem permissão para deletá-la."}), 404
        
    try:
        db.session.delete(sala)
        db.session.commit()
        return jsonify({"message": "Sala deletada com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao deletar sala: {str(e)}"}), 500

# ----------------ROTAS DE GERENCIAMENTO COM OS ALUNOS----------------

# ROTA PARA VER OS ALUNOS DA SALA - AINDA NÃO TESTADA
@app.route('/api/salas/<int:sala_id>/alunos', methods=['GET'])
def get_alunos_da_sala(sala_id):
    professor_id = get_jwt_identity()

    # 1. Verifica se a sala existe E se ela pertence ao professor logado
    sala = Sala.query.filter_by(id=sala_id, professor_id=professor_id).first()
    if not sala:
        return jsonify({"message": "Sala não encontrada ou você não tem permissão para acessá-la."}), 404

    # 2. Obtém a lista de alunos associados a esta sala
    # A relação M-N é acessada diretamente via sala.alunos
    alunos = sala.alunos

    # 3. Formata a lista de alunos para o JSON
    alunos_list = [aluno.to_dict() for aluno in alunos]

    return jsonify(alunos_list), 200

# ROTA PARA CRIAR UM ALUNO - AINDA NÃO TESTADA
@app.route('/api/salas/<int:sala_id>/alunos', methods=['POST'])
def create_aluno_na_sala(sala_id):
    professor_id = get_jwt_identity()
    data = request.get_json()

    nome = data.get('nome')
    email = data.get('email')
    senha = data.get('senha')

    # Validação inicial dos dados
    if not all([nome, email, senha]):
        return jsonify({"message": "Nome, email e senha são obrigatórios."}), 400

    # 1. Verifica se a sala existe e se pertence ao professor logado
    sala = Sala.query.filter_by(id=sala_id, professor_id=professor_id).first()
    if not sala:
        return jsonify({"message": "Sala não encontrada ou você não tem permissão para adicionar alunos a ela."}), 404

    # 2. Verifica se o email já está em uso por outro aluno
    if Aluno.query.filter_by(email=email).first():
        return jsonify({"message": "Email já cadastrado."}), 409 # Conflict

    # 3. Cria o novo aluno e define a senha
    novo_aluno = Aluno(nome=nome, email=email)
    novo_aluno.senha = senha # O setter do modelo fará o hash

    try:
        # 4. Adiciona o aluno ao banco de dados e à sala
        db.session.add(novo_aluno)
        sala.alunos.append(novo_aluno)
        db.session.commit()
        
        return jsonify({
            "message": "Aluno criado e adicionado à sala com sucesso!",
            "aluno": novo_aluno.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao criar aluno: {str(e)}"}), 500

# ROTA PARA EDITAR ALUNO - AINDA NÃO TESTADA
@app.route('/api/salas/<int:sala_id>/alunos/<int:aluno_id>', methods=['PUT'])
def update_aluno_na_sala(sala_id, aluno_id):
    professor_id = get_jwt_identity()
    data = request.get_json()

    # 1. Verifica se a sala e o aluno existem e se o professor tem permissão
    sala = Sala.query.filter_by(id=sala_id, professor_id=professor_id).first()
    if not sala:
        return jsonify({"message": "Sala não encontrada ou você não tem permissão para editá-la."}), 404

    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # 2. Garante que o aluno pertence à sala
    # A verificação é feita através da lista de alunos da sala, carregada pelo SQLAlchemy
    if aluno not in sala.alunos:
        return jsonify({"message": "Este aluno não pertence à sala informada."}), 403 # Forbidden

    try:
        # 3. Atualiza os campos do aluno
        if 'nome' in data:
            aluno.nome = data['nome']

        if 'email' in data:
            novo_email = data['email']
            # Verifica se o novo email já existe, exceto para o próprio aluno
            if Aluno.query.filter(Aluno.email == novo_email, Aluno.id != aluno_id).first():
                return jsonify({"message": "O novo email já está em uso por outro aluno."}), 409
            aluno.email = novo_email

        if 'senha' in data:
            # O setter de senha do modelo Aluno cuidará do hash
            aluno.senha = data['senha']
        
        db.session.commit()
        
        return jsonify({"message": "Dados do aluno atualizados com sucesso!", "aluno": aluno.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao atualizar aluno: {str(e)}"}), 500

# ROTA PARA DELETAR ALUNO - AINDA NÃO TESTADA
@app.route('/api/salas/<int:sala_id>/alunos/<int:aluno_id>', methods=['DELETE'])
def delete_aluno_da_sala(sala_id, aluno_id):
    professor_id = get_jwt_identity()

    # 1. Verifica se a sala e o aluno existem e se o professor tem permissão
    sala = Sala.query.filter_by(id=sala_id, professor_id=professor_id).first()
    if not sala:
        return jsonify({"message": "Sala não encontrada ou você não tem permissão para gerenciá-la."}), 404

    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # 2. Garante que o aluno pertence à sala
    if aluno not in sala.alunos:
        return jsonify({"message": "Este aluno não pertence à sala informada."}), 403 # Forbidden

    try:
        # 3. Deleta o aluno
        db.session.delete(aluno)
        db.session.commit()
        
        return jsonify({"message": "Aluno deletado com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao deletar aluno: {str(e)}"}), 500

# ROTA PARA VER PERFIL DO ALUNO - AINDA NÃO TESTADA
@app.route('/api/alunos/<int:aluno_id>', methods=['GET'])
def get_perfil_aluno(aluno_id):
    professor_id = get_jwt_identity()

    # 1. Encontra o aluno pelo ID
    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # 2. Verifica se o aluno pertence a alguma sala do professor logado
    # Isso é crucial para garantir a autorização
    # Fazemos um loop pelas salas do professor e verificamos se o aluno está em alguma delas
    professor = Professor.query.get(professor_id)
    aluno_e_do_professor = False
    for sala in professor.salas:
        if aluno in sala.alunos:
            aluno_e_do_professor = True
            break
            
    if not aluno_e_do_professor:
        return jsonify({"message": "Você não tem permissão para acessar o perfil deste aluno."}), 403 # Forbidden

    # 3. Retorna os dados do aluno e as trilhas da sala a que ele pertence
    # Como um aluno pode estar em várias salas, vamos buscar todas as salas e suas trilhas
    salas_do_aluno = []
    for sala in aluno.salas:
        salas_do_aluno.append({
            'id': sala.id,
            'nome': sala.nome,
            'trilhas': [trilha.to_dict() for trilha in sala.trilhas]
        })

    perfil_do_aluno = aluno.to_dict()
    perfil_do_aluno['salas'] = salas_do_aluno

    return jsonify(perfil_do_aluno), 200

# ROTA PARA VER RELATÓRIO DO ALUNO POR TRILHA - AINDA NÃO TESTADA
@app.route('/api/alunos/<int:aluno_id>/historico/trilha/<int:trilha_id>', methods=['GET'])
def get_historico_aluno_por_trilha(aluno_id, trilha_id):
    professor_id = get_jwt_identity()

    # 1. Verifica se o aluno existe e se ele pertence a uma das salas do professor
    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # Busca todas as salas do professor
    professor = Professor.query.get(professor_id)
    professor_possui_aluno = False
    for sala in professor.salas:
        if aluno in sala.alunos:
            professor_possui_aluno = True
            break
    
    if not professor_possui_aluno:
        return jsonify({"message": "Você não tem permissão para acessar o histórico deste aluno."}), 403

    # 2. Verifica se a trilha existe e se ela está associada a alguma sala do aluno
    trilha = Trilha.query.get(trilha_id)
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404
        
    # Esta verificação é opcional, mas evita que um professor veja o desempenho em uma trilha que
    # não foi associada a nenhuma sala do aluno.
    aluno_tem_acesso_a_trilha = False
    for sala in aluno.salas:
        if trilha in sala.trilhas:
            aluno_tem_acesso_a_trilha = True
            break
            
    if not aluno_tem_acesso_a_trilha:
         return jsonify({"message": "Esta trilha não está disponível para este aluno através de nenhuma das suas salas."}), 403

    # 3. Busca os desempenhos do aluno na trilha
    desempenhos = DesempenhoJogo.query.filter_by(aluno_id=aluno_id, trilha_id=trilha_id)\
                                     .options(db.joinedload(DesempenhoJogo.jogo))\
                                     .order_by(DesempenhoJogo.data_hora.desc())\
                                     .all()

    historico_data = []
    for d in desempenhos:
        jogo_nome = d.jogo.nome if d.jogo else f"Jogo ID {d.jogo_id}"
        historico_data.append({
            "id": d.id,
            "jogo_id": d.jogo_id,
            "jogo_nome": jogo_nome,
            "data_hora": d.data_hora.isoformat(),
            "passou": d.passou,
            "acertos": d.acertos,
            "erros": d.erros
        })
        
    return jsonify(historico_data), 200

# ROTA PARA VER ANALISE DA IA DO DESEMPENHO DO ALUNO - AINDA NÃO TESTADA
@app.route('/api/alunos/<int:aluno_id>/historico/trilha/<int:trilha_id>/analise-ia', methods=['GET'])
def get_analise_ia(aluno_id, trilha_id):
    professor_id = get_jwt_identity()

    # 1. Validação de permissão
    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    professor = Professor.query.get(professor_id)
    if not any(aluno in sala.alunos for sala in professor.salas):
        return jsonify({"message": "Você não tem permissão para acessar o histórico deste aluno."}), 403

    trilha = Trilha.query.get(trilha_id)
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404
        
    # 2. Busca o histórico de desempenho (mesma lógica da rota anterior)
    desempenhos = DesempenhoJogo.query.filter_by(aluno_id=aluno_id, trilha_id=trilha_id)\
                                     .options(db.joinedload(DesempenhoJogo.jogo))\
                                     .order_by(DesempenhoJogo.data_hora.desc())\
                                     .all()

    if not desempenhos:
        return jsonify({"message": "Nenhum dado de desempenho encontrado para este aluno nesta trilha."}), 404

    # 3. Cria o prompt com base nos dados do histórico
    prompt = "Você é um assistente de análise de desempenho escolar. "
    "Sua tarefa é analisar os dados de um aluno e gerar um relatório detalhado e útil para o professor. "
    "A resposta deve ser um objeto JSON válido, contendo as seguintes chaves: "
    "'resumo_geral', 'habilidades', 'melhorias', 'analise_detalhada', 'progresso' (se houver dados suficientes) e 'sugestoes'. "
    "Cada chave deve conter um texto explicativo. Não inclua texto extra, apenas o JSON. "
    f"Análise de desempenho do aluno {aluno.nome} na trilha '{trilha.nome}'. "
    
    # Adiciona os dados de desempenho ao prompt
    for d in desempenhos:
        jogo_nome = d.jogo.nome if d.jogo else "Jogo Desconhecido"
        passou_texto = "passou" if d.passou else "não passou"
        acertos_str = f"Acertos: {len(d.acertos) if d.acertos else 0}"
        erros_str = f"Erros: {len(d.erros) if d.erros else 0}"
        
        prompt += f"\nNo jogo '{jogo_nome}', ele {passou_texto} com {acertos_str} e {erros_str}. "
        prompt += f"Detalhes dos erros: {d.erros if d.erros else 'Nenhum'}. "
    
    # 4. Envia o prompt para a API do Gemini
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        analise = response.text
        
        return jsonify({"analise_ia": analise}), 200
    except Exception as e:
        return jsonify({"message": f"Erro ao gerar análise da IA: {str(e)}"}), 500

# =====================================FIM DAS ROTAS DO PROFESSOR======================================

# =================================ROTAS DO ALUNO================================================

# ROTA DE LOGIN DO ALUNO - AINDA NÃO TESTADA - DEVE RENDERIZAR A TELA DA SALA NA SALA QUE ELE FOI MATRICULADO
@app.route('/api/login_aluno', methods=['POST'])
def login_aluno():
    email = request.json.get('email', None)
    senha = request.json.get('senha', None)

    aluno = Aluno.query.filter_by(email=email).first()

    if not aluno or not aluno.verificar_senha(senha): 
        return jsonify({"message": "Email ou senha incorretos."}), 401 

    access_token = create_access_token(identity=f"aluno_{aluno.id}")
    return jsonify(access_token=access_token), 200

# ROTA PARA VER AS TRILHAS DISPONIVEIS NA SALA, PELO ALUNO - AINDA NÃO TESTADA
@app.route('/api/aluno/trilhas', methods=['GET'])
def get_aluno_trilhas():
    # Obtém a identidade do aluno do token JWT
    identity = get_jwt_identity()
    if not identity.startswith('aluno_'):
        return jsonify({"message": "Acesso negado: Apenas alunos podem acessar esta rota."}), 403

    aluno_id = int(identity.split('_')[1])
    aluno = Aluno.query.get(aluno_id)

    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # Busca a primeira sala do aluno
    sala = aluno.salas.first()
    if not sala:
        return jsonify({"message": "Aluno não está associado a nenhuma sala."}), 404

    trilhas_da_sala = [t.to_dict() for t in sala.trilhas]
    
    return jsonify({
        "sala_nome": sala.nome,
        "trilhas": trilhas_da_sala
    }), 200

# ROTA PARA VER OS JOGOS DE UMA TRILHA, PELO ALUNO - AINDA NÃO TESTADA
@app.route('/api/trilhas/<int:trilha_id>/jogos', methods=['GET'])
def get_jogos_da_trilha(trilha_id):
    # Verifica se a trilha existe
    trilha = Trilha.query.get(trilha_id)
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404

    # Como a relação já foi definida no modelo, é fácil acessar os jogos
    jogos_da_trilha = [j.to_dict() for j in trilha.jogos]
    
    return jsonify({
        "trilha_nome": trilha.nome,
        "jogos": jogos_da_trilha
    }), 200

# ROTA PARA SALVAR DESEMPENHO DO ALUNO - AINDA NÃO TESTADA
@app.route('/api/desempenho', methods=['POST'])
def save_desempenho():
    # 1. Obtém a identidade do aluno logado
    identity = get_jwt_identity()
    if not identity.startswith('aluno_'):
        return jsonify({"message": "Acesso negado: Apenas alunos podem salvar o desempenho."}), 403

    aluno_id = int(identity.split('_')[1])
    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # 2. Recebe os dados do corpo da requisição
    data = request.get_json()
    jogo_id = data.get('jogo_id')
    trilha_id = data.get('trilha_id')
    passou = data.get('passou')
    acertos = data.get('acertos')
    erros = data.get('erros')

    # Validação inicial dos dados
    if not all([jogo_id, trilha_id, passou is not None, acertos is not None, erros is not None]):
        return jsonify({"message": "Dados incompletos. Jogo, trilha, resultado e acertos/erros são obrigatórios."}), 400

    # 3. Validação adicional: garante que o aluno, jogo e trilha existem
    jogo = Jogo.query.get(jogo_id)
    trilha = Trilha.query.get(trilha_id)
    if not jogo or not trilha:
        return jsonify({"message": "Jogo ou trilha não encontrados."}), 404

    # 4. Encontra a sala do aluno para associar o desempenho
    # Como um aluno pode estar em várias salas, vamos buscar a primeira
    sala_do_aluno = aluno.salas.first()
    if not sala_do_aluno:
        return jsonify({"message": "Aluno não está em nenhuma sala."}), 404

    # 5. Salva o desempenho no banco de dados
    try:
        novo_desempenho = DesempenhoJogo(
            aluno_id=aluno.id,
            jogo_id=jogo.id,
            trilha_id=trilha.id,
            sala_id=sala_do_aluno.id,
            passou=passou,
            acertos=acertos,
            erros=erros
        )
        db.session.add(novo_desempenho)
        db.session.commit()

        return jsonify({"message": "Desempenho salvo com sucesso!", "desempenho": novo_desempenho.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao salvar desempenho: {str(e)}"}), 500


    current_aluno_id = get_jwt_identity() 

    aluno = Aluno.query.get(current_aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado (via token)."}), 404

    return jsonify({"message": "Bem-vindo ao seu perfil!", "aluno": aluno.to_dict()}), 200


if __name__ == '__main__':
    app.run(debug=True) # Mude debug=False em produção