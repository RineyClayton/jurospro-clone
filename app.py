from flask import Flask, render_template, request, redirect, url_for, flash, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os, io, csv

# --------------------------------------------------------------------
# CONFIGURAÇÃO BÁSICA
# --------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = "chave-secreta-fixa"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///app.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# --------------------------------------------------------------------
# MODELOS
# --------------------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    cpf = db.Column(db.String(20))
    email = db.Column(db.String(200))
    address = db.Column(db.String(300))
    loans = db.relationship('Loan', backref='client', lazy=True)


class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    principal = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    installments = db.relationship('Installment', backref='loan', lazy=True, cascade="all, delete")

    def total_amount(self):
        return round(self.principal * (1 + (self.interest_rate or 0)/100), 2)


class Installment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date)
    amount = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime)


# --------------------------------------------------------------------
# LOGIN MANAGER
# --------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --------------------------------------------------------------------
# AUTO-CREATE DB + ADMIN (FUNCIONA NO RENDER)
# --------------------------------------------------------------------
with app.app_context():
    db.create_all()

    admin = User.query.filter_by(username="admin").first()
    if not admin:
        u = User(username="admin")
        u.set_password("123456")
        db.session.add(u)
        db.session.commit()
        print(">>> ADMIN CRIADO AUTOMATICAMENTE (admin / 123456)")


# --------------------------------------------------------------------
# ROTAS
# --------------------------------------------------------------------
@app.route('/')
@login_required
def dashboard():
    loans = Loan.query.all()
    installments = Installment.query.all()

    total_principal = sum(l.principal for l in loans)
    total_amount = sum(l.total_amount() for l in loans)
    total_to_receive = sum(i.amount for i in installments if not i.paid)
    total_overdue = sum(i.amount for i in installments if (not i.paid and i.due_date < datetime.utcnow().date()))
    paid_total = sum(i.amount for i in installments if i.paid)

    upcoming = [
        i for i in installments
        if not i.paid and (i.due_date - datetime.utcnow().date()).days <= 7
    ]

    return render_template(
        "dashboard.html",
        total_principal=total_principal,
        total_amount=total_amount,
        total_to_receive=total_to_receive,
        total_overdue=total_overdue,
        paid_total=paid_total,
        upcoming=upcoming
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Credenciais inválidas", "danger")
    return render_template("login.html")


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


# --------------------------------------------------------------------
# INICIAR APP
# --------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
