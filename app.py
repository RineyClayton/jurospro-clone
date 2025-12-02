from flask import Flask, render_template, request, redirect, url_for, flash, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import os
import io
import csv
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///jurospro_clone.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
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
    interest_rate = db.Column(db.Float, default=0.0) # as percent per installment or per month (configurable)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    installments = db.relationship('Installment', backref='loan', lazy=True, cascade='all, delete')
    notes = db.Column(db.Text)

    def total_amount(self):
        # naive interest calculation: principal * (1 + rate/100)
        return round(self.principal * (1 + (self.interest_rate or 0)/100), 2)

class Installment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date)
    amount = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)

    def is_overdue(self):
        if self.paid:
            return False
        return datetime.utcnow().date() > self.due_date

# User loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/init')
def init_db():
    # Only for local setup convenience. Create DB, a demo user and some sample data.
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        u = User(username='admin')
        u.set_password('admin123')
        db.session.add(u)
        db.session.commit()
    # add sample client and loan if none exist
    if Client.query.count() == 0:
        c = Client(name='João Silva', phone='11999998888', cpf='123.456.789-00', email='joao@example.com')
        db.session.add(c)
        db.session.commit()
        l = Loan(client_id=c.id, principal=1000.0, interest_rate=2.0, notes='Empréstimo pessoal')
        db.session.add(l)
        db.session.commit()
        # create 3 installments
        for i in range(3):
            inst = Installment(loan_id=l.id, number=i+1, due_date=(datetime.utcnow().date() + timedelta(days=30*(i+1))), amount=round(l.total_amount()/3,2))
            db.session.add(inst)
        db.session.commit()
    return 'Initialized database with demo user (admin/admin123) and sample data. Go to /login.'

@app.route('/')
@login_required
def dashboard():
    # calculations
    loans = Loan.query.all()
    total_principal = sum(l.principal for l in loans)
    total_amount = sum(l.total_amount() for l in loans)
    installments = Installment.query.all()
    total_to_receive = sum(it.amount for it in installments if not it.paid)
    total_overdue = sum(it.amount for it in installments if (not it.paid and it.is_overdue()))
    paid_total = sum(it.amount for it in installments if it.paid)
    upcoming = [it for it in installments if (not it.paid and (it.due_date - datetime.utcnow().date()).days <=7)]
    return render_template('dashboard.html',
                           total_principal=total_principal,
                           total_amount=total_amount,
                           total_to_receive=total_to_receive,
                           total_overdue=total_overdue,
                           paid_total=paid_total,
                           upcoming=upcoming)

@app.route('/clients')
@login_required
def clients():
    clients = Client.query.order_by(Client.name).all()
    return render_template('clients.html', clients=clients)

@app.route('/clients/new', methods=['GET','POST'])
@login_required
def new_client():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form.get('phone')
        cpf = request.form.get('cpf')
        email = request.form.get('email')
        address = request.form.get('address')
        c = Client(name=name, phone=phone, cpf=cpf, email=email, address=address)
        db.session.add(c)
        db.session.commit()
        flash('Cliente criado com sucesso', 'success')
        return redirect(url_for('clients'))
    return render_template('new_client.html')

@app.route('/clients/<int:client_id>')
@login_required
def client_detail(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template('client_detail.html', client=client)

@app.route('/loans')
@login_required
def loans():
    loans = Loan.query.order_by(Loan.created_at.desc()).all()
    return render_template('loans.html', loans=loans)

@app.route('/loans/new', methods=['GET','POST'])
@login_required
def new_loan():
    clients = Client.query.order_by(Client.name).all()
    if request.method == 'POST':
        client_id = int(request.form['client_id'])
        principal = float(request.form['principal'])
        interest_rate = float(request.form.get('interest_rate') or 0)
        parcels = int(request.form.get('parcels') or 1)
        first_due = datetime.strptime(request.form.get('first_due'), '%Y-%m-%d').date()
        notes = request.form.get('notes')
        loan = Loan(client_id=client_id, principal=principal, interest_rate=interest_rate, notes=notes)
        db.session.add(loan)
        db.session.commit()
        total = loan.total_amount()
        per = round(total / parcels, 2)
        for i in range(parcels):
            due = first_due + timedelta(days=30*i)
            inst = Installment(loan_id=loan.id, number=i+1, due_date=due, amount=per)
            db.session.add(inst)
        db.session.commit()
        flash('Empréstimo criado', 'success')
        return redirect(url_for('loan_detail', loan_id=loan.id))
    return render_template('new_loan.html', clients=clients)

@app.route('/loans/<int:loan_id>')
@login_required
def loan_detail(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    return render_template('loan_detail.html', loan=loan)

@app.route('/installment/<int:inst_id>/pay', methods=['POST'])
@login_required
def pay_installment(inst_id):
    inst = Installment.query.get_or_404(inst_id)
    inst.paid = True
    inst.paid_at = datetime.utcnow()
    db.session.commit()
    flash('Parcela marcada como paga', 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/export/csv')
@login_required
def export_csv():
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Client','Loan ID','Installment #','Due Date','Amount','Paid','Paid At'])
    for it in Installment.query.join(Loan).join(Client).add_columns(Client.name, Loan.id, Installment.number, Installment.due_date, Installment.amount, Installment.paid, Installment.paid_at).all():
        row = [it[1], it[2], it[3], it[4].isoformat(), it[5], it[6].isoformat() if it[6] else '']
        cw.writerow(row)
    output = make_response(si.getvalue())
    output.headers['Content-Disposition'] = 'attachment; filename=installments.csv'
    output.headers['Content-type'] = 'text/csv'
    return output

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Credenciais inválidas', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Simple search
@app.route('/search')
@login_required
def search():
    q = request.args.get('q','')
    clients = Client.query.filter(Client.name.ilike(f'%{q}%')).all()
    loans = Loan.query.join(Client).filter(Client.name.ilike(f'%{q}%')).all()
    return render_template('clients.html', clients=clients, loans=loans)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
