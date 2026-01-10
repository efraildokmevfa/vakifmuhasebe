from functools import wraps
from flask import request, jsonify, g, current_app
from app.models.auth import User # User modelini import ediyoruz
import jwt

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({'message': 'Token eksik!'}), 401

        try:
            data = User.verify_auth_token(token)
            if data is None:
                return jsonify({'message': 'Token geçersiz veya süresi dolmuş!'}), 401

            current_user = User.query.get(data['user_id'])
            if not current_user or not current_user.is_active:
                return jsonify({'message': 'Kullanıcı bulunamadı veya aktif değil!'}), 401
            g.current_user = current_user # Global context'e kullanıcıyı ekle
            g.current_user_roles = data.get('roles', [])

        except Exception as e:
            current_app.logger.error(f"Token doğrulama hatası: {e}")
            return jsonify({'message': 'Token doğrulanamadı!'}), 401

        return f(*args, **kwargs)
    return decorated

def role_required(roles_list):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user_roles'):
                return jsonify({'message': 'Yetkilendirme hatası: Kullanıcı rolleri bulunamadı. @token_required önce kullanılmalı.'}), 403

            user_roles = set(g.current_user_roles)
            required_roles = set(roles_list)

            if not user_roles.intersection(required_roles):
                return jsonify({'message': f'Bu işlem için yetkiniz yok. Gerekli roller: {", ".join(roles_list)}'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
