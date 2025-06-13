from flask import Flask, request, jsonify
from config import Config
from models import db, Aluno, Trilha, Jogo, DesempenhoJogo # Importa todos os modelos
from datetime import datetime
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from flask_cors import CORS

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Configuração do JWT
app.config["JWT_SECRET_KEY"] = "grupofunction" 
jwt = JWTManager(app)

db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/api/criar_aluno', methods=['POST'])
def criar_aluno():
    data = request.get_json()

    nome = data.get('nome')
    email = data.get('email')
    senha = data.get('senha')


    if not nome or not email or not senha:
        return jsonify({"message": "Nome, senha e email são obrigatórios."}), 400

    if Aluno.query.filter_by(email=email).first():
        return jsonify({"message": "Email já cadastrado."}), 409 # Conflict

    novo_aluno = Aluno(nome=nome, email=email)
    novo_aluno.senha = senha # Atribui a senha, o setter fará o hash
    try:
        db.session.add(novo_aluno)
        db.session.commit()
        return jsonify({"message": "Aluno criado com sucesso!", "aluno": novo_aluno.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao criar aluno: {str(e)}"}), 500

@app.route('/api/login_aluno', methods=['POST'])
def login_aluno():
    email = request.json.get('email', None)
    senha = request.json.get('senha', None)

    aluno = Aluno.query.filter_by(email=email).first()

    if not aluno or not aluno.verificar_senha(senha): 
        return jsonify({"message": "Email ou senha incorretos."}), 401 

    access_token = create_access_token(identity=str(aluno.id))
    return jsonify(access_token=access_token), 200


@app.route('/api/meu-perfil', methods=['GET'])
@jwt_required() 
def meu_perfil():
    current_aluno_id = get_jwt_identity() 

    aluno = Aluno.query.get(current_aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado (via token)."}), 404

    return jsonify({"message": "Bem-vindo ao seu perfil!", "aluno": aluno.to_dict()}), 200

@app.route('/api/desempenho_jogo', methods=['POST'])
def registrar_desempenho_jogo():
    data = request.get_json()

    if not data:
        return jsonify({"message": "Dados JSON inválidos."}), 400

    trilha_id = data.get('trilha')
    jogo_id = data.get('jogo')
    aluno_id = data.get('aluno_id')
    passou_str = data.get('passou') 
    acertos_raw = data.get('acertos', [])
    erros_raw = data.get('erros', [])

    if not all(isinstance(id, int) for id in [jogo_id, trilha_id, aluno_id]):
        return jsonify({"message": "IDs de aluno, jogo e trilha devem ser inteiros."}), 400

    if not isinstance(passou_str, str) or passou_str.lower() not in ['true', 'false']:
         return jsonify({"message": "'passou' deve ser 'true' ou 'false'."}), 400

    passou = passou_str.lower() == 'true'

    jogo = Jogo.query.get(jogo_id)
    trilha = Trilha.query.get(trilha_id)

    if not jogo:
        return jsonify({"message": f"Jogo com ID {jogo_id} não encontrado."}), 404
    if not trilha:
        return jsonify({"message": f"Trilha com ID {trilha_id} não encontrada."}), 404

    if jogo.trilha_id != trilha_id:
        return jsonify({"message": "O jogo não pertence à trilha informada."}), 400

    try:
        novo_desempenho = DesempenhoJogo(
            jogo_id=jogo_id,
            trilha_id=trilha_id,
            aluno_id=aluno_id,
            passou=passou,
            acertos=acertos_raw,
            erros=erros_raw
            
        )
        db.session.add(novo_desempenho)
        db.session.commit()
        return jsonify({"message": "Desempenho do jogo registrado com sucesso!", "desempenho": novo_desempenho.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao registrar desempenho: {str(e)}"}), 500


@app.route('/api/trilhas', methods=['GET'])
def get_trilhas():
    trilhas = Trilha.query.all()
    return jsonify([trilha.to_dict() for trilha in trilhas]), 200

@app.route('/api/trilhas/<int:trilha_id>', methods=['GET'])
def get_trilha(trilha_id):
    trilha = Trilha.query.get(trilha_id)
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404
    return jsonify(trilha.to_dict()), 200

@app.route('/api/jogos', methods=['GET'])
def get_jogos():
    trilha_id = request.args.get('trilha_id', type=int)
    if trilha_id:
        jogos = Jogo.query.filter_by(trilha_id=trilha_id).all()
    else:
        jogos = Jogo.query.all()
    return jsonify([jogo.to_dict() for jogo in jogos]), 200

@app.route('/api/jogos/<int:jogo_id>', methods=['GET'])
def get_jogo(jogo_id):
    jogo = Jogo.query.get(jogo_id)
    if not jogo:
        return jsonify({"message": "Jogo não encontrado."}), 404
    return jsonify(jogo.to_dict()), 200

# Rota para obter o histórico de desempenho de um aluno
@app.route('/api/alunos/<int:aluno_id>/historico', methods=['GET'])
def get_historico_aluno(aluno_id):
    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404

    # Carrega os desempenhos do aluno, ordenados por data
    # Usando .options(db.joinedload()) para carregar Jogo e Trilha junto
    # isso evita N+1 queries, melhorando a performance.
    desempenhos = DesempenhoJogo.query.filter_by(aluno_id=aluno_id)\
                                 .options(db.joinedload(DesempenhoJogo.jogo))\
                                 .options(db.joinedload(DesempenhoJogo.trilha))\
                                 .order_by(DesempenhoJogo.data_hora.desc())\
                                 .all()

    historico_data = []
    for d in desempenhos:
        jogo_nome = d.jogo.nome if d.jogo else f"Jogo ID {d.jogo_id}"
        trilha_nome = d.trilha.nome if d.trilha else f"Trilha ID {d.trilha_id}"
        historico_data.append({
            "id": d.id,
            "jogo_id": d.jogo_id,
            "jogo_nome": jogo_nome,
            "trilha_id": d.trilha_id,
            "trilha_nome": trilha_nome,
            "data_hora": d.data_hora.isoformat(),
            "passou": d.passou,
            "acertos": d.acertos,
            "erros": d.erros
        })
    return jsonify(historico_data), 200

# Rota para obter o histórico de desempenho de um aluno em uma trilha específica
@app.route('/api/alunos/<int:aluno_id>/historico/trilha/<int:trilha_id>', methods=['GET'])
def get_historico_aluno_por_trilha(aluno_id, trilha_id):
    aluno = Aluno.query.get(aluno_id)
    trilha = Trilha.query.get(trilha_id)

    if not aluno:
        return jsonify({"message": "Aluno não encontrado."}), 404
    if not trilha:
        return jsonify({"message": "Trilha não encontrada."}), 404

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


if __name__ == '__main__':
    app.run(debug=True) # Mude debug=False em produção