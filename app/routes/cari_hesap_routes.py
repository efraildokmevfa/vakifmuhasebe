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
    CariHesap.query.get_or_404(cari_id)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    tarih_baslangic_str = request.args.get('tarih_baslangic')
    tarih_bitis_str = request.args.get('tarih_bitis')
    sirala_alan = request.args.get('sirala_alan', 'tarih')
    sirala_yon = request.args.get('sirala_yon', 'desc')

    islem_tipi_filter = request.args.get('islem_tipi')
    referans_tablo_filter = request.args.get('referans_tablo')
    referans_id_filter = request.args.get('referans_id', type=int)
    user_id_filter = request.args.get('user_id', type=int)

    query = CariHesapHareketi.query.filter_by(cari_hesap_id=cari_id)

    if tarih_baslangic_str:
        try:
            tarih_baslangic = datetime.fromisoformat(tarih_baslangic_str)
            query = query.filter(CariHesapHareketi.tarih >= tarih_baslangic)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_baslangic formatı.'}), 400
    if tarih_bitis_str:
        try:
            tarih_bitis = datetime.fromisoformat(tarih_bitis_str).replace(hour=23, minute=59, second=59)
            query = query.filter(CariHesapHareketi.tarih <= tarih_bitis)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_bitis formatı.'}), 400

    if islem_tipi_filter:
        query = query.filter(CariHesapHareketi.islem_tipi.ilike(f"%{islem_tipi_filter}%"))
    if referans_tablo_filter:
        query = query.filter(CariHesapHareketi.referans_tablo == referans_tablo_filter)
    if referans_id_filter:
        query = query.filter(CariHesapHareketi.referans_id == referans_id_filter)
    if user_id_filter:
        query = query.filter(CariHesapHareketi.user_id == user_id_filter)

    valid_sort_fields = {
        'tarih': CariHesapHareketi.tarih,
        'tutar': CariHesapHareketi.tutar,
        'islem_tipi': CariHesapHareketi.islem_tipi,
        'id': CariHesapHareketi.id
    }
    sort_column = valid_sort_fields.get(sirala_alan, CariHesapHareketi.tarih)
    if sirala_yon == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc(), CariHesapHareketi.id.desc())

    paginated_hareketler = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'hareketler': [h.to_dict() for h in paginated_hareketler.items],
        'total': paginated_hareketler.total,
        'page': paginated_hareketler.page,
        'per_page': paginated_hareketler.per_page,
        'total_pages': paginated_hareketler.pages
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


# --- Mütevelli Özel İşlemleri ---
@cari_hesap_bp.route('/mutevelli/<int:mutevelli_cari_id>/vakfa-aktarim', methods=['POST'])
@token_required
# @role_required(['admin', 'accountant']) # Gerekli rolleri belirleyin
def mutevelli_vakfa_aktarim(mutevelli_cari_id):
    data = request.get_json()
    required_fields = ['tutar', 'para_birimi', 'hedef_kasa_id']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'Eksik bilgi: {field} zorunludur.'}), 400

    try:
        tutar = Decimal(data['tutar'])
        if tutar <= 0: raise ValueError("Tutar pozitif olmalı.")
        hedef_kasa_id = int(data['hedef_kasa_id'])
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz tutar veya kasa ID formatı.'}), 400

    mutevelli_cari = CariHesap.query.get_or_404(mutevelli_cari_id)
    if mutevelli_cari.hesap_turu != "Mütevelli":
        return jsonify({'message': 'Bu işlem sadece Mütevelli tipindeki cari hesaplar için geçerlidir.'}), 400

    hedef_kasa = Kasa.query.get(hedef_kasa_id)
    if not hedef_kasa:
        return jsonify({'message': 'Hedef kasa bulunamadı.'}), 404

    para_birimi = data['para_birimi'].upper()
    if mutevelli_cari.para_birimi != para_birimi or hedef_kasa.para_birimi != para_birimi:
        return jsonify({'message': 'Para birimleri uyuşmuyor (Mütevelli Cari, Hedef Kasa, İşlem Tutarı).'}), 400

    aciklama = data.get('aciklama', f"{mutevelli_cari.hesap_adi} adlı mütevelliden vakfa para aktarımı.")

    try:
        # 1. Mütevelli cari hesabına alacak kaydı (borcu azalır)
        add_cari_hesap_hareketi(
            cari_hesap_id=mutevelli_cari_id,
            tutar=-tutar, # Alacaklandığı için negatif
            islem_tipi="Mütevelli Vakfa Para Aktarımı",
            aciklama=aciklama,
            referans_tablo='kasalar', # Hedef kasaya referans
            referans_id=hedef_kasa.id,
            user_id=g.current_user.id,
            commit_session=False
        )
        # 2. Hedef kasaya gelir kaydı
        from app.routes.kasa_routes import add_kasa_hareketi
        add_kasa_hareketi(
            kasa_id=hedef_kasa.id,
            tutar=tutar, # Gelir
            islem_tipi="Mütevelliden Para Aktarımı",
            aciklama=aciklama,
            referans_tablo='cari_hesaplar', # Kaynak mütevelli carisine referans
            referans_id=mutevelli_cari.id,
            user_id=g.current_user.id,
            commit_session=False
        )
        db.session.commit()
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Mütevelli aktarımı sırasında hata: {str(e)}'}), 500

    return jsonify({
        'message': 'Mütevelliden vakfa para aktarımı başarıyla kaydedildi.',
        'mutevelli_cari_bakiye': str(mutevelli_cari.bakiye),
        'hedef_kasa_bakiye': str(hedef_kasa.bakiye)
    }), 200


@cari_hesap_bp.route('/mutevelli/<int:mutevelli_cari_id>/vakiftan-odeme', methods=['POST'])
@token_required
# @role_required(['admin', 'accountant'])
def mutevelli_vakiftan_odeme(mutevelli_cari_id):
    data = request.get_json()
    required_fields = ['tutar', 'para_birimi', 'kaynak_kasa_id']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'Eksik bilgi: {field} zorunludur.'}), 400

    try:
        tutar = Decimal(data['tutar'])
        if tutar <= 0: raise ValueError("Tutar pozitif olmalı.")
        kaynak_kasa_id = int(data['kaynak_kasa_id'])
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz tutar veya kasa ID formatı.'}), 400

    mutevelli_cari = CariHesap.query.get_or_404(mutevelli_cari_id)
    if mutevelli_cari.hesap_turu != "Mütevelli":
        return jsonify({'message': 'Bu işlem sadece Mütevelli tipindeki cari hesaplar için geçerlidir.'}), 400

    kaynak_kasa = Kasa.query.get(kaynak_kasa_id)
    if not kaynak_kasa:
        return jsonify({'message': 'Kaynak kasa bulunamadı.'}), 404

    para_birimi = data['para_birimi'].upper()
    if mutevelli_cari.para_birimi != para_birimi or kaynak_kasa.para_birimi != para_birimi:
        return jsonify({'message': 'Para birimleri uyuşmuyor (Mütevelli Cari, Kaynak Kasa, İşlem Tutarı).'}), 400

    if kaynak_kasa.bakiye < tutar:
        return jsonify({'message': f'Kaynak kasada ({kaynak_kasa.kasa_adi}) yeterli bakiye yok.'}), 400

    aciklama = data.get('aciklama', f"{mutevelli_cari.hesap_adi} adlı mütevelliye vakıftan ödeme.")

    try:
        # 1. Mütevelli cari hesabına borç kaydı (alacağı azalır/borcu artar)
        add_cari_hesap_hareketi(
            cari_hesap_id=mutevelli_cari_id,
            tutar=tutar, # Borçlandığı için pozitif
            islem_tipi="Vakıftan Mütevelliye Ödeme",
            aciklama=aciklama,
            referans_tablo='kasalar', # Kaynak kasaya referans
            referans_id=kaynak_kasa.id,
            user_id=g.current_user.id,
            commit_session=False
        )
        # 2. Kaynak kasadan gider kaydı
        from app.routes.kasa_routes import add_kasa_hareketi
        add_kasa_hareketi(
            kasa_id=kaynak_kasa.id,
            tutar=-tutar, # Gider
            islem_tipi="Mütevelliye Ödeme",
            aciklama=aciklama,
            referans_tablo='cari_hesaplar', # Hedef mütevelli carisine referans
            referans_id=mutevelli_cari.id,
            user_id=g.current_user.id,
            commit_session=False
        )
        db.session.commit()
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Mütevelliye ödeme sırasında hata: {str(e)}'}), 500

    return jsonify({
        'message': 'Vakıftan mütevelliye ödeme başarıyla kaydedildi.',
        'mutevelli_cari_bakiye': str(mutevelli_cari.bakiye),
        'kaynak_kasa_bakiye': str(kaynak_kasa.bakiye)
    }), 200
