from app import app, db
from models.user import User

with app.app_context():
    print("🔧 Apagando e recriando todas as tabelas...")
    db.drop_all()
    db.create_all()
    print("✔️ Banco recriado com sucesso!")

    # Criar usuário admin
    admin_email = "admin@admin.com"
    admin_password = "123456"

    # Verifica se já existe
    existing = User.query.filter_by(email=admin_email).first()
    if existing:
        print("⚠️ Admin já existe, não será recriado.")
    else:
        print("🔧 Criando usuário admin...")
        u = User(name="admin", email=admin_email)
        u.set_password(admin_password)
        db.session.add(u)
        db.session.commit()
        print("✔️ Usuário admin criado!")

print("🚀 Finalizado! Reinicie o serviço no Render se necessário.")
