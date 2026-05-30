from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Plaintext for simple robust local demo

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username
        }

class PredictionHistory(db.Model):
    __tablename__ = "prediction_history"

    id = db.Column(db.Integer, primary_key=True)
    input_type = db.Column(db.String(20), nullable=False)  # 'text', 'file', 'url'
    source_name = db.Column(db.String(255), nullable=False) # File name, URL, or Text title
    text_content = db.Column(db.Text, nullable=False)
    trust_score = db.Column(db.Integer, nullable=False)    # 0 to 100
    category = db.Column(db.String(20), nullable=False)     # 'Trusted', 'Suspicious', 'Fake'
    
    # Individual model estimates
    nb_confidence = db.Column(db.Float, nullable=False)
    lr_confidence = db.Column(db.Float, nullable=False)
    rf_confidence = db.Column(db.Float, nullable=False)
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "input_type": self.input_type,
            "source_name": self.source_name,
            "text_content": self.text_content[:300] + ("..." if len(self.text_content) > 300 else ""),
            "trust_score": self.trust_score,
            "category": self.category,
            "nb_confidence": round(self.nb_confidence * 100, 1),
            "lr_confidence": round(self.lr_confidence * 100, 1),
            "rf_confidence": round(self.rf_confidence * 100, 1),
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }