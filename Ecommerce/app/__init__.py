from flask import Flask

from config import Config

from .extensions import db, login_manager, migrate


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from .models import User
    from .routes.admin import admin_bp
    from .routes.api import api_bp
    from .routes.auth import auth_bp
    from .routes.web import web_bp
    from .services.seed import seed_data

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(web_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        db.create_all()
        seed_data()

    return app
