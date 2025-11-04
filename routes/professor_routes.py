from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy.orm import joinedload
from sqlalchemy import or_

# Importações de Ferramentas (IA)
import google.generativeai as genai
import json

# Importações dos Modelos
from models import db, Aluno, Trilha, Jogo, DesempenhoJogo, Professor, Sala

# Definição do Blueprint
professor_bp = Blueprint('professor_bp', __name__, url_prefix='/api/professor')

try:
    IA_MODEL = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    IA_MODEL = None

#============================================ROTAS DO PROFESSOR====================================================

# -------------------------CRUD COM AS SALAS--------------------------------

#ROTAS PARA PESQUISAR SALAS POR NOME - NÃO TESTADA
@professor_bp.route('/salas/search', methods=['GET'])
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
@professor_bp.route('/salas', methods=['GET'])
@jwt_required()
def get_sala():
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403

    professor_id = get_jwt_identity()

    salas = Sala.query.filter_by(professor_id=professor_id).all()
    
    if not salas:
        return jsonify({"message": "Nenhuma sala encontrada para este professor."})

    salas_com_alunos = []
    for sala in salas:
        sala_dict = sala.to_dict()
        sala_dict['alunos'] = [aluno.to_dict() for aluno in sala.alunos]
        salas_com_alunos.append(sala_dict)
    
    return jsonify(salas_com_alunos), 200

@professor_bp.route('/trilhas', methods=['GET'])
@jwt_required()
def get_trilhas():
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403

    # Busca todas as trilhas (sem filtrar por professor)
    trilhas = Trilha.query.all()

    if not trilhas:
        return jsonify({"message": "Nenhuma trilha cadastrada no sistema."}), 200

    trilhas_data = [trilha.to_dict() for trilha in trilhas]

    return jsonify(trilhas_data), 200

# ROTA PARA CRIAR SALAS - TESTADA E FUNCIONANDO
@professor_bp.route('/salas', methods=['POST'])
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
    
@professor_bp.route('/salas/<int:sala_id>', methods=['GET'])
@jwt_required()
def get_sala_by_id(sala_id):
    claims = get_jwt()

    # 1. Verifica se o usuário logado é um professor
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403

    # 2. Obtém o ID do professor autenticado
    professor_id = get_jwt_identity()

    # 3. Busca a sala com o ID informado e pertencente ao professor logado
    sala = Sala.query.filter_by(id=sala_id, professor_id=professor_id).first()

    if not sala:
        return jsonify({"message": "Sala não encontrada ou você não tem permissão para acessá-la."}), 404

    # 4. Monta o dicionário da sala com os alunos vinculados
    sala_dict = sala.to_dict()
    sala_dict['alunos'] = [aluno.to_dict() for aluno in sala.alunos]

    # 5. Retorna os dados completos da sala
    return jsonify(sala_dict), 200

# ROTA PARA EDITAR UMA SALA - TESTADA E FUNCIONANDO
@professor_bp.route('/salas/<int:sala_id>', methods=['PUT'])
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
@professor_bp.route('/salas/<int:sala_id>', methods=['DELETE'])
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

#ROTA PARA PESQUISAR ALUNOS POR NOME - NÃO TESTADA
@professor_bp.route('/alunos/search', methods=['GET'])
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
@professor_bp.route('/salas/<int:sala_id>/alunos', methods=['GET'])
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
@professor_bp.route('/salas/<int:sala_id>/alunos', methods=['POST'])
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
@professor_bp.route('/salas/<int:sala_id>/alunos/<int:aluno_id>', methods=['PUT'])
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
@professor_bp.route('/salas/<int:sala_id>/alunos/<int:aluno_id>', methods=['DELETE'])
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
@professor_bp.route('/alunos/<int:aluno_id>', methods=['GET'])
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
@professor_bp.route('/alunos/<int:aluno_id>/historico/trilha/<int:trilha_id>', methods=['GET'])
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

# ROTA PARA VER ANALISE DA IA DO DESEMPENHO DO ALUNO - AINDA NÃO TESTADA
@professor_bp.route('/alunos/<int:aluno_id>/historico/trilha/<int:trilha_id>/analise-ia', methods=['GET'])
@jwt_required()
def get_analise_ia(aluno_id, trilha_id):
    claims = get_jwt()
    if claims.get('funcao') != 'professor':
        return jsonify({"message": "Acesso negado: Apenas Professores podem acessar esta rota."}), 403
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
    
    if IA_MODEL is None:
        return jsonify({"message": "Serviço de IA indisponível. Configuração inicial falhou."}), 503
        
    # 2. Busca o histórico de desempenho (mesma lógica da rota anterior)
    desempenhos = DesempenhoJogo.query.filter_by(aluno_id=aluno_id, trilha_id=trilha_id)\
                                     .options(joinedload(DesempenhoJogo.jogo))\
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
        response = IA_MODEL.generate_content(prompt)
        analise = response.text
        
        return jsonify({"analise_ia": analise}), 200
    except Exception as e:
        return jsonify({"message": f"Erro ao gerar análise da IA: {str(e)}"}), 500

# =====================================FIM DAS ROTAS DO PROFESSOR======================================