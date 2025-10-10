from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy.orm import joinedload

# Importações dos Modelos
from models import db, Aluno, Trilha, Jogo, DesempenhoJogo, Sala 

# Definição do Blueprint
aluno_bp = Blueprint('aluno_bp', __name__, url_prefix='/api/aluno')

# =================================ROTAS DO ALUNO================================================

# ROTA PARA PESQUISAR AS TRILHAS POR NOME - NÃO TESTADA
@aluno_bp.route('/trilhas/search', methods=['GET'])
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
@aluno_bp.route('/trilhas', methods=['GET'])
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

# ROTA PARA VER OS JOGOS DE UMA TRILHA, PELO ALUNO - TESTADA E FUNCIONANDO
@aluno_bp.route('/trilhas/<int:trilha_id>/jogos', methods=['GET'])
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
@aluno_bp.route('/desempenho', methods=['POST'])
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
