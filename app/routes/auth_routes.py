from flask import request, jsonify, g, current_app
# from functools import wraps # Artık burada değil
from app import db
from app.models.auth import User, Role
from . import auth_bp
from app.utils.decorators import token_required, role_required # Decorator'ler buradan import ediliyor
import jwt

# --- Rota İşleyicileri ---
@auth_bp.route('/register', methods=['POST'])
# @token_required # Register için token gerekmez
def register_user():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Eksik bilgi: username, email ve password zorunludur'}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Bu kullanıcı adı zaten mevcut'}), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Bu e-posta adresi zaten kayıtlı'}), 409

    new_user = User(
        username=data['username'],
        email=data['email'].lower()
    )
    new_user.set_password(data['password'])

    # Varsayılan rol ataması (opsiyonel, örn: 'user')
    default_role_name = data.get('role', 'user') # İstekte rol belirtilmezse 'user' ata
    default_role = Role.query.filter_by(name=default_role_name).first()
    if default_role:
        new_user.roles.append(default_role)
    else:
        # Eğer varsayılan rol DB'de yoksa, oluşturulabilir veya hata döndürülebilir.
        # Şimdilik rolsüz oluşturmasına izin verelim veya loglayalım.
        current_app.logger.warning(f"Varsayılan rol '{default_role_name}' bulunamadı, kullanıcı {data['username']} rolsüz oluşturuluyor.")


    db.session.add(new_user)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Kullanıcı kaydı hatası: {e}")
        return jsonify({'message': f'Kullanıcı kaydedilirken bir hata oluştu: {str(e)}'}), 500

    return jsonify({'message': 'Kullanıcı başarıyla oluşturuldu', 'user': new_user.to_dict()}), 201

@auth_bp.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data or not data.get('username_or_email') or not data.get('password'):
        return jsonify({'message': 'Eksik bilgi: username_or_email ve password zorunludur'}), 400

    user = User.query.filter((User.username == data['username_or_email']) | (User.email == data['username_or_email'].lower())).first()

    if user and user.check_password(data['password']):
        if not user.is_active:
            return jsonify({'message': 'Kullanıcınız aktif değil. Lütfen yönetici ile iletişime geçin.'}), 403

        token = user.generate_auth_token()
        return jsonify({
            'message': 'Giriş başarılı',
            'token': token,
            'user_id': user.id,
            'username': user.username,
            'roles': user.get_roles()
        }), 200

    return jsonify({'message': 'Geçersiz kullanıcı adı/e-posta veya şifre'}), 401

@auth_bp.route('/users', methods=['GET'])
@token_required
@role_required(['admin']) # Sadece adminler tüm kullanıcıları listeleyebilir
def get_all_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users]), 200

@auth_bp.route('/users/<int:user_id>', methods=['GET'])
@token_required
# Kullanıcı kendi bilgilerini veya admin başka kullanıcı bilgilerini görebilir
def get_user_by_id(user_id):
    if g.current_user.id != user_id and not g.current_user.has_role('admin'):
        return jsonify({'message': 'Bu kullanıcı bilgilerini görüntüleme yetkiniz yok.'}), 403

    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict()), 200


@auth_bp.route('/users/<int:user_id>/roles', methods=['POST'])
@token_required
@role_required(['admin']) # Sadece adminler rol atayabilir
def assign_role_to_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    if not data or not data.get('role_name'):
        return jsonify({'message': 'Eksik bilgi: role_name zorunludur'}), 400

    role_name = data['role_name']
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        return jsonify({'message': f"Rol '{role_name}' bulunamadı."}), 404

    if user.has_role(role_name):
        return jsonify({'message': f"Kullanıcı zaten '{role_name}' rolüne sahip."}), 409

    user.roles.append(role)
    db.session.commit()
    return jsonify({'message': f"'{role_name}' rolü kullanıcıya başarıyla atandı.", 'user': user.to_dict()}), 200

@auth_bp.route('/users/<int:user_id>/roles/<string:role_name>', methods=['DELETE'])
@token_required
@role_required(['admin']) # Sadece adminler rol kaldırabilir
def remove_role_from_user(user_id, role_name):
    user = User.query.get_or_404(user_id)
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        return jsonify({'message': f"Rol '{role_name}' bulunamadı."}), 404

    if not user.has_role(role_name):
        return jsonify({'message': f"Kullanıcının '{role_name}' rolü zaten yok."}), 404

    user.roles.remove(role)
    db.session.commit()
    return jsonify({'message': f"'{role_name}' rolü kullanıcıdan başarıyla kaldırıldı.", 'user': user.to_dict()}), 200


# --- Rol Yönetimi Rotaları ---
@auth_bp.route('/roles', methods=['POST'])
@token_required
@role_required(['admin'])
def create_role():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'message': 'Eksik bilgi: name (rol adı) zorunludur'}), 400

    if Role.query.filter_by(name=data['name']).first():
        return jsonify({'message': 'Bu rol adı zaten mevcut'}), 409

    new_role = Role(name=data['name'], description=data.get('description'))
    db.session.add(new_role)
    db.session.commit()
    return jsonify({'message': 'Rol başarıyla oluşturuldu', 'role': new_role.to_dict()}), 201

@auth_bp.route('/roles', methods=['GET'])
@token_required
@role_required(['admin', 'user']) # Rolleri listelemek için daha geniş yetki
def get_all_roles():
    roles = Role.query.all()
    return jsonify([role.to_dict() for role in roles]), 200

@auth_bp.route('/roles/<int:role_id>', methods=['PUT'])
@token_required
@role_required(['admin'])
def update_role(role_id):
    role = Role.query.get_or_404(role_id)
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Güncellenecek veri yok'}),400

    new_name = data.get('name')
    if new_name and new_name != role.name:
        if Role.query.filter_by(name=new_name).first():
            return jsonify({'message': 'Bu rol adı zaten mevcut'}), 409
        role.name = new_name

    role.description = data.get('description', role.description)
    db.session.commit()
    return jsonify({'message': 'Rol güncellendi', 'role': role.to_dict()}), 200


@auth_bp.route('/roles/<int:role_id>', methods=['DELETE'])
@token_required
@role_required(['admin'])
def delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    # Rol silinirken bu role sahip kullanıcılar ne olacak?
    # SQLAlchemy otomatik olarak user_roles tablosundan ilişkili kayıtları siler.
    # Ama eğer bir rolün silinmesini engellemek isterseniz (örn: 'admin' rolü) kontrol ekleyebilirsiniz.
    if role.name in ['admin', 'user']: # Temel rollerin silinmesini engelle
         return jsonify({'message': f"Temel rol '{role.name}' silinemez."}), 403
    if role.users: # Eğer role atanmış kullanıcılar varsa (ilişki üzerinden kontrol)
        return jsonify({'message': f"Bu rol ('{role.name}') bazı kullanıcılara atanmış durumda. Önce kullanıcıların rollerini değiştirin."}), 400

    db.session.delete(role)
    db.session.commit()
    return jsonify({'message': 'Rol başarıyla silindi'}), 200


@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user_profile():
    # g.current_user token_required decorator'ü tarafından atanır
    return jsonify(g.current_user.to_dict()), 200
