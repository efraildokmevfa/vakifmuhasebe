from flask import request, jsonify, g
from app import db
from app.models.cari_hesap import CariHesap, CariHesapHareketi
from app.models.auth import User
from . import cari_hesap_bp
from app.utils.decorators import token_required, role_required # Güncellendi
from decimal import Decimal
from datetime import datetime

# Yardımcı Fonksiyon: Cari Hesap Hareketi Ekleme ve Bakiye Güncelleme
def add_cari_hesap_hareketi(cari_hesap_id, tutar, islem_tipi, aciklama=None, referans_tablo=None, referans_id=None, user_id=None, commit_session=True):
    """
    Verilen cari hesap için bir hareket oluşturur ve cari hesabın bakiyesini günceller.
    Tutar: Pozitif ise cari borçlanır (bizim alacağımız artar), Negatif ise cari alacaklanır (bizim borcumuz artar).
    """
    cari_hesap = CariHesap.query.get(cari_hesap_id)
    if not cari_hesap:
        raise ValueError(f"Cari hesap bulunamadı: ID {cari_hesap_id}")

    tutar_decimal = Decimal(tutar)

    hareket = CariHesapHareketi(
        cari_hesap_id=cari_hesap_id,
        tutar=tutar_decimal, # Pozitif: Borç, Negatif: Alacak
        islem_tipi=islem_tipi,
        aciklama=aciklama,
        referans_tablo=referans_tablo,
        referans_id=referans_id,
        user_id=user_id,
        tarih=datetime.utcnow()
    )
    db.session.add(hareket)

    # Cari hesap bakiyesini güncelle
    # Bakiye: Pozitif ise cari bize borçlu, Negatif ise biz cariye borçluyuz.
    # Eğer hareket tutarı pozitif (cari borçlandı) ise bakiye artar.
    # Eğer hareket tutarı negatif (cari alacaklandı) ise bakiye azalır.
    cari_hesap.bakiye += tutar_decimal
    db.session.add(cari_hesap)

    if commit_session:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
    else:
        db.session.flush()

    return hareket


@cari_hesap_bp.route('', methods=['POST'])
@token_required
def create_cari_hesap():
    data = request.get_json()
    if not data or not data.get('hesap_adi') or not data.get('hesap_turu') or not data.get('para_birimi'):
        return jsonify({'message': 'Eksik bilgi: hesap_adi, hesap_turu ve para_birimi zorunludur'}), 400

    # Aynı isimde cari hesap kontrolü (opsiyonel, iş mantığına göre)
    # if CariHesap.query.filter_by(hesap_adi=data['hesap_adi']).first():
    #     return jsonify({'message': 'Bu hesap adı zaten mevcut'}), 409

    yeni_cari_hesap = CariHesap(
        hesap_adi=data['hesap_adi'],
        hesap_turu=data['hesap_turu'],
        para_birimi=data['para_birimi'].upper(),
        bakiye=data.get('bakiye', 0.00),
        vergi_no=data.get('vergi_no'),
        adres=data.get('adres'),
        telefon=data.get('telefon'),
        email=data.get('email'),
        aktif=data.get('aktif', True)
    )
    # Açılış bakiyesi için hareket eklenebilir (opsiyonel)
    # initial_bakiye_str = data.get('bakiye', '0.00')
    # initial_bakiye = Decimal(initial_bakiye_str)
    # if initial_bakiye != 0:
    #     # Önce cari_hesap commit edilmeli ki ID alsın.
    #     # Veya add_cari_hesap_hareketi içinde commit_session=False kullanılır.
    #     pass

    db.session.add(yeni_cari_hesap)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Cari hesap oluşturulurken hata: {str(e)}'}), 500
    return jsonify(yeni_cari_hesap.to_dict()), 201

@cari_hesap_bp.route('', methods=['GET'])
@token_required
def get_cari_hesaplar():
    # Filtreleme parametreleri (örneğin ?aktif=true&hesap_turu=Personel)
    aktif_filter = request.args.get('aktif')
    hesap_turu_filter = request.args.get('hesap_turu')

    query = CariHesap.query

    if aktif_filter is not None:
        query = query.filter(CariHesap.aktif == (aktif_filter.lower() == 'true'))
    if hesap_turu_filter:
        query = query.filter(CariHesap.hesap_turu == hesap_turu_filter)
    if hesap_turu_filter:
        query = query.filter(CariHesap.hesap_turu == hesap_turu_filter)

    cari_hesaplar = query.order_by(CariHesap.hesap_adi).all()
    return jsonify([ch.to_dict() for ch in cari_hesaplar]), 200

@cari_hesap_bp.route('/<int:cari_id>', methods=['GET'])
@token_required
def get_cari_hesap_by_id(cari_id):
    cari_hesap = CariHesap.query.get_or_404(cari_id)
    return jsonify(cari_hesap.to_dict()), 200

@cari_hesap_bp.route('/<int:cari_id>/hareketler', methods=['GET'])
@token_required
def get_cari_hesap_hareketleri(cari_id):
    CariHesap.query.get_or_404(cari_id) # Cari hesabın varlığını kontrol et

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    hareketler = CariHesapHareketi.query.filter_by(cari_hesap_id=cari_id)\
        .order_by(CariHesapHareketi.tarih.desc(), CariHesapHareketi.id.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'hareketler': [h.to_dict() for h in hareketler.items],
        'total': hareketler.total,
        'page': hareketler.page,
        'per_page': hareketler.per_page,
        'total_pages': hareketler.pages
    }), 200

@cari_hesap_bp.route('/<int:cari_id>/hareketler', methods=['POST'])
@token_required
# @role_required(['admin', 'editor'])
def create_manuel_cari_hesap_hareketi(cari_id):
    """Manuel olarak cari hesaba borç veya alacak hareketi ekler."""
    data = request.get_json()
    if not data or not data.get('tutar') or not data.get('islem_tipi'):
        return jsonify({'message': 'Eksik bilgi: tutar ve islem_tipi zorunludur'}), 400

    try:
        # Pozitif tutar cariyi borçlandırır, negatif tutar alacaklandırır.
        tutar_decimal = Decimal(data['tutar'])
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz tutar formatı'}), 400

    islem_tipi = data['islem_tipi'] # Örn: "Manuel Borç Kaydı", "Manuel Alacak Kaydı"
    aciklama = data.get('aciklama', f"Manuel {islem_tipi}")

    # if islem_tipi not in ["Manuel Borç", "Manuel Alacak", "Açılış Fişi Borç", "Açılış Fişi Alacak"]:
    #    return jsonify({'message': 'Geçersiz manuel işlem tipi.'}), 400

    try:
        hareket = add_cari_hesap_hareketi(
            cari_hesap_id=cari_id,
            tutar=tutar_decimal,
            islem_tipi=islem_tipi,
            aciklama=aciklama,
            user_id=g.current_user.id,
            commit_session=True
        )
        return jsonify(hareket.to_dict()), 201
    except ValueError as ve:
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        return jsonify({'message': f'Cari hesap hareketi oluşturulurken hata: {str(e)}'}), 500


@cari_hesap_bp.route('/<int:cari_id>', methods=['PUT'])
@token_required
# @role_required(['admin', 'editor'])
def update_cari_hesap(cari_id):
    cari_hesap = CariHesap.query.get_or_404(cari_id)
    data = request.get_json()

    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    cari_hesap.hesap_adi = data.get('hesap_adi', cari_hesap.hesap_adi)
    cari_hesap.hesap_turu = data.get('hesap_turu', cari_hesap.hesap_turu)

    # Para birimi değişikliği, eğer cari hesapta hareket varsa dikkatli yapılmalı veya engellenmeli.
    new_para_birimi = data.get('para_birimi')
    if new_para_birimi and new_para_birimi.upper() != cari_hesap.para_birimi:
        if cari_hesap.hareketler.count() > 0:
            return jsonify({'message': 'Cari hesapta hareket bulunduğu için para birimi değiştirilemez.'}), 400
        cari_hesap.para_birimi = new_para_birimi.upper()

    cari_hesap.vergi_no = data.get('vergi_no', cari_hesap.vergi_no)
    cari_hesap.adres = data.get('adres', cari_hesap.adres)
    cari_hesap.telefon = data.get('telefon', cari_hesap.telefon)
    cari_hesap.email = data.get('email', cari_hesap.email)
    cari_hesap.aktif = data.get('aktif', cari_hesap.aktif)
    # Bakiye doğrudan güncellenmez.

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Cari hesap güncellenirken hata: {str(e)}'}), 500
    return jsonify(cari_hesap.to_dict()), 200

@cari_hesap_bp.route('/<int:cari_id>', methods=['DELETE'])
@token_required
# @role_required(['admin'])
def delete_cari_hesap(cari_id):
    cari_hesap = CariHesap.query.get_or_404(cari_id)

    if cari_hesap.hareketler.count() > 0:
       return jsonify({'message': 'Cari hesapta hareket bulunduğu için silinemez. Önce hareketleri silin veya hesabı pasif duruma getirin.'}), 400

    # Personel ile bağlantı kontrolü
    from app.models.personel import Personel
    if Personel.query.filter_by(cari_hesap_id=cari_id).first():
       return jsonify({'message': 'Bu cari hesap bir personele bağlı olduğu için silinemez. Önce personel kaydındaki cari hesap bağlantısını kaldırın.'}), 400

    # Diğer modüllerle potansiyel bağlantılar da burada kontrol edilebilir (örn: KurbanBagisi)

    db.session.delete(cari_hesap)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Cari hesap silinirken hata: {str(e)}'}), 500
    return jsonify({'message': 'Cari hesap başarıyla silindi'}), 200
