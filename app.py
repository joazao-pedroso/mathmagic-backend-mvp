from dotenv import load_dotenv
import os
from datetime import timedelta

# Importações ESSENCIAIS para a inicialização
from flask import Flask
from config import Config
from models import db
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_cors import CORS

# Importações específicas para a IA e o BLACKLIST
import google.generativeai as genai

# -------------------------------------------------------------
# 1. PRÉ-CONFIGURAÇÃO
# -------------------------------------------------------------
load_dotenv() 
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

# Variável GLOBAL para tokens revogados (BLACKLIST)
BLACKLIST = set()

# -------------------------------------------------------------
# 2. INICIALIZAÇÃO DO FLASK E CONFIGS
# -------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)

# Configurações do JWT que usam timedelta
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "fallback-secret-key") # Use uma variável de ambiente!


CORS(app)
jwt = JWTManager(app)

db.init_app(app)
migrate = Migrate(app, db)

# -------------------------------------------------------------
# 3. IMPORTAÇÃO E REGISTRO DOS BLUEPRINTS (CRÍTICO)
# -------------------------------------------------------------
from routes.auth_routes import auth_bp
from routes.professor_routes import professor_bp
from routes.aluno_routes import aluno_bp
from routes.admin_routes import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(professor_bp)
app.register_blueprint(aluno_bp)


# -------------------------------------------------------------
# 4. FUNÇÃO DE CHECAGEM DE REVOGAÇÃO (CALLBACK JWT)
# -------------------------------------------------------------
@jwt.token_in_blocklist_loader
def check_if_token_is_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return jti in BLACKLIST 

# -------------------------------------------------------------
# 5. EXECUÇÃO
# -------------------------------------------------------------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True) # Mude debug=False em produção