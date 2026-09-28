"""
Central place for Flask extension instances.
Keeping them here (instead of in app.py) avoids circular imports:
models.py and routes/*.py can import `db` and `login_manager`
without importing the app itself.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"
