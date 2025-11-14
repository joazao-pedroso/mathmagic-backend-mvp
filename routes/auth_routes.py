from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt
from blacklist import BLACKLIST
from models import db, Admin, Professor, Aluno
from flask_cors import CORS

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/api/auth')

# ROTA DE REGISTRO DO ADM QUE RETORNA COM A SENHA HASH - TESTADA E FUNCIONANDO
@auth_bp.route('/register/admin', methods=['POST'])
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

#ROTA DE LOGIN GERAL - TESTADA E FUNCIONANDO
@auth_bp.route('/login', methods=['POST'])
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

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    
    # Adiciona o JTI à lista de bloqueio
    if jti:
        BLACKLIST.add(jti)
        return jsonify({"message": "Logout bem-sucedido. Token revogado."}), 200
    
    return jsonify({"message": "Erro ao revogar token."}), 500