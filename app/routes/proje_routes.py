from flask import request, jsonify, g
from app import db
from app.models.proje import Proje, ProjeTuru, ProjeHarcamasi
from app.models.kasa import Kasa
from app.routes.kasa_routes import add_kasa_hareketi
from . import proje_bp
from app.utils.decorators import token_required, role_required # Güncellendi
from datetime import datetime
from decimal import Decimal

# --- Proje Türü Rotaları ---
@proje_bp.route('/turler', methods=['POST'])
@token_required
# @role_required(['admin', 'project_manager'])
def create_proje_turu():
    data = request.get_json()
    if not data or not data.get('tur_adi'):
        return jsonify({'message': 'Eksik bilgi: tur_adi zorunludur'}), 400

    if ProjeTuru.query.filter_by(tur_adi=data['tur_adi']).first():
        return jsonify({'message': 'Bu proje türü zaten mevcut'}), 409

    yeni_tur = ProjeTuru(
        tur_adi=data['tur_adi'],
        aciklama=data.get('aciklama')
    )
    db.session.add(yeni_tur)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje türü oluşturulurken hata: {str(e)}'}), 500
    return jsonify(yeni_tur.to_dict()), 201

@proje_bp.route('/turler', methods=['GET'])
@token_required
def get_proje_turleri():
    turler = ProjeTuru.query.order_by(ProjeTuru.tur_adi).all()
    return jsonify([tur.to_dict() for tur in turler]), 200

@proje_bp.route('/turler/<int:tur_id>', methods=['GET'])
@token_required
def get_proje_turu_by_id(tur_id):
    tur = ProjeTuru.query.get_or_404(tur_id)
    return jsonify(tur.to_dict()), 200

@proje_bp.route('/turler/<int:tur_id>', methods=['PUT'])
@token_required
# @role_required(['admin', 'project_manager'])
def update_proje_turu(tur_id):
    tur = ProjeTuru.query.get_or_404(tur_id)
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    new_tur_adi = data.get('tur_adi')
    if new_tur_adi and new_tur_adi != tur.tur_adi:
        if ProjeTuru.query.filter_by(tur_adi=new_tur_adi).first():
            return jsonify({'message': 'Bu proje türü adı zaten mevcut'}), 409
        tur.tur_adi = new_tur_adi

    tur.aciklama = data.get('aciklama', tur.aciklama)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje türü güncellenirken hata: {str(e)}'}), 500
    return jsonify(tur.to_dict()), 200

@proje_bp.route('/turler/<int:tur_id>', methods=['DELETE'])
@token_required
# @role_required(['admin'])
def delete_proje_turu(tur_id):
    tur = ProjeTuru.query.get_or_404(tur_id)
    if tur.projeler.count() > 0: # Eğer bu türe atanmış projeler varsa silme
        return jsonify({'message': 'Bu proje türüne atanmış projeler bulunduğu için silinemez.'}), 400
    db.session.delete(tur)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje türü silinirken hata: {str(e)}'}), 500
    return jsonify({'message': 'Proje türü başarıyla silindi'}), 200


# --- Proje Rotaları (Güncellenmiş) ---
@proje_bp.route('', methods=['POST'])
@token_required
# @role_required(['admin', 'project_manager'])
def create_proje():
    data = request.get_json()
    if not data or not data.get('proje_adi'):
        return jsonify({'message': 'Eksik bilgi: proje_adi zorunludur'}), 400

    if Proje.query.filter_by(proje_adi=data['proje_adi']).first():
        return jsonify({'message': 'Bu proje adı zaten mevcut'}), 409

    yeni_proje = Proje(
        proje_adi=data['proje_adi'],
        proje_aciklamasi=data.get('proje_aciklamasi'),
        durum=data.get('durum', 'Planlandı'),
        proje_turu_id=data.get('proje_turu_id')
    )

    if data.get('proje_turu_id') and not ProjeTuru.query.get(data.get('proje_turu_id')):
        return jsonify({'message': 'Geçersiz proje_turu_id.'}), 400

    if data.get('baslangic_tarihi'):
        try:
            yeni_proje.baslangic_tarihi = datetime.fromisoformat(data['baslangic_tarihi'].split('T')[0]).date()
        except ValueError:
            return jsonify({'message': 'Geçersiz başlangıç tarihi formatı. YYYY-MM-DD kullanın.'}), 400

    if data.get('bitis_tarihi'):
        try:
            yeni_proje.bitis_tarihi = datetime.fromisoformat(data['bitis_tarihi'].split('T')[0]).date()
        except ValueError:
            return jsonify({'message': 'Geçersiz bitiş tarihi formatı. YYYY-MM-DD kullanın.'}), 400

    if data.get('proje_butcesi') is not None:
        try:
            yeni_proje.proje_butcesi = Decimal(data['proje_butcesi'])
        except (ValueError, TypeError):
            return jsonify({'message': 'Geçersiz bütçe formatı. Sayısal bir değer olmalı.'}), 400

    db.session.add(yeni_proje)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje oluşturulurken hata: {str(e)}'}), 500
    return jsonify(yeni_proje.to_dict()), 201

@proje_bp.route('', methods=['GET'])
@token_required
def get_projeler():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    tarih_baslangic_str = request.args.get('tarih_baslangic') # Proje başlangıç tarihi için
    tarih_bitis_str = request.args.get('tarih_bitis') # Proje başlangıç tarihi için
    sirala_alan = request.args.get('sirala_alan', 'baslangic_tarihi')
    sirala_yon = request.args.get('sirala_yon', 'desc')

    durum_filter = request.args.get('durum')
    proje_turu_id_filter = request.args.get('proje_turu_id', type=int)
    proje_adi_filter = request.args.get('proje_adi') # Proje adına göre arama

    query = Proje.query

    if tarih_baslangic_str:
        try:
            tarih_baslangic = datetime.fromisoformat(tarih_baslangic_str).date()
            query = query.filter(Proje.baslangic_tarihi >= tarih_baslangic)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_baslangic formatı. YYYY-MM-DD kullanın.'}), 400
    if tarih_bitis_str: # Bu bitiş tarihi, projenin başlangıç tarihinin bitiş aralığı mı, yoksa projenin bitiş tarihinin mi?
                        # Şimdilik başlangıç tarihi için üst sınır olarak alalım.
        try:
            tarih_bitis = datetime.fromisoformat(tarih_bitis_str).date()
            query = query.filter(Proje.baslangic_tarihi <= tarih_bitis)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_bitis formatı. YYYY-MM-DD kullanın.'}), 400

    if durum_filter:
        query = query.filter(Proje.durum == durum_filter)
    if proje_turu_id_filter:
        query = query.filter(Proje.proje_turu_id == proje_turu_id_filter)
    if proje_adi_filter:
        query = query.filter(Proje.proje_adi.ilike(f"%{proje_adi_filter}%"))

    valid_sort_fields = {
        'baslangic_tarihi': Proje.baslangic_tarihi,
        'proje_adi': Proje.proje_adi,
        'durum': Proje.durum,
        'proje_butcesi': Proje.proje_butcesi,
        'id': Proje.id
    }
    sort_column = valid_sort_fields.get(sirala_alan, Proje.baslangic_tarihi)

    if sirala_yon == 'asc':
        # Nullable alanlarda nullsfirst() veya nullslast() eklenebilir.
        query = query.order_by(sort_column.asc().nullslast()) if sort_column is Proje.baslangic_tarihi else query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc().nullslast()) if sort_column is Proje.baslangic_tarihi else query.order_by(sort_column.desc())

    paginated_projeler = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'projeler': [p.to_dict() for p in paginated_projeler.items],
        'total': paginated_projeler.total,
        'page': paginated_projeler.page,
        'per_page': paginated_projeler.per_page,
        'total_pages': paginated_projeler.pages
    }), 200

@proje_bp.route('/<int:proje_id>', methods=['GET'])
@token_required
def get_proje_by_id(proje_id):
    proje = Proje.query.get_or_404(proje_id)
    return jsonify(proje.to_dict()), 200

@proje_bp.route('/<int:proje_id>', methods=['PUT'])
@token_required
# @role_required(['admin', 'project_manager'])
def update_proje(proje_id):
    proje = Proje.query.get_or_404(proje_id)
    data = request.get_json()

    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    if 'proje_adi' in data and data['proje_adi'] != proje.proje_adi:
        if Proje.query.filter_by(proje_adi=data['proje_adi']).first():
            return jsonify({'message': 'Bu proje adı zaten mevcut'}), 409
        proje.proje_adi = data['proje_adi']

    proje.proje_aciklamasi = data.get('proje_aciklamasi', proje.proje_aciklamasi)
    proje.durum = data.get('durum', proje.durum)

    new_proje_turu_id = data.get('proje_turu_id')
    if new_proje_turu_id is not None: # 0 veya geçerli bir ID olabilir. Sadece null değilse kontrol et.
        if new_proje_turu_id == 0: # Proje türünü kaldırmak için
            proje.proje_turu_id = None
        elif not ProjeTuru.query.get(new_proje_turu_id):
            return jsonify({'message': 'Geçersiz proje_turu_id.'}), 400
        else:
            proje.proje_turu_id = new_proje_turu_id


    if data.get('baslangic_tarihi'):
        try:
            proje.baslangic_tarihi = datetime.fromisoformat(data['baslangic_tarihi'].split('T')[0]).date()
        except ValueError:
            return jsonify({'message': 'Geçersiz başlangıç tarihi formatı. YYYY-MM-DD kullanın.'}), 400

    if data.get('bitis_tarihi'):
        try:
            proje.bitis_tarihi = datetime.fromisoformat(data['bitis_tarihi'].split('T')[0]).date()
        except ValueError:
            return jsonify({'message': 'Geçersiz bitiş tarihi formatı. YYYY-MM-DD kullanın.'}), 400
    elif 'bitis_tarihi' in data and data['bitis_tarihi'] is None: # Bitiş tarihini null yapmak için
        proje.bitis_tarihi = None


    if data.get('proje_butcesi') is not None:
        try:
            proje.proje_butcesi = Decimal(data['proje_butcesi'])
        except (ValueError, TypeError):
            return jsonify({'message': 'Geçersiz bütçe formatı. Sayısal bir değer olmalı.'}), 400

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje güncellenirken hata: {str(e)}'}), 500
    return jsonify(proje.to_dict()), 200

@proje_bp.route('/<int:proje_id>', methods=['DELETE'])
@token_required
# @role_required(['admin'])
def delete_proje(proje_id):
    proje = Proje.query.get_or_404(proje_id)
    # Projeye ait harcamalar varsa, cascade delete ile otomatik silinecek (modelde tanımlı)
    # Veya burada manuel bir kontrol/uyarı eklenebilir.
    if proje.harcamalar.count() > 0:
         return jsonify({'message': 'Projeye ait harcamalar bulunduğu için silinemez. Önce harcamaları silin.'}), 400

    db.session.delete(proje)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje silinirken hata: {str(e)}'}), 500
    return jsonify({'message': 'Proje başarıyla silindi'}), 200


# --- Proje Harcaması Rotaları ---
@proje_bp.route('/<int:proje_id>/harcamalar', methods=['POST'])
@token_required
# @role_required(['admin', 'project_manager', 'editor'])
def create_proje_harcamasi(proje_id):
    proje = Proje.query.get_or_404(proje_id)
    data = request.get_json()

    required_fields = ['aciklama', 'tutar', 'para_birimi', 'odeme_kaynagi']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'Eksik bilgi: {field} zorunludur'}), 400

    odeme_kaynagi = data['odeme_kaynagi']
    kasa_id = data.get('kasa_id')
    mutevelli_cari_id = data.get('mutevelli_cari_id')

    if odeme_kaynagi == "Kasa" and not kasa_id:
        return jsonify({'message': 'Ödeme kaynağı Kasa ise kasa_id zorunludur.'}), 400
    if odeme_kaynagi == "Mütevelli" and not mutevelli_cari_id:
        return jsonify({'message': 'Ödeme kaynağı Mütevelli ise mutevelli_cari_id zorunludur.'}), 400
    if odeme_kaynagi not in ["Kasa", "Mütevelli"]:
        return jsonify({'message': 'Geçersiz odeme_kaynagi değeri.'}), 400

    try:
        tutar_decimal = Decimal(data['tutar'])
        if tutar_decimal <= 0:
            raise ValueError("Harcama tutarı pozitif olmalı.")
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz harcama tutarı.'}), 400

    kasa = None
    if odeme_kaynagi == "Kasa":
        kasa = Kasa.query.get(kasa_id)
        if not kasa:
            return jsonify({'message': 'Harcama kasası bulunamadı.'}), 404
        if kasa.para_birimi.upper() != data['para_birimi'].upper():
            return jsonify({'message': f'Harcama para birimi ({data["para_birimi"]}) ile kasa para birimi ({kasa.para_birimi}) uyuşmuyor.'}), 400
        if kasa.bakiye < tutar_decimal:
            return jsonify({'message': f'Harcama kasasında ({kasa.kasa_adi}) yeterli bakiye yok. Bakiye: {kasa.bakiye}'}), 400

    mutevelli_cari = None
    if odeme_kaynagi == "Mütevelli":
        from app.models.cari_hesap import CariHesap
        mutevelli_cari = CariHesap.query.get(mutevelli_cari_id)
        if not mutevelli_cari:
            return jsonify({'message': 'Mütevelli cari hesabı bulunamadı.'}), 404
        if mutevelli_cari.hesap_turu != "Mütevelli":
             return jsonify({'message': 'Belirtilen cari hesap bir mütevelli hesabı değil.'}), 400
        if mutevelli_cari.para_birimi.upper() != data['para_birimi'].upper():
            return jsonify({'message': f'Harcama para birimi ({data["para_birimi"]}) ile mütevelli cari para birimi ({mutevelli_cari.para_birimi}) uyuşmuyor.'}), 400


    yeni_harcama = ProjeHarcamasi(
        proje_id=proje_id,
        aciklama=data['aciklama'],
        tutar=tutar_decimal,
        para_birimi=data['para_birimi'].upper(),
        user_id=g.current_user.id,
        odeme_kaynagi=odeme_kaynagi,
        kasa_id=kasa_id if odeme_kaynagi == "Kasa" else None,
        mutevelli_cari_id=mutevelli_cari_id if odeme_kaynagi == "Mütevelli" else None
    )
    if data.get('harcama_tarihi'):
        try:
            yeni_harcama.harcama_tarihi = datetime.fromisoformat(data['harcama_tarihi'])
        except ValueError:
             return jsonify({'message': 'Geçersiz harcama tarihi formatı.'}), 400

    try:
        db.session.add(yeni_harcama)
        # Kasa hareketini harcama ile aynı transaction içinde yönetmek için:
        # 1. Harcamayı session'a ekle.
        # 2. Kasa hareketini `commit_session=False` ile ekle.
        # 3. Harcama ID'si flush ile alınır.
        # 4. Kasa hareketinin referans_id'si güncellenir.
        # 5. Tek commit yapılır.

        db.session.flush() # yeni_harcama için ID oluşturulsun

        if odeme_kaynagi == "Kasa":
            if not kasa: raise ValueError("Harcama kasası geçerli değil.")
            add_kasa_hareketi(
                kasa_id=kasa.id,
                tutar=-tutar_decimal, # Gider
                islem_tipi="Proje Harcaması",
                aciklama=f"Proje: {proje.proje_adi} - {data['aciklama']}",
                referans_tablo='proje_harcamalari',
                referans_id=yeni_harcama.id,
                user_id=g.current_user.id,
                commit_session=False
            )
        elif odeme_kaynagi == "Mütevelli":
            if not mutevelli_cari: raise ValueError("Mütevelli cari hesabı geçerli değil.")
            from app.routes.cari_hesap_routes import add_cari_hesap_hareketi
            add_cari_hesap_hareketi(
                cari_hesap_id=mutevelli_cari.id,
                tutar=-tutar_decimal, # Mütevelli alacaklandı (vakıf borçlandı)
                islem_tipi="Mütevelli Ödemeli Proje Harcaması",
                aciklama=f"Proje: {proje.proje_adi} - {data['aciklama']}",
                referans_tablo='proje_harcamalari',
                referans_id=yeni_harcama.id,
                user_id=g.current_user.id,
                commit_session=False
            )

        db.session.commit()

    except ValueError as ve:
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje harcaması oluşturulurken hata: {str(e)}'}), 500

    return jsonify(yeni_harcama.to_dict()), 201


@proje_bp.route('/harcamalar/<int:harcama_id>', methods=['PUT'])
@token_required
# @role_required(['admin', 'project_manager', 'editor'])
def update_proje_harcamasi(harcama_id):
    harcama = ProjeHarcamasi.query.get_or_404(harcama_id)
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    # Eski değerleri sakla
    eski_tutar = harcama.tutar
    eski_odeme_kaynagi = harcama.odeme_kaynagi
    eski_kasa_id = harcama.kasa_id
    eski_mutevelli_cari_id = harcama.mutevelli_cari_id
    eski_para_birimi = harcama.para_birimi # Para birimi değişikliği de ele alınmalı
    # Proje adı değişebileceği için açıklama için proje adını dinamik alalım
    # eski_aciklama_detay = f"Proje: {harcama.proje.proje_adi} - {harcama.aciklama}"


    # Yeni değerleri al
    harcama.aciklama = data.get('aciklama', harcama.aciklama)
    yeni_odeme_kaynagi = data.get('odeme_kaynagi', eski_odeme_kaynagi)
    yeni_kasa_id = data.get('kasa_id') # Eğer Kasa ise güncellenecek
    yeni_mutevelli_cari_id = data.get('mutevelli_cari_id') # Eğer Mütevelli ise güncellenecek
    yeni_tutar_str = data.get('tutar')
    yeni_para_birimi = data.get('para_birimi', eski_para_birimi).upper()

    if yeni_odeme_kaynagi == "Kasa" and not yeni_kasa_id and not (eski_odeme_kaynagi == "Kasa" and eski_kasa_id) :
        return jsonify({'message': 'Yeni ödeme kaynağı Kasa ise yeni kasa_id zorunludur (veya eskisi kullanılacaksa belirtilmemeli).'}), 400
    if yeni_odeme_kaynagi == "Mütevelli" and not yeni_mutevelli_cari_id and not (eski_odeme_kaynagi == "Mütevelli" and eski_mutevelli_cari_id):
        return jsonify({'message': 'Yeni ödeme kaynağı Mütevelli ise yeni mutevelli_cari_id zorunludur (veya eskisi kullanılacaksa belirtilmemeli).'}), 400
    if yeni_odeme_kaynagi not in ["Kasa", "Mütevelli"]:
        return jsonify({'message': 'Geçersiz yeni odeme_kaynagi değeri.'}), 400


    if data.get('harcama_tarihi'):
        try:
            harcama.harcama_tarihi = datetime.fromisoformat(data['harcama_tarihi'])
        except ValueError:
            return jsonify({'message': 'Geçersiz harcama tarihi formatı.'}), 400

    yeni_tutar_str = data.get('tutar')

    # Kasa ID'lerini doğru atayalım
    if yeni_odeme_kaynagi == "Kasa":
        yeni_kasa_id = data.get('kasa_id', eski_kasa_id if eski_odeme_kaynagi == "Kasa" else None)
        if not yeni_kasa_id: return jsonify({'message': 'Ödeme kaynağı Kasa ise kasa_id zorunludur.'}), 400
    else: # Ödeme kaynağı Mütevelli ise kasa_id null olmalı
        yeni_kasa_id = None

    if yeni_odeme_kaynagi == "Mütevelli":
        yeni_mutevelli_cari_id = data.get('mutevelli_cari_id', eski_mutevelli_cari_id if eski_odeme_kaynagi == "Mütevelli" else None)
        if not yeni_mutevelli_cari_id: return jsonify({'message': 'Ödeme kaynağı Mütevelli ise mutevelli_cari_id zorunludur.'}), 400
    else: # Ödeme kaynağı Kasa ise mutevelli_cari_id null olmalı
        yeni_mutevelli_cari_id = None

    yeni_para_birimi = data.get('para_birimi', eski_para_birimi).upper()


    try:
        db.session.begin_nested()

        yeni_tutar = Decimal(yeni_tutar_str) if yeni_tutar_str is not None else eski_tutar
        if yeni_tutar <= 0:
            raise ValueError('Harcama tutarı pozitif olmalı.')

        # Değişiklik var mı kontrolü (tutar, ödeme kaynağı, ilgili ID veya para birimi)
        is_changed = (yeni_tutar != eski_tutar or \
                      yeni_odeme_kaynagi != eski_odeme_kaynagi or \
                      (yeni_odeme_kaynagi == "Kasa" and yeni_kasa_id != eski_kasa_id) or \
                      (yeni_odeme_kaynagi == "Mütevelli" and yeni_mutevelli_cari_id != eski_mutevelli_cari_id) or \
                      yeni_para_birimi != eski_para_birimi)

        if is_changed:
            # 1. Eski hareketi tersine çevir
            aciklama_iptal = f"Düzeltme (İptal): Proje Harcaması ID {harcama.id} - Proje: {harcama.proje.proje_adi}"
            if eski_odeme_kaynagi == "Kasa" and eski_kasa_id:
                add_kasa_hareketi(eski_kasa_id, eski_tutar, "Proje Harcaması Düzeltme (İade)", aciklama_iptal, 'proje_harcamalari', harcama.id, g.current_user.id, False)
            elif eski_odeme_kaynagi == "Mütevelli" and eski_mutevelli_cari_id:
                from app.routes.cari_hesap_routes import add_cari_hesap_hareketi
                add_cari_hesap_hareketi(eski_mutevelli_cari_id, eski_tutar, "Proje Harcaması Düzeltme (Mütevelli Alacak İptali)", aciklama_iptal, 'proje_harcamalari', harcama.id, g.current_user.id, False)

            # 2. Yeni hareketi ekle
            aciklama_yeni = f"Proje: {harcama.proje.proje_adi} - {data.get('aciklama', harcama.aciklama)}"
            if yeni_odeme_kaynagi == "Kasa":
                yeni_kasa_obj = Kasa.query.get(yeni_kasa_id)
                if not yeni_kasa_obj: raise ValueError("Yeni harcama kasası bulunamadı.")
                if yeni_kasa_obj.para_birimi.upper() != yeni_para_birimi:
                    raise ValueError(f"Yeni harcama para birimi ({yeni_para_birimi}) ile yeni kasa para birimi ({yeni_kasa_obj.para_birimi}) uyuşmuyor.")
                add_kasa_hareketi(yeni_kasa_id, -yeni_tutar, "Proje Harcaması", aciklama_yeni, 'proje_harcamalari', harcama.id, g.current_user.id, False)
            elif yeni_odeme_kaynagi == "Mütevelli":
                from app.models.cari_hesap import CariHesap
                yeni_mutevelli_obj = CariHesap.query.get(yeni_mutevelli_cari_id)
                if not yeni_mutevelli_obj: raise ValueError("Yeni mütevelli cari hesabı bulunamadı.")
                if yeni_mutevelli_obj.hesap_turu != "Mütevelli": raise ValueError("Belirtilen cari hesap mütevelli değil.")
                if yeni_mutevelli_obj.para_birimi.upper() != yeni_para_birimi:
                    raise ValueError(f"Yeni harcama para birimi ({yeni_para_birimi}) ile yeni mütevelli cari para birimi ({yeni_mutevelli_obj.para_birimi}) uyuşmuyor.")
                from app.routes.cari_hesap_routes import add_cari_hesap_hareketi
                add_cari_hesap_hareketi(yeni_mutevelli_cari_id, -yeni_tutar, "Mütevelli Ödemeli Proje Harcaması", aciklama_yeni, 'proje_harcamalari', harcama.id, g.current_user.id, False)

        # Harcama objesini güncelle
        harcama.tutar = yeni_tutar
        harcama.odeme_kaynagi = yeni_odeme_kaynagi
        harcama.kasa_id = yeni_kasa_id if yeni_odeme_kaynagi == "Kasa" else None
        harcama.mutevelli_cari_id = yeni_mutevelli_cari_id if yeni_odeme_kaynagi == "Mütevelli" else None
        harcama.para_birimi = yeni_para_birimi

        db.session.add(harcama)
        db.session.commit()
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje harcaması güncellenirken hata: {str(e)}'}), 500

    return jsonify(harcama.to_dict()), 200


@proje_bp.route('/harcamalar/<int:harcama_id>', methods=['DELETE'])
@token_required
# @role_required(['admin', 'project_manager'])
def delete_proje_harcamasi(harcama_id):
    harcama = ProjeHarcamasi.query.get_or_404(harcama_id)

    try:
        db.session.begin_nested() # İşlemleri grupla
        aciklama_iptal = f"Silinen Harcama ID {harcama.id}: Proje: {harcama.proje.proje_adi} - {harcama.aciklama}"

        if harcama.odeme_kaynagi == "Kasa" and harcama.kasa_id:
            add_kasa_hareketi(
                kasa_id=harcama.kasa_id,
                tutar=harcama.tutar, # Pozitif olarak iade
                islem_tipi="Proje Harcaması Silme (Kasa İade)",
                aciklama=aciklama_iptal,
                referans_tablo='proje_harcamalari',
                referans_id=harcama.id,
                user_id=g.current_user.id,
                commit_session=False
            )
        elif harcama.odeme_kaynagi == "Mütevelli" and harcama.mutevelli_cari_id:
            from app.routes.cari_hesap_routes import add_cari_hesap_hareketi
            add_cari_hesap_hareketi(
                cari_hesap_id=harcama.mutevelli_cari_id,
                tutar=harcama.tutar, # Mütevellinin alacağını iptal et (borç hareketi)
                islem_tipi="Proje Harcaması Silme (Mütevelli Alacak İptali)",
                aciklama=aciklama_iptal,
                referans_tablo='proje_harcamalari',
                referans_id=harcama.id,
                user_id=g.current_user.id,
                commit_session=False
            )

        db.session.delete(harcama)
        db.session.commit()
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje harcaması silinirken hata: {str(e)}'}), 500

    return jsonify({'message': 'Proje harcaması başarıyla silindi'}), 200

@proje_bp.route('/harcamalar', methods=['GET']) # Tüm proje harcamalarını listelemek için
@token_required
# @role_required(['admin', 'accountant', 'project_viewer'])
def get_all_proje_harcamalari():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    tarih_baslangic_str = request.args.get('tarih_baslangic') # Harcama tarihi için
    tarih_bitis_str = request.args.get('tarih_bitis') # Harcama tarihi için
    sirala_alan = request.args.get('sirala_alan', 'harcama_tarihi')
    sirala_yon = request.args.get('sirala_yon', 'desc')

    proje_id_filter = request.args.get('proje_id', type=int)
    kasa_id_filter = request.args.get('kasa_id', type=int)
    odeme_kaynagi_filter = request.args.get('odeme_kaynagi')
    mutevelli_cari_id_filter = request.args.get('mutevelli_cari_id', type=int)
    user_id_filter = request.args.get('user_id', type=int) # Harcamayı giren kullanıcı
    min_tutar_filter = request.args.get('min_tutar', type=Decimal)
    max_tutar_filter = request.args.get('max_tutar', type=Decimal)
    para_birimi_filter = request.args.get('para_birimi')

    query = ProjeHarcamasi.query

    if tarih_baslangic_str:
        try:
            tarih_baslangic = datetime.fromisoformat(tarih_baslangic_str)
            query = query.filter(ProjeHarcamasi.harcama_tarihi >= tarih_baslangic)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_baslangic formatı.'}), 400
    if tarih_bitis_str:
        try:
            tarih_bitis = datetime.fromisoformat(tarih_bitis_str).replace(hour=23, minute=59, second=59)
            query = query.filter(ProjeHarcamasi.harcama_tarihi <= tarih_bitis)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_bitis formatı.'}), 400

    if proje_id_filter:
        query = query.filter(ProjeHarcamasi.proje_id == proje_id_filter)
    if kasa_id_filter:
        query = query.filter(ProjeHarcamasi.kasa_id == kasa_id_filter)
    if odeme_kaynagi_filter:
        query = query.filter(ProjeHarcamasi.odeme_kaynagi == odeme_kaynagi_filter)
    if mutevelli_cari_id_filter:
        query = query.filter(ProjeHarcamasi.mutevelli_cari_id == mutevelli_cari_id_filter)
    if user_id_filter:
        query = query.filter(ProjeHarcamasi.user_id == user_id_filter)
    if min_tutar_filter is not None:
        query = query.filter(ProjeHarcamasi.tutar >= min_tutar_filter)
    if max_tutar_filter is not None:
        query = query.filter(ProjeHarcamasi.tutar <= max_tutar_filter)
    if para_birimi_filter:
        query = query.filter(ProjeHarcamasi.para_birimi == para_birimi_filter.upper())


    valid_sort_fields = {
        'harcama_tarihi': ProjeHarcamasi.harcama_tarihi,
        'tutar': ProjeHarcamasi.tutar,
        'proje_id': ProjeHarcamasi.proje_id, # veya proje.proje_adi ile join yapılabilir
        'kasa_id': ProjeHarcamasi.kasa_id,
        'odeme_kaynagi': ProjeHarcamasi.odeme_kaynagi,
        'id': ProjeHarcamasi.id
    }
    sort_column = valid_sort_fields.get(sirala_alan, ProjeHarcamasi.harcama_tarihi)

    if sirala_yon == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    paginated_harcamalar = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'harcamalar': [h.to_dict() for h in paginated_harcamalar.items],
        'total': paginated_harcamalar.total,
        'page': paginated_harcamalar.page,
        'per_page': paginated_harcamalar.per_page,
        'total_pages': paginated_harcamalar.pages
    }), 200
