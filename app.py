from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS, cross_origin

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['CORS_HEADERS'] = 'Content-Type'
db = SQLAlchemy(app)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

@app.before_request
def log_request():
    print(
        "Incoming request:",
        request.method,
        request.path,
        "Origin=", request.headers.get("Origin"),
        "Content-Type=", request.content_type,
    )

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Websites(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    previous_delta = db.Column(db.String(2000), nullable=True)
    content_1 = db.Column(db.Text, nullable=False)
    content_2 = db.Column(db.Text, nullable=True)
    url_name = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/api/hello")
def hello():
    return jsonify(message="Hello from Flask")

@app.route("/api/data", methods=["POST", "OPTIONS"])
@cross_origin(origins="http://localhost:3000", methods=["POST", "OPTIONS"])
def data():
    print("Route /api/data entered", request.method, "content_type=", request.content_type)
    if request.method == "OPTIONS":
        return "", 204

    if request.is_json:
        body = request.get_json()
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
    # db.create_all()
    app.run(debug=True)