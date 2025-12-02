# JurosPRO Clone — Como rodar localmente e deploy

## Rodar localmente (rápido)

1. Tenha Python 3.10+ instalado.
2. Crie um virtualenv: `python -m venv venv && source venv/bin/activate` (Unix) ou `venv\Scripts\activate` (Windows).
3. Instale dependências: `pip install -r requirements.txt`.
4. Exporte variáveis (opcional): `export FLASK_APP=app.py`.
5. Rode `python app.py` ou `flask run`.
6. Acesse `http://127.0.0.1:5000/init` para criar usuário demo (admin/admin123) e dados de exemplo.
7. Acesse `http://127.0.0.1:5000/login`.

## Deploy (recomendado)

- Para deixar online use Render, Railway, Fly.io ou Heroku.
- Configure `DATABASE_URL` se quiser usar Postgres (Render/Railway). Caso contrário, usa SQLite.
- Configure `SECRET_KEY` em variáveis ambiente.
- Para notificações via WhatsApp ou SMS, integre Twilio/360dialog e configure as rotas para enviar mensagens.
