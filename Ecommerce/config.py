import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "amazon-style-demo-secret")
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'ecommerce.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
