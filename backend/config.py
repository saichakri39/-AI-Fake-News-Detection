import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "veritas-secret-security-token-9982")
    
    # Update this with your Postgres password (e.g. replacing 'yourpassword' below)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", 
        "postgresql://postgres:chakri123@localhost:5432/veritas_db"
    )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")