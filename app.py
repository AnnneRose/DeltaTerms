from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
import os

from delta import DeltaGenerator
from chat import Chatbot
import json
import uuid
from datetime import datetime


load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db = SQLAlchemy(app)
delta_generator = DeltaGenerator()
chatbot = Chatbot()
LOGS_DIR = "conversation_logs"
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
CORS(
    app,
    resources={r"/api/.*": {
        "origins": [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
    }},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)


@app.before_request
def log_request():
    print(
        "Incoming request:",
        request.method,
        request.path,
        "Origin=", request.headers.get("Origin"),
        "Content-Type=", request.content_type,
    )

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)

class Websites(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chatbot_name = db.Column(db.String(200), nullable=False, unique=True)
    previous_delta = db.Column(db.String(2000), nullable=True)
    content_1 = db.Column(db.Text, nullable=False)
    content_2 = db.Column(db.Text, nullable=True)
    url_name = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html')

@app.route("/api/signup", methods=["POST", "OPTIONS"])
def signup():
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    

    # Validation
    if not username or not password:
        return jsonify(error="Username and password are required"), 400
    
    if len(password) < 6:
        return jsonify(error="Password must be at least 6 characters"), 400
    
    # Check if user already exists
    if User.query.filter_by(username=username).first():
        return jsonify(error="Username already exists"), 400
    
    # Create new user
    user = User(username=username, email=email or username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    login_user(user)
    return jsonify(message="User created successfully", user_id=user.id, username=user.username), 201

@app.route("/api/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify(error="Username and password are required"), 400
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify(error="Invalid username or password"), 401
    
    login_user(user)
    return jsonify(message="Login successful", user_id=user.id, username=user.username), 200

@app.route("/api/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify(message="Logout successful"), 200

@app.route("/api/me", methods=["GET"])
def get_current_user():
    if current_user.is_authenticated:
        return jsonify(user_id=current_user.id, username=current_user.username, email=current_user.email), 200
    return jsonify(error="Not authenticated"), 401

# TOS History Endpoints

@app.route("/api/tos-history", methods=["POST", "OPTIONS"])
@login_required
def save_tos_history():
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json(silent=True) or {}
    print("data:",data)
    chatbot_name = data.get('chatbot_name', '').strip()
    current_tos = data.get('current_tos', '').strip()
    # previous_tos = data.get('previous_tos', '').strip()
    website_url = data.get('website_url', '').strip()
    # delta = data.get('delta', '').strip()
    
    if not chatbot_name or not current_tos or not website_url:
        return jsonify(error="chatbot_name, current_tos, and website_url are required"), 400
    
    tos_record = Websites(
        chatbot_name=chatbot_name,
        content_1=current_tos,
        content_2=None,
        url_name=website_url,
        previous_delta= None,
        user_id=current_user.id
    )
    record = db.session.query(Websites).filter_by(chatbot_name=chatbot_name).first()
    if record:
        print(f"[upsert] UPDATE path for chatbot_name={chatbot_name!r} (existing id={record.id})")
        print(f"[upsert] old content_1 length={len(record.content_1 or '')}, new content length={len(current_tos)}")
        delta = generate_delta(record.content_1, current_tos)
        print(f"[upsert] generated delta: {delta!r}")
        record.previous_delta = delta
        record.content_2 = record.content_1
        record.content_1 = tos_record.content_1
        record.url_name = tos_record.url_name
    else:
        print(f"[upsert] CREATE path for chatbot_name={chatbot_name!r} (no existing record found)")
        existing_names = [r.chatbot_name for r in Websites.query.filter_by(user_id=current_user.id).all()]
        print(f"[upsert] this user's existing chatbot_names: {existing_names}")
        db.session.add(tos_record)
    db.session.commit()
        
    
    return jsonify(message="TOS history saved", id=tos_record.id), 201
def generate_delta(old_tos, new_tos):
    return delta_generator.get_delta(old_tos, new_tos)
    
@app.route("/api/tos-history", methods=["GET"])
@login_required
def get_tos_history():
    tos_records = Websites.query.filter_by(user_id=current_user.id).all()
    print("Fetched TOS records for user_id", current_user.id, ":", tos_records)
    return jsonify([
        {
            'id': record.id,
            'chatbot_name': record.chatbot_name,
            'current_tos': record.content_1,
            'previous_tos': record.content_2,
            'website_url': record.url_name,
            'delta': record.previous_delta
        }
        for record in tos_records
    ]), 200

def log_chat_turn(conversation_id, service_id, history, user_message, assistant_reply):
    os.makedirs(LOGS_DIR, exist_ok=True)
    path = os.path.join(LOGS_DIR, f"{conversation_id}.json")

    turns = []
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            turns.append({"role": role, "content": content})
    turns.append({"role": "user", "content": user_message})
    turns.append({"role": "assistant", "content": assistant_reply})

    payload = {
        "name": conversation_id,
        "service_id": service_id,
        "user_id": current_user.id if current_user.is_authenticated else None,
        "timestamp": datetime.now().isoformat(),
        "conversation": turns,
        "retrieved_context": "",
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


@app.route("/api/chat/<int:service_id>", methods=["POST", "OPTIONS"])
@login_required
def chat(service_id):
    if request.method == "OPTIONS":
        return "", 200

    record = Websites.query.filter_by(id=service_id, user_id=current_user.id).first()
    if not record:
        return jsonify(error="Service not found"), 404

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    conversation_id = (data.get("conversation_id") or "").strip() or str(uuid.uuid4())[:8]

    if not message:
        return jsonify(error="message is required"), 400

    try:
        reply = chatbot.get_response(
            user_input=message,
            history=history,
            service_name=record.chatbot_name,
            current_tos=record.content_1,
            previous_tos=record.content_2,
            delta=record.previous_delta,
        )
    except Exception as exc:
        print(f"[chat] generation failed: {type(exc).__name__}: {exc}")
        return jsonify(error="The model is busy or unavailable. Please try again."), 502

    if not reply:
        return jsonify(error="The model returned an empty response. Please try again."), 502

    try:
        log_chat_turn(conversation_id, service_id, history, message, reply)
    except Exception as exc:
        print(f"[chat] logging failed (non-fatal): {type(exc).__name__}: {exc}")

    return jsonify(reply=reply, conversation_id=conversation_id), 200


@app.route("/api/hello")
def hello():
    return jsonify(message="Hello from Flask")

@app.route("/api/data", methods=["POST", "OPTIONS"])
def data():
    if request.method == "OPTIONS":
        return "", 200
    
    print("Route /api/data entered", request.method, "content_type=", request.content_type)

    if request.is_json:
        body = request.get_json(silent=True) or {}
    else:
        body = request.form.to_dict()
        uploaded_file = request.files.get("file")
        if uploaded_file:
            body["file_name"] = uploaded_file.filename
            body["file_type"] = uploaded_file.mimetype
            try:
                if uploaded_file.mimetype.startswith("text/"):
                    body["file_content"] = uploaded_file.read().decode("utf-8", errors="ignore")
                else:
                    body["file_content"] = f"<binary file {uploaded_file.filename} type={uploaded_file.mimetype}>"
            except Exception:
                body["file_content"] = f"<unable to read file {uploaded_file.filename}>"

    return jsonify(received=body)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Sanity check to print out all of the users and websites
    with app.app_context():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        print(inspector.get_table_names())

    with app.app_context():
        print(User.query.all())

        for row in User.query.all():
            print(row.id, row.username, row.email)

        for row in Websites.query.all():
            print(row.id, row.chatbot_name, row.url_name, row.user_id, row.content_1, row.content_2, row.previous_delta)
    app.run(debug=True)