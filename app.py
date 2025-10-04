from dotenv import load_dotenv
load_dotenv() 

from flask import Flask, request, jsonify, session
from config import Config
from models import db, Aluno, Trilha, Jogo, DesempenhoJogo, Professor, Sala, Admin
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, create_refresh_token, JWTManager, get_jwt
from datetime import timedelta
from flask_migrate import Migrate
from flask_cors import CORS
from sqlalchemy.orm import joinedload
from sqlalchemy import or_

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

@app.route('/api/login', methods=['POST'])
def login():

    data = request.get_json()
    email = data.get('email')
    senha = data.get('senha')

    if not email or not senha:
        return jsonify({"message": "Email e senha são obrigatórios para o login."}), 400

    # 1. Tentar encontrar e autenticar como ADMIN (Prioridade 1)
    user = Admin.query.filter_by(email=email).first()
    if user and user.verificar_senha(senha):
        funcao = 'admin'
        # Adiciona a informação da função ao payload do token
        additional_claims = {"funcao": funcao} 
    
    # 2. Tentar encontrar e autenticar como PROFESSOR (Prioridade 2)
    else:
        user = Professor.query.filter_by(email=email).first()
        if user and user.verificar_senha(senha):
            funcao = 'professor'
            # Adiciona a informação da função ao payload do token
            additional_claims = {"funcao": funcao}
        
        # 3. Tentar encontrar e autenticar como ALUNO (Prioridade 3)
        else:
            user = Aluno.query.filter_by(email=email).first()
            if user and user.verificar_senha(senha):
                funcao = 'aluno'
                # Adiciona a informação da função ao payload do token
                additional_claims = {"funcao": funcao}
            
            # Autenticação falhou em todas as tabelas
            else:
                return jsonify({"message": "Email ou senha incorretos."}), 401

    # Autenticação bem-sucedida
    
    # Criamos o token com o ID do usuário e a função (role) em 'additional_claims'
    access_token = create_access_token(
        identity=str(user.id), 
        additional_claims=additional_claims
    )
    
    # Retorna o token e a função do usuário para o frontend saber qual fluxo seguir
    return jsonify(
        access_token=access_token,
        usuario_id=user.id,
        funcao=funcao
    ), 200

#-------------------CRUD COM AS TRILHAS---------------------

# ROTA PARA PESQUISAR TRILHAS POR NOME - TESTADA E FUNCIONANDO
@app.route('/api/admin/trilhas/search', methods=['GET'])
@jwt_required()
def search_trilhas_admin():
    claims = get_jwt()
    if claims.get('funcao') != 'admin':
        return jsonify({"message": "Acesso negado: Apenas administradores podem pesquisar trilhas."}), 403

    # Obtém o termo de pesquisa da query string (ex: /search?query=subtracao)
    search_term = request.args.get('query', None)

    if not search_term:
        # Se não houver termo, retorna todas as trilhas ou um erro
        return jsonify({"message": "O termo de pesquisa 'query' é obrigatório."}), 400

    # Adiciona o wildcard (%) para busca parcial e case-insensitive
    termo_like = f"%{search_term}%"
    
    trilhas = Trilha.query.filter(Trilha.nome.ilike(termo_like)).all()

    if not trilhas:
        return jsonify({"message": f"Nenhuma trilha encontrada com o nome: '{search_term}'"}), 404

    return jsonify([t.to_dict() for t in trilhas]), 200

# ROTA PARA VER AS TRILHAS - TESTADA E FUNCIONANDO
@app.route('/api/trilhas', methods=['GET'])
@jwt_required()
def get_trilhas():
    claims = get_jwt()
    if claims.get('funcao') != 'admin':
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
    if claims.get('funcao') != 'admin':
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
    if claims.get('funcao') != 'admin':
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
    if claims.get('funcao') != 'admin':
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

# ROTA DE PESQUISAR JOGOS POR NOME - TESTADA E FUNCIONANDO
@app.route('/api/admin/jogos/search', methods=['GET'])
@jwt_required()
def search_jogos_admin():
    claims = get_jwt()
    if claims.get('funcao') != 'admin':
        return jsonify({"message": "Acesso negado: Apenas administradores podem pesquisar jogos."}), 403

    search_term = request.args.get('query', None)

    if not search_term:
        return jsonify({"message": "O termo de pesquisa 'query' é obrigatório."}), 400

    termo_like = f"%{search_term}%"
    
    # Busca jogos pelo nome, ignorando maiúsculas/minúsculas
    jogos = Jogo.query.filter(Jogo.nome.ilike(termo_like)).all()

    if not jogos:
        return jsonify({"message": f"Nenhum jogo encontrado com o nome: '{search_term}'"}), 404

    return jsonify([j.to_dict() for j in jogos]), 200

# ROTA DE VER OS JOGOS - TESTADA E FUNCIONANDO
@app.route('/api/jogos', methods=['GET'])
@jwt_required()
def get_jogos():
    claims = get_jwt()
    if claims.get('funcao') != 'admin':
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
    if claims.get('funcao') != 'admin':
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
    if claims.get('funcao') != 'admin':
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
    if claims.get('funcao') != 'admin':
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

#ROTA DE PESQUISAR PROFESSORES POR NOME - TESTADA E FUNCIONANDO
@app.route('/api/admin/professores/search', methods=['GET'])
@jwt_required()
def search_professores_admin():
    claims = get_jwt()
    if claims.get('funcao') != 'admin':
        return jsonify({"message": "Acesso negado: Apenas administradores podem pesquisar professores."}), 403

    search_term = request.args.get('query', None)

    if not search_term:
        return jsonify({"message": "O termo de pesquisa 'query' é obrigatório."}), 400

    termo_like = f"%{search_term}%"
    
    # Usa 'or_' para buscar o termo no nome OU no email
    professores = Professor.query.filter(
        or_(
            Professor.nome.ilike(termo_like),
            Professor.email.ilike(termo_like)
        )
    ).all()

    if not professores:
        return jsonify({"message": f"Nenhum professor encontrado com o termo: '{search_term}'"}), 404

    return jsonify([p.to_dict() for p in professores]), 200

# ROTA DE VER PROFESSORES - TESTADA E FUNCIONANDO
@app.route('/api/professores', methods=['GET'])
@jwt_required()
def get_professores():
    claims = get_jwt()
    if claims.get('funcao') != 'admin':
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
    if claims.get('funcao') != 'admin':
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
    if claims.get('funcao') != 'admin':
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
    if claims.get('funcao') != 'admin':
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
# -------------------------CRUD COM AS SALAS--------------------------------

#ROTAS PARA PESQUISAR SALAS POR NOME - TESTADA E FUNCIONANDO
@app.route('/api/professor/salas/search', methods=['GET'])
@jwt_required()
def search_salas_professor():
    claims = get_jwt()
    
    # 1. VALIDAÇÃO DE FUNÇÃO
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas professores podem pesquisar salas."}), 403

    # 2. EXTRAÇÃO DO ID DO PROFESSOR LOGADO
    professor_id_str = get_jwt_identity()
    try:
        professor_id = int(professor_id_str)
    except ValueError:
        return jsonify({"message": "ID de professor no token inválido."}), 401
    
    # 3. OBTÉM O TERMO DE PESQUISA
    search_term = request.args.get('query', None)

    if not search_term:
        # Se não houver termo de pesquisa, o professor pode querer ver todas as suas salas
        # Mantenha o filtro de professor_id para segurança
        salas = Sala.query.filter_by(professor_id=professor_id).all()
        
        if not salas:
            return jsonify({"message": "Você não possui nenhuma sala cadastrada."}), 404
        
        return jsonify([s.to_dict() for s in salas]), 200

    termo_like = f"%{search_term}%"
    
    # 4. EXECUTA A BUSCA COM FILTRO DE AUTORIZAÇÃO
    
    # Busca salas cujo nome contenha o termo
    # E que pertençam ao professor logado (professor_id)
    salas = Sala.query.filter(
        Sala.professor_id == professor_id, # Filtro de Autorização: Sala pertence ao professor
        Sala.nome.ilike(termo_like)       # Filtro de Pesquisa: Nome da sala contém o termo
    ).all()

    if not salas:
        return jsonify({"message": f"Nenhuma sala encontrada com o termo: '{search_term}'"}), 404

    return jsonify([s.to_dict() for s in salas]), 200

# ROTA PARA VER AS SALAS - TESTADA E FUNCIONANDO
@app.route('/api/salas', methods=['GET'])
@jwt_required()
def get_sala():
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403

    professor_id = get_jwt_identity()

    salas = Sala.query.filter_by(professor_id=professor_id).all()
    
    if not salas:
        return jsonify({"message": "Nenhuma sala encontrada para este professor."}), 404

    salas_com_alunos = []
    for sala in salas:
        sala_dict = sala.to_dict()
        sala_dict['alunos'] = [aluno.to_dict() for aluno in sala.alunos]
        salas_com_alunos.append(sala_dict)
    
    return jsonify(salas_com_alunos), 200

# ROTA PARA CRIAR SALAS - TESTADA E FUNCIONANDO
@app.route('/api/salas', methods=['POST'])
@jwt_required()
def create_sala():
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403
        
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

        for trilha in trilhas:
            nova_sala.trilhas.append(trilha)

        db.session.add(nova_sala)
        db.session.commit()
        
        return jsonify({
            "message": "Sala criada com sucesso!", 
            "sala": nova_sala.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao criar sala: {str(e)}"}), 500

# ROTA PARA EDITAR UMA SALA - TESTADA E FUNCIONANDO
@app.route('/api/salas/<int:sala_id>', methods=['PUT'])
@jwt_required()
def update_sala(sala_id):
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403

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

# ROTA PARA DELETAR UMA SALA - TESTADA E FUNCIONANDO - PRECISA DELETAR ALUNOS CONECTADOS
@app.route('/api/salas/<int:sala_id>', methods=['DELETE'])
@jwt_required()
def delete_sala(sala_id):
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403

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

#ROTA PARA PESQUISAR ALUNOS POR NOME - TESTADA E FUNCIONANDO
@app.route('/api/professor/alunos/search', methods=['GET'])
@jwt_required()
def search_alunos_professor():
    claims = get_jwt()
    
    # 1. VALIDAÇÃO DE FUNÇÃO
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas professores podem pesquisar alunos."}), 403

    # 2. EXTRAÇÃO DO ID DO PROFESSOR LOGADO
    professor_id_str = get_jwt_identity()
    try:
        professor_id = int(professor_id_str)
    except ValueError:
        return jsonify({"message": "ID de professor no token inválido."}), 401
    
    # 3. OBTÉM O TERMO DE PESQUISA
    search_term = request.args.get('query', None)

    if not search_term:
        return jsonify({"message": "O termo de pesquisa 'query' é obrigatório."}), 400

    termo_like = f"%{search_term}%"
    
    # 4. ENCONTRA O PROFESSOR E SUAS SALAS
    professor = Professor.query.get(professor_id)
    if not professor:
        return jsonify({"message": "Professor não encontrado."}), 404
    
    # 5. EXECUTA A BUSCA COM FILTRO DE AUTORIZAÇÃO
    
    # Primeiro, identificamos os IDs de todas as salas pertencentes a este professor
    # Assumindo que 'professor.salas' é uma relação que lista as salas dele.
    sala_ids = [sala.id for sala in professor.salas]
    
    if not sala_ids:
        return jsonify({"message": "Você não possui salas cadastradas para realizar a pesquisa."}), 404

    # Busca alunos cujo nome OU email contenha o termo
    # E que estejam em QUALQUER uma das salas do professor (sala_id IN [IDs])
    alunos = Aluno.query.filter(
        Aluno.sala_id.in_(sala_ids), # Filtro de Autorização: Aluno pertence a uma sala do professor
        or_(
            Aluno.nome.ilike(termo_like),
            Aluno.email.ilike(termo_like)
        )
    ).all()

    if not alunos:
        return jsonify({"message": f"Nenhum aluno encontrado nas suas salas com o termo: '{search_term}'"}), 404

    return jsonify([a.to_dict() for a in alunos]), 200

# ROTA PARA VER OS ALUNOS DA SALA - TESTADA E FUNCIONANDO
@app.route('/api/salas/<int:sala_id>/alunos', methods=['GET'])
@jwt_required()
def get_alunos_da_sala(sala_id):
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403

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

# ROTA PARA CRIAR UM ALUNO - TESTADA E FUNCIONANDO
@app.route('/api/salas/<int:sala_id>/alunos', methods=['POST'])
@jwt_required()
def create_aluno_na_sala(sala_id):
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas professores podem acessar esta rota."}), 403
    professor_id_str = get_jwt_identity()

    try:
        professor_id = int(professor_id_str)
    except ValueError:
        # Isso pode acontecer se o token for manipulado ou não contiver um ID válido.
        return jsonify({"message": "ID de usuário no token inválido."}), 401
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
    novo_aluno = Aluno(nome=nome, email=email, sala_id=sala_id)
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

# ROTA PARA EDITAR ALUNO - TESTADA E FUNCIONANDO
@app.route('/api/salas/<int:sala_id>/alunos/<int:aluno_id>', methods=['PUT'])
@jwt_required()
def update_aluno_na_sala(sala_id, aluno_id):
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403
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

# ROTA PARA DELETAR ALUNO - TESTADA E FUNCIONANDO
@app.route('/api/salas/<int:sala_id>/alunos/<int:aluno_id>', methods=['DELETE'])
@jwt_required()
def delete_aluno_da_sala(sala_id, aluno_id):
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403
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

# ROTA PARA VER PERFIL DO ALUNO - TESTADA E FUNCIONANDO
@app.route('/api/alunos/<int:aluno_id>', methods=['GET'])
@jwt_required()
def get_perfil_aluno(aluno_id):
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403
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

    if aluno.sala:
        sala = aluno.sala
        salas_do_aluno.append({
            'id': sala.id,
            'nome': sala.nome,
            # Você está assumindo que 'sala' tem uma propriedade 'trilhas'
            'trilhas': [trilha.to_dict() for trilha in sala.trilhas] 
    })

    perfil_do_aluno = aluno.to_dict()
    perfil_do_aluno['salas'] = salas_do_aluno

    return jsonify(perfil_do_aluno), 200

# ROTA PARA VER RELATÓRIO DO ALUNO POR TRILHA - TESTADA E FUNCIONANDO
@app.route('/api/alunos/<int:aluno_id>/historico/trilha/<int:trilha_id>', methods=['GET'])
@jwt_required()
def get_historico_aluno_por_trilha(aluno_id, trilha_id):
    claims = get_jwt()
    
    # 1. VERIFICAÇÃO DE FUNÇÃO E ID DO PROFESSOR
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403
    
    professor_id_str = get_jwt_identity()
    try:
        professor_id = int(professor_id_str)
    except ValueError:
        return jsonify({"message": "ID de professor no token inválido."}), 401

    # 2. VERIFICAÇÃO DE AUTORIZAÇÃO: O professor pode ver este aluno?
    aluno = Aluno.query.get(aluno_id)
    professor = Professor.query.get(professor_id)
    
    if not aluno or not professor:
        return jsonify({"message": "Aluno ou Professor não encontrado."}), 404

    # Busca todas as salas do professor e verifica se o aluno está em alguma delas
    professor_possui_aluno = False
    aluno_sala = aluno.sala

    if aluno_sala:
        # Verifica se o ID do professor logado é o mesmo ID do professor dono da sala do aluno
        if aluno_sala.professor_id == professor.id:
            professor_possui_aluno = True
    
    if not professor_possui_aluno:
        return jsonify({"message": "Você não tem permissão para acessar o histórico deste aluno."}), 403

    # 3. VERIFICAÇÃO DE TRILHA
    trilha = Trilha.query.get(trilha_id)
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404
    
    if aluno_sala and trilha not in aluno_sala.trilhas:
        return jsonify({"message": "Esta trilha não está disponível para este aluno através de nenhuma das suas salas."}), 403

    # CORREÇÃO CRÍTICA: Se Aluno tem relação 1:N com Sala (aluno.sala), a lógica de trilha deve mudar.
    # Assumiremos que o professor só está interessado no desempenho que está na sala dele.
    
    # 4. BUSCA E CONSOLIDAÇÃO DOS DESEMPENHOS
    desempenhos = DesempenhoJogo.query.filter_by(aluno_id=aluno_id, trilha_id=trilha_id)\
                                     .options(joinedload(DesempenhoJogo.jogo))\
                                     .order_by(DesempenhoJogo.data_hora.desc())\
                                     .all()
    
    # Se não houver desempenho, retorne uma resposta vazia, mas válida
    if not desempenhos:
        return jsonify({
            "aluno_nome": aluno.nome,
            "trilha_nome": trilha.nome,
            "estatisticas": {
                "tentativas_totais": 0,
                "passou_trilha": False,
                "acertos_consolidados": [],
                "erros_consolidados": []
            }
        }), 200

    # Lógica de Consolidação para o Relatório:
    tentativas_totais = len(desempenhos)
    
    # Para saber se o aluno 'passou na trilha', contamos quantos jogos ele passou:
    # 1. Agrupamos os desempenhos pelo ID do Jogo (considerando a tentativa mais recente para cada jogo, se for 1 tentativa/jogo)
    #    OU simplesmente contamos os registros 'passou=True' e comparamos com o número total de jogos na trilha.
    
    # Vamos contar os registros distintos de jogos que ele passou (passou=True):
    jogos_passados = set()
    for d in desempenhos:
        if d.passou:
            jogos_passados.add(d.jogo_id)
            
    # Para verificar se "passou_trilha", precisamos do número total de jogos na trilha.
    # ASSUMIMOS que o número de jogos passados (len(jogos_passados)) deve ser 4 para passar, conforme sua regra.
    
    # Se a trilha tem 4 jogos, a regra de 'passou_trilha' é:
    total_jogos_na_trilha = len(trilha.jogos) # Pega do modelo Trilha (relação 'jogos')
    passou_trilha = len(jogos_passados) >= total_jogos_na_trilha # TRUE se ele passou em todos os jogos

    # Consolidação de Acertos e Erros (Juntando todas as listas de JSON)
    acertos_consolidados = []
    erros_consolidados = []
    
    for d in desempenhos:
        # d.acertos e d.erros são listas (JSON do banco)
        if isinstance(d.acertos, list):
            acertos_consolidados.extend(d.acertos)
        if isinstance(d.erros, list):
            erros_consolidados.extend(d.erros)

    # 5. RETORNA O RELATÓRIO CONSOLIDADO
    return jsonify({
        "aluno_nome": aluno.nome,
        "trilha_nome": trilha.nome,
        "estatisticas": {
            "tentativas_totais": tentativas_totais,
            "passou_trilha": passou_trilha,
            "acertos_consolidados": acertos_consolidados,
            "erros_consolidados": erros_consolidados
        },
        # Mantemos os dados brutos para que o frontend possa criar gráficos
        "detalhes_desempenho_bruto": [d.to_dict() for d in desempenhos]
    }), 200

# ROTA PARA VER ANALISE DA IA DO DESEMPENHO DO ALUNO - TESTADA E FUNCIONANDO
@app.route('/api/alunos/<int:aluno_id>/historico/trilha/<int:trilha_id>/analise-ia', methods=['GET'])
@jwt_required()
def get_analise_ia(aluno_id, trilha_id):
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403
    professor_id = get_jwt_identity()

    # 1. Validação de permissão (Mantenha a correção do acesso a aluno.sala aqui)
    aluno = Aluno.query.get(aluno_id)
    professor = Professor.query.get(professor_id)
    # AQUI DEVE ESTAR SUA LÓGICA CORRETA DE AUTORIZAÇÃO (usando aluno.sala.professor_id)
    # ...
    
    trilha = Trilha.query.get(trilha_id)
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404
        
    # 2. Busca o histórico de desempenho (Otimizada para carregar jogos)
    desempenhos = DesempenhoJogo.query.filter_by(aluno_id=aluno_id, trilha_id=trilha_id)\
                                     .options(db.joinedload(DesempenhoJogo.jogo))\
                                     .order_by(DesempenhoJogo.data_hora.desc())\
                                     .all()

    if not desempenhos:
        return jsonify({"message": "Nenhum dado de desempenho encontrado para este aluno nesta trilha."}), 404

    # 3. Cria o prompt com base nos dados do histórico (NOVO PROMPT OTIMIZADO)
    
    # 3.1. INSTRUÇÃO IMPOSTIVIA DE JSON E DEFINIÇÃO DE CHAVES
    prompt_instrucao = (
        "Você é um assistente de análise de desempenho escolar com foco pedagógico e **DEVE** retornar APENAS UM objeto JSON. "
        "Não inclua markdown (como ```json```), explicações ou qualquer texto fora do JSON. "
        "O JSON deve ter as seguintes 4 chaves (keys) OBRIGATÓRIAS, cada uma contendo um parágrafo de texto bem estruturado: "
        "'resumo_geral', 'pontos_fortes_analise', 'erros_comuns_analise', 'sugestoes_pedagogicas'. "
        
        # INSTRUÇÕES ESPECÍFICAS PARA MELHORAR A QUALIDADE
        "REQUISITOS DE ANÁLISE: "
        "1. **'resumo_geral':** Comece com o nível de proficiência atual do aluno na trilha. Este campo substitui a chave 'nivel_proficiencia'. Seja claro sobre o estado geral de aprendizado. "
        "2. **'pontos_fortes_analise':** Identifique os *padrões de sucesso* e as *habilidades consolidadas* (e.g., raciocínio lógico, domínio de números específicos, agilidade) por trás dos acertos. Não liste apenas as operações acertadas. "
        "3. **'erros_comuns_analise':** Identifique os *padrões de dificuldade* (e.g., erro de transposição, confusão de sinais, dificuldade com o conceito de dezena/centena) por trás dos erros. Seja detalhado e específico. "
        "4. **'sugestoes_pedagogicas':** Sugira *ideias práticas e de recursos* para o reforço. Não apenas diga 'estude divisão'; dê exemplos de atividades (e.g., uso de material dourado, jogos de cartas, problemas de contexto real)."
        
        f"\n\n--- DADOS DO ALUNO E TRILHA ---\n"
        f"Aluno: {aluno.nome}. Trilha: '{trilha.nome}'.\n"
        f"\n--- DESEMPENHO BRUTO (JSON) ---\n"
    )

    # 3.2. Adiciona os dados brutos consolidados
    dados_desempenho_consolidado = []
    
    for d in desempenhos:
        jogo_nome = d.jogo.nome if d.jogo else "Jogo Desconhecido"
        passou_texto = "PASSOU" if d.passou else "NÃO PASSOU"
        
        erros_detalhes = ', '.join(d.erros) if d.erros and isinstance(d.erros, list) else 'Nenhum erro registrado.'
        acertos_detalhes = ', '.join(d.acertos) if d.acertos and isinstance(d.acertos, list) else 'Nenhum acerto detalhado.'

        dados_desempenho_consolidado.append({
            "jogo_nome": jogo_nome,
            "resultado": passou_texto,
            "total_acertos": len(d.acertos) if d.acertos and isinstance(d.acertos, list) else 0,
            "total_erros": len(d.erros) if d.erros and isinstance(d.erros, list) else 0,
            "erros_detalhes": erros_detalhes,
            "acertos_detalhes": acertos_detalhes
        })
    
    # Adiciona o JSON dos dados brutos ao prompt
    prompt = prompt_instrucao + jsonify(dados_desempenho_consolidado).get_data(as_text=True)

    # 4. Envia o prompt para a API do Gemini
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        # Mantemos a temperatura para análise criativa
        response = model.generate_content(prompt, generation_config={"temperature": 0.7}) 
        analise = response.text
        
        import json
        
        # Tenta carregar a string JSON que veio da IA
        analise_json_objeto = json.loads(analise)
        
        # Retorna o JSON como um objeto nativo
        return jsonify(analise_json_objeto), 200 
        
    except json.JSONDecodeError:
        # Se a IA quebrar a formatação JSON, avise o professor
        return jsonify({"message": "Erro de formatação na análise da IA. Retornando texto bruto.", "analise_bruta": analise}), 500
        
    except Exception as e:
        return jsonify({"message": f"Erro ao gerar análise da IA: {str(e)}"}), 500

# =====================================FIM DAS ROTAS DO PROFESSOR======================================

# =================================ROTAS DO ALUNO================================================

# ROTA PARA PESQUISAR AS TRILHAS POR NOME - TESTADA E FUNCIONANDO
@app.route('/api/aluno/trilhas/search', methods=['GET'])
@jwt_required()
def search_trilhas_aluno():
    claims = get_jwt()
    
    # 1. VALIDAÇÃO DE FUNÇÃO
    if claims.get('funcao') != 'aluno':
        return jsonify({"message": "Acesso negado: Apenas alunos podem pesquisar trilhas."}), 403

    # 2. EXTRAÇÃO DO ID DO ALUNO LOGADO E OBTER OBJETO
    identity = get_jwt_identity()
    try:
        aluno_id = int(identity)
    except ValueError:
        return jsonify({"message": "ID de aluno no token inválido."}), 401
    
    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404
    
    # Obtém a sala do aluno (relação singular)
    sala_do_aluno = aluno.sala
    
    if not sala_do_aluno:
        return jsonify({"message": "Você não está associado a nenhuma sala com trilhas."}), 404

    # 3. OBTÉM O TERMO DE PESQUISA
    search_term = request.args.get('query', None)
    
    # Se não houver termo de pesquisa, o aluno pode querer ver todas as trilhas disponíveis na sua sala
    if not search_term:
        trilhas = sala_do_aluno.trilhas
        
        if not trilhas:
            return jsonify({"message": "Sua sala não possui trilhas cadastradas."}), 404
        
        return jsonify([t.to_dict() for t in trilhas]), 200

    termo_like = f"%{search_term}%"
    
    # 4. FILTRO DE PESQUISA E AUTORIZAÇÃO

    # Obtém os IDs das trilhas associadas à sala do aluno
    trilhas_na_sala_ids = [t.id for t in sala_do_aluno.trilhas]
    
    # Busca trilhas cujo nome contenha o termo
    # E que estejam na lista de IDs da sala do aluno
    trilhas_encontradas = Trilha.query.filter(
        Trilha.id.in_(trilhas_na_sala_ids), # Filtro de Autorização: A trilha deve estar na sala do aluno
        Trilha.nome.ilike(termo_like)       # Filtro de Pesquisa: Nome da trilha contém o termo
    ).all()

    if not trilhas_encontradas:
        return jsonify({"message": f"Nenhuma trilha encontrada com o termo '{search_term}' na sua sala."}), 404

    return jsonify([t.to_dict() for t in trilhas_encontradas]), 200

# ROTA PARA VER AS TRILHAS DISPONIVEIS NA SALA, PELO ALUNO - TESTADA E FUNCIONANDO
@app.route('/api/aluno/trilhas', methods=['GET'])
@jwt_required()
def get_aluno_trilhas():
    claims = get_jwt()
    
    # 1. VALIDAÇÃO DE FUNÇÃO: Garante que apenas ALUNOS acessem esta rota.
    if claims.get('funcao') != 'aluno':
        return jsonify({"message": "Acesso negado: Apenas Alunos podem acessar esta rota."}), 403

    # 2. EXTRAÇÃO DO ID: O identity agora é apenas o ID (string)
    identity = get_jwt_identity()
    
    try:
        # Tenta converter o ID (que é o identity) para inteiro
        aluno_id = int(identity)
    except ValueError:
        return jsonify({"message": "ID de aluno no token inválido."}), 401

    # 3. Encontra o aluno no banco
    aluno = Aluno.query.get(aluno_id)

    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # 4. Busca a sala do aluno (Usando .sala no singular, conforme o modelo 1:N)
    sala = aluno.sala
    
    if not sala:
        return jsonify({"message": "Você não está associado a nenhuma sala."}), 404

    # 5. Busca as trilhas da sala
    # Assumindo que a sala tem uma relação 'trilhas' que retorna uma lista
    trilhas_da_sala = [t.to_dict() for t in sala.trilhas]
    
    return jsonify({
        "sala_id": sala.id,
        "sala_nome": sala.nome,
        "trilhas": trilhas_da_sala
    }), 200
 # Mude debug=False em produção
# ROTA PARA VER OS JOGOS DE UMA TRILHA, PELO ALUNO - TESTADA E FUNCIONANDO
@app.route('/api/trilhas/<int:trilha_id>/jogos', methods=['GET'])
@jwt_required()
def get_jogos_da_trilha(trilha_id):
    claims = get_jwt()
    
    # 1. VALIDAÇÃO DE FUNÇÃO: Garante que apenas ALUNOS acessem esta rota.
    if claims.get('funcao') != 'aluno':
        return jsonify({"message": "Acesso negado: Apenas Alunos podem acessar esta rota."}), 403

    # 2. ENCONTRAR O ALUNO LOGADO
    try:
        aluno_id = int(get_jwt_identity())
    except ValueError:
        return jsonify({"message": "ID de aluno no token inválido."}), 401

    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # 3. VERIFICAR AUTORIZAÇÃO: O aluno tem acesso a esta trilha?
    
    # Obtém a sala do aluno (assumindo 1:N com 'aluno.sala')
    sala_do_aluno = aluno.sala
    
    if not sala_do_aluno:
        return jsonify({"message": "Você não está associado a nenhuma sala com trilhas disponíveis."}), 403

    # Verifica se o trilha_id está na lista de trilhas da sala do aluno
    trilha_valida_para_aluno = False
    
    # Percorre a coleção de trilhas da sala (sala_do_aluno.trilhas)
    for trilha in sala_do_aluno.trilhas:
        if trilha.id == trilha_id:
            trilha_valida_para_aluno = True
            break
            
    if not trilha_valida_para_aluno:
        return jsonify({"message": "Trilha indisponível: Esta trilha não está associada à sua sala."}), 403 # Forbidden

    # 4. ENCONTRAR A TRILHA (já sabemos que ela existe e está na sala)
    trilha = Trilha.query.get(trilha_id)
    
    # 5. RETORNA OS JOGOS
    # Como a relação já foi definida no modelo, é fácil acessar os jogos
    jogos_da_trilha = [j.to_dict() for j in trilha.jogos]
    
    return jsonify({
        "trilha_id": trilha.id,
        "trilha_nome": trilha.nome,
        "jogos": jogos_da_trilha
    }), 200

# ROTA PARA SALVAR DESEMPENHO DO ALUNO - TESTADA E FUNCIONANDO
@app.route('/api/desempenho', methods=['POST'])
@jwt_required()
def save_desempenho():
    claims = get_jwt()

    if claims.get('funcao') != 'aluno':
        return jsonify({"message": "Acesso negado: Apenas Alunos podem salvar desempenho."}), 403
    
    # 2. EXTRAÇÃO DE ID: Pega o ID puro do token
    identity = get_jwt_identity()
    try:
        aluno_id = int(identity)
    except ValueError:
        return jsonify({"message": "ID de aluno no token inválido."}), 401
    
    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # 3. Recebe os dados
    data = request.get_json()
    jogo_id = data.get('jogo_id')
    trilha_id = data.get('trilha_id')
    passou = data.get('passou')          
    
    # Campos que agora aceitam LISTAS/JSON
    acertos = data.get('acertos', [])    # Garante que seja pelo menos uma lista vazia
    erros = data.get('erros', [])        # Garante que seja pelo menos uma lista vazia

    # 4. Validação inicial dos dados
    # A validação agora checa se acertos e erros são listas, e se os IDs e 'passou' estão presentes.
    if not all([jogo_id, trilha_id, passou is not None, isinstance(acertos, list), isinstance(erros, list)]):
         return jsonify({"message": "Dados incompletos ou formatos inválidos. Verifique jogo, trilha, resultado e se acertos/erros são listas."}), 400

    # 5. Encontra a sala do aluno para associar o desempenho
    sala_do_aluno = aluno.sala # Usando a relação singular (1:N)
    if not sala_do_aluno:
        return jsonify({"message": "Você não está associado a nenhuma sala. Não é possível salvar o desempenho."}), 404

    # 6. Validação adicional: garante que o jogo e trilha existem e são válidos
    jogo = Jogo.query.get(jogo_id)
    trilha = Trilha.query.get(trilha_id)
    
    if not jogo or not trilha:
        return jsonify({"message": "Jogo ou trilha não encontrados."}), 404
        
    # VERIFICAÇÃO DE AUTORIZAÇÃO: Garante que a trilha é da sala do aluno
    if trilha not in sala_do_aluno.trilhas:
        return jsonify({"message": "Trilha não pertence à sua sala. Desempenho não pode ser salvo."}), 403

    # 7. Salva o desempenho no banco de dados
    try:
        novo_desempenho = DesempenhoJogo(
            aluno_id=aluno.id,
            jogo_id=jogo.id,
            trilha_id=trilha.id,
            sala_id=sala_do_aluno.id,
            passou=passou,
            acertos=acertos,  # SQLAlchemy salvará esta lista como JSON
            erros=erros       # SQLAlchemy salvará esta lista como JSON
        )
        db.session.add(novo_desempenho)
        db.session.commit()

        return jsonify({"message": "Desempenho salvo com sucesso!", "desempenho": novo_desempenho.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao salvar desempenho: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)