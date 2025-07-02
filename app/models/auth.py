from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
import jwt
from datetime import datetime, timedelta
from flask import current_app

# Ara tablo: User ve Role arasında Many-to-Many ilişki için
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False) # Örn: admin, editor, viewer
    description = db.Column(db.String(255), nullable=True)

    users = relationship("User", secondary=user_roles, back_populates="roles")

    def __repr__(self):
        return f'<Role {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False) # Daha uzun hashler için artırıldı
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, role_name):
        return self.roles.filter(Role.name == role_name).count() > 0

    def get_roles(self):
        return [role.name for role in self.roles.all()]

    def generate_auth_token(self, expires_in=3600): # 1 saat geçerlilik süresi
        try:
            payload = {
                'exp': datetime.utcnow() + timedelta(seconds=expires_in),
                'iat': datetime.utcnow(),
                'sub': self.id, # Subject: kullanıcı ID'si
                'roles': self.get_roles() # Token içine rolleri de ekleyelim
            }
            token = jwt.encode(
                payload,
                current_app.config['SECRET_KEY'],
                algorithm='HS256'
            )
            return token
        except Exception as e:
            return e

    @staticmethod
    def verify_auth_token(token):
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            return {'user_id': payload['sub'], 'roles': payload.get('roles', [])}
        except jwt.ExpiredSignatureError:
            return None  # Token süresi dolmuş
        except jwt.InvalidTokenError:
            return None  # Geçersiz token
        except Exception:
            return None


    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'roles': [role.to_dict() for role in self.roles]
        }
