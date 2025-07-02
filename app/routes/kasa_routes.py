from flask import request, jsonify, g
from app import db
from app.models.kasa import Kasa, KasaHareketi
from app.models.auth import User
from . import kasa_bp
from app.utils.decorators import token_required, role_required # Güncellendi
from decimal import Decimal
from datetime import datetime

# Yardımcı Fonksiyon: Kasa Hareketi Ekleme ve Bakiye Güncelleme
def add_kasa_hareketi(kasa_id, tutar, islem_tipi, aciklama=None, referans_tablo=None, referans_id=None, user_id=None, commit_session=True):
    """
    Verilen kasa için bir hareket oluşturur ve kasanın bakiyesini günceller.
    Tutar pozitif ise gelir, negatif ise gider olarak işlenir.
    """
    kasa = Kasa.query.get(kasa_id)
    if not kasa:
        raise ValueError(f"Kasa bulunamadı: ID {kasa_id}")

    tutar_decimal = Decimal(tutar)

    # Giderse ve bakiye yetersizse kontrol (opsiyonel, bazı durumlarda eksiye düşebilir)
    # if tutar_decimal < 0 and kasa.bakiye < abs(tutar_decimal):
    #     raise ValueError(f"Yetersiz kasa bakiyesi. Kasa: {kasa.kasa_adi}, Bakiye: {kasa.bakiye}, İstenen Gider: {abs(tutar_decimal)}")

    hareket = KasaHareketi(
        kasa_id=kasa_id,
        tutar=tutar_decimal,
        islem_tipi=islem_tipi,
        aciklama=aciklama,
        referans_tablo=referans_tablo,
        referans_id=referans_id,
        user_id=user_id, # İşlemi yapan kullanıcı
        tarih=datetime.utcnow()
    )
    db.session.add(hareket)

    # Kasa bakiyesini güncelle
    kasa.bakiye += tutar_decimal
    db.session.add(kasa)

    if commit_session:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e # Hatayı yukarıya fırlat
    else:
        # Eğer commit_session False ise, çağıran fonksiyonun commit etmesi beklenir.
        # Bu, birden fazla DB işlemini tek bir transaction'da yapmak için kullanışlıdır.
        db.session.flush() # ID'lerin atanması için flush edilebilir.

    return hareket


@kasa_bp.route('', methods=['POST'])
@token_required
def create_kasa():
    data = request.get_json()
    if not data or not data.get('kasa_adi') or not data.get('para_birimi'):
        return jsonify({'message': 'Eksik bilgi: kasa_adi ve para_birimi zorunludur'}), 400

    if Kasa.query.filter_by(kasa_adi=data['kasa_adi']).first():
        return jsonify({'message': 'Bu kasa adı zaten mevcut'}), 409 # Conflict

    yeni_kasa = Kasa(
        kasa_adi=data['kasa_adi'],
        para_birimi=data['para_birimi'].upper(),
        bakiye=data.get('bakiye', 0.00)
    )
    # Başlangıç bakiyesi için bir hareket eklenebilir (opsiyonel)
    # initial_bakiye = data.get('bakiye', 0.00)
    # if Decimal(initial_bakiye) != 0:
    #     try:
    #         # Kasa commit edildikten sonra ID alır, bu yüzden önce kasa oluşturulmalı.
    #         # Veya flush kullanılabilir. Şimdilik manuel hareketle eklensin.
    #         pass
    #     except Exception as e:
    #         db.session.rollback()
    #         return jsonify({'message': f'Başlangıç bakiyesi hareketi eklenirken hata: {str(e)}'}), 500

    db.session.add(yeni_kasa)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Kasa oluşturulurken hata: {str(e)}'}), 500
    return jsonify(yeni_kasa.to_dict()), 201

@kasa_bp.route('', methods=['GET'])
@token_required
def get_kasalar():
    kasalar = Kasa.query.order_by(Kasa.kasa_adi).all()
    return jsonify([kasa.to_dict() for kasa in kasalar]), 200

@kasa_bp.route('/<int:kasa_id>', methods=['GET'])
@token_required
def get_kasa_by_id(kasa_id):
    kasa = Kasa.query.get_or_404(kasa_id)
    return jsonify(kasa.to_dict()), 200

@kasa_bp.route('/<int:kasa_id>/hareketler', methods=['GET'])
@token_required
def get_kasa_hareketleri(kasa_id):
    Kasa.query.get_or_404(kasa_id) # Kasanın varlığını kontrol et

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    hareketler = KasaHareketi.query.filter_by(kasa_id=kasa_id)\
        .order_by(KasaHareketi.tarih.desc(), KasaHareketi.id.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'hareketler': [h.to_dict() for h in hareketler.items],
        'total': hareketler.total,
        'page': hareketler.page,
        'per_page': hareketler.per_page,
        'total_pages': hareketler.pages
    }), 200


@kasa_bp.route('/<int:kasa_id>/hareketler', methods=['POST'])
@token_required
# @role_required(['admin', 'editor']) # veya daha spesifik bir rol
def create_manuel_kasa_hareketi(kasa_id):
    """Manuel olarak kasaya gelir veya gider hareketi ekler."""
    data = request.get_json()
    if not data or not data.get('tutar') or not data.get('islem_tipi'):
        return jsonify({'message': 'Eksik bilgi: tutar ve islem_tipi zorunludur'}), 400

    try:
        tutar_decimal = Decimal(data['tutar']) # Pozitif (gelir) veya negatif (gider) olabilir
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz tutar formatı'}), 400

    islem_tipi = data['islem_tipi']
    aciklama = data.get('aciklama', f"Manuel {islem_tipi}")

    # Güvenlik: Kullanıcının doğrudan "Kurban Bağışı" gibi sistem tiplerini manuel girmesini engelle
    # Veya belirli manuel işlem tipleri tanımlanabilir: "Manuel Gelir", "Manuel Gider"
    # if islem_tipi not in ["Manuel Gelir", "Manuel Gider", "Açılış Fişi", "Devir Fişi"]:
    #    return jsonify({'message': 'Geçersiz manuel işlem tipi.'}), 400

    try:
        hareket = add_kasa_hareketi(
            kasa_id=kasa_id,
            tutar=tutar_decimal,
            islem_tipi=islem_tipi,
            aciklama=aciklama,
            user_id=g.current_user.id, # İşlemi yapan kullanıcı
            commit_session=True # Bu fonksiyon kendi commit'ini yapsın
        )
        return jsonify(hareket.to_dict()), 201
    except ValueError as ve: # Kasa bulunamadı veya bakiye yetersiz gibi
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        # db.session.rollback() # add_kasa_hareketi içinde rollback var
        return jsonify({'message': f'Kasa hareketi oluşturulurken hata: {str(e)}'}), 500


@kasa_bp.route('/<int:kasa_id>', methods=['PUT'])
@token_required
# @role_required(['admin'])
def update_kasa(kasa_id):
    kasa = Kasa.query.get_or_404(kasa_id)
    data = request.get_json()

    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    new_kasa_adi = data.get('kasa_adi')
    if new_kasa_adi and new_kasa_adi != kasa.kasa_adi:
        if Kasa.query.filter_by(kasa_adi=new_kasa_adi).first():
            return jsonify({'message': 'Bu kasa adı zaten mevcut'}), 409
        kasa.kasa_adi = new_kasa_adi

    # Para birimi değişikliği, eğer kasada hareket varsa dikkatli yapılmalı veya engellenmeli.
    # Şimdilik, eğer hareket yoksa izin verelim.
    new_para_birimi = data.get('para_birimi')
    if new_para_birimi and new_para_birimi.upper() != kasa.para_birimi:
        if kasa.hareketler.count() > 0:
            return jsonify({'message': 'Kasada hareket bulunduğu için para birimi değiştirilemez.'}), 400
        kasa.para_birimi = new_para_birimi.upper()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Kasa güncellenirken hata: {str(e)}'}), 500
    return jsonify(kasa.to_dict()), 200

@kasa_bp.route('/<int:kasa_id>', methods=['DELETE'])
@token_required
# @role_required(['admin'])
def delete_kasa(kasa_id):
    kasa = Kasa.query.get_or_404(kasa_id)

    if kasa.hareketler.count() > 0:
        return jsonify({'message': 'Kasada hareket bulunduğu için silinemez. Önce hareketleri silin veya kasayı pasif duruma getirin.'}), 400

    # Eğer kasa başka modellerle ilişkiliyse (örn: KurbanBagisi.gelir_kasa_id) bu ilişkiler de kontrol edilmeli.
    # Örneğin, KurbanBagisi'nde bu kasa kullanılmışsa silinmemeli.
    # Bu kontroller ilgili modellerin ForeignKey tanımlarında ondelete='RESTRICT' ile de sağlanabilir.
    # from app.models.kurban import KurbanBagisi
    # if KurbanBagisi.query.filter((KurbanBagisi.gelir_kasa_id == kasa_id) | (KurbanBagisi.kesim_masraf_kasa_id == kasa_id)).first():
    #    return jsonify({'message': 'Bu kasa kurban bağışlarında kullanıldığı için silinemez.'}), 400
    # Benzer kontroller İş Avansı vb. için de eklenebilir.

    db.session.delete(kasa)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Kasa silinirken hata: {str(e)}'}), 500
    return jsonify({'message': 'Kasa başarıyla silindi'}), 200
