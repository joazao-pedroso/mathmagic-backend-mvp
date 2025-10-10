from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import or_
from models import db, Trilha, Jogo, Professor

# Definição do Blueprint
admin_bp = Blueprint('admin_bp', __name__, url_prefix='/api/admin')

#-------------------CRUD COM AS TRILHAS---------------------

# ROTA PARA PESQUISAR TRILHAS POR NOME - TESTADA E FUNCIONANDO
@admin_bp.route('/trilhas/search', methods=['GET'])
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
@admin_bp.route('/trilhas', methods=['GET'])
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
@admin_bp.route('/trilhas', methods=['POST'])
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
@admin_bp.route('/trilhas/<int:trilha_id>', methods=['PUT'])
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
@admin_bp.route('/trilhas/<int:trilha_id>', methods=['DELETE'])
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

# ROTA DE PESQUISAR JOGOS POR NOME - NÃO TESTADA
@admin_bp.route('/jogos/search', methods=['GET'])
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
@admin_bp.route('/jogos', methods=['GET'])
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
@admin_bp.route('/jogos', methods=['POST'])
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
@admin_bp.route('/jogos/<int:jogo_id>', methods=['PUT'])
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
@admin_bp.route('/jogos/<int:jogo_id>', methods=['DELETE'])
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

#ROTA DE PESQUISAR PROFESSORES POR NOME - NÃO TESTADA
@admin_bp.route('/professores/search', methods=['GET'])
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
@admin_bp.route('/professores', methods=['GET'])
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
@admin_bp.route('/professores', methods=['POST'])
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
@admin_bp.route('/professores/<int:professor_id>', methods=['PUT'])
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
@admin_bp.route('/professores/<int:professor_id>', methods=['DELETE'])
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