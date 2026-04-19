from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)

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

if __name__ == '__main__':
    # db.create_all()
    app.run(debug=True)