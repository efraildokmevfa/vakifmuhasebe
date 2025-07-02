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
    durum_filter = request.args.get('durum')
    proje_turu_id_filter = request.args.get('proje_turu_id', type=int)

    query = Proje.query
    if durum_filter:
        query = query.filter(Proje.durum == durum_filter)
    if proje_turu_id_filter:
        query = query.filter(Proje.proje_turu_id == proje_turu_id_filter)

    projeler = query.order_by(Proje.baslangic_tarihi.desc().nullslast(), Proje.id.desc()).all()
    return jsonify([proje.to_dict() for proje in projeler]), 200

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

    required_fields = ['kasa_id', 'aciklama', 'tutar', 'para_birimi']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'Eksik bilgi: {field} zorunludur'}), 400

    try:
        tutar_decimal = Decimal(data['tutar'])
        if tutar_decimal <= 0:
            raise ValueError("Harcama tutarı pozitif olmalı.")
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz harcama tutarı.'}), 400

    kasa = Kasa.query.get(data['kasa_id'])
    if not kasa:
        return jsonify({'message': 'Harcama kasası bulunamadı.'}), 404

    if kasa.para_birimi.upper() != data['para_birimi'].upper():
        return jsonify({'message': f'Harcama para birimi ({data["para_birimi"]}) ile kasa para birimi ({kasa.para_birimi}) uyuşmuyor.'}), 400

    if kasa.bakiye < tutar_decimal:
        return jsonify({'message': f'Harcama kasasında ({kasa.kasa_adi}) yeterli bakiye yok. Bakiye: {kasa.bakiye}'}), 400

    yeni_harcama = ProjeHarcamasi(
        proje_id=proje_id,
        kasa_id=data['kasa_id'],
        aciklama=data['aciklama'],
        tutar=tutar_decimal,
        para_birimi=data['para_birimi'].upper(),
        user_id=g.current_user.id
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

        kasa_hareketi = add_kasa_hareketi(
            kasa_id=kasa.id,
            tutar=-tutar_decimal, # Gider olduğu için negatif
            islem_tipi="Proje Harcaması",
            aciklama=f"Proje: {proje.proje_adi} - {data['aciklama']}",
            referans_tablo='proje_harcamalari',
            referans_id=yeni_harcama.id, # Flush sayesinde ID burada mevcut
            user_id=g.current_user.id,
            commit_session=False # Ana commit dışarıda yapılacak
        )
        # add_kasa_hareketi içinde kasa ve hareket session'a eklendi.

        db.session.commit() # Tüm değişiklikleri (yeni_harcama, kasa bakiyesi, kasa_hareketi) commit et.

    except ValueError as ve: # Kasa bakiye yetersiz veya kasa bulunamadı vb.
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

    # Eski değerleri sakla (kasa hareketini düzeltmek için)
    eski_tutar = harcama.tutar
    eski_kasa_id = harcama.kasa_id
    eski_aciklama_detay = f"Proje: {harcama.proje.proje_adi} - {harcama.aciklama}"


    # Alanları güncelle
    harcama.aciklama = data.get('aciklama', harcama.aciklama)
    if data.get('harcama_tarihi'):
        try:
            harcama.harcama_tarihi = datetime.fromisoformat(data['harcama_tarihi'])
        except ValueError:
            return jsonify({'message': 'Geçersiz harcama tarihi formatı.'}), 400

    yeni_tutar_str = data.get('tutar')
    yeni_kasa_id = data.get('kasa_id', harcama.kasa_id) # Kasa değişebilir
    yeni_para_birimi = data.get('para_birimi', harcama.para_birimi).upper() # Para birimi değişebilir (dikkat!)

    try:
        db.session.begin_nested() # İç içe transaction veya savepoint

        # Kasa ve tutar değişikliği varsa kasa hareketlerini ayarla
        if yeni_tutar_str is not None or yeni_kasa_id != eski_kasa_id:
            yeni_tutar = Decimal(yeni_tutar_str) if yeni_tutar_str is not None else eski_tutar
            if yeni_tutar <= 0:
                return jsonify({'message': 'Harcama tutarı pozitif olmalı.'}), 400

            # 1. Eski kasa hareketini tersine çevir (eski kasaya iade)
            add_kasa_hareketi(
                kasa_id=eski_kasa_id,
                tutar=eski_tutar, # Pozitif olarak iade
                islem_tipi="Proje Harcaması Düzeltme (İade)",
                aciklama=f"Düzeltme: {eski_aciklama_detay}",
                referans_tablo='proje_harcamalari',
                referans_id=harcama.id,
                user_id=g.current_user.id,
                commit_session=False # Ana commit dışarıda
            )

            # 2. Yeni kasa hareketini ekle (yeni kasadan düş)
            yeni_kasa = Kasa.query.get(yeni_kasa_id)
            if not yeni_kasa:
                raise ValueError("Yeni harcama kasası bulunamadı.")
            if yeni_kasa.para_birimi.upper() != yeni_para_birimi.upper():
                raise ValueError(f"Yeni harcama para birimi ({yeni_para_birimi}) ile yeni kasa para birimi ({yeni_kasa.para_birimi}) uyuşmuyor.")

            # Kasa bakiyesi kontrolü add_kasa_hareketi içinde yapılacak.
            add_kasa_hareketi(
                kasa_id=yeni_kasa_id,
                tutar=-yeni_tutar, # Gider
                islem_tipi="Proje Harcaması",
                aciklama=f"Proje: {harcama.proje.proje_adi} - {harcama.aciklama}", # Güncellenmiş açıklama
                referans_tablo='proje_harcamalari',
                referans_id=harcama.id,
                user_id=g.current_user.id,
                commit_session=False
            )
            harcama.tutar = yeni_tutar
            harcama.kasa_id = yeni_kasa_id
            harcama.para_birimi = yeni_para_birimi

        db.session.add(harcama)
        db.session.commit() # Ana transaction'ı commit et
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
        # Kasa hareketini tersine çevir (kasaya iade)
        add_kasa_hareketi(
            kasa_id=harcama.kasa_id,
            tutar=harcama.tutar, # Pozitif olarak iade
            islem_tipi="Proje Harcaması Silme (İade)",
            aciklama=f"Silinen Harcama: Proje: {harcama.proje.proje_adi} - {harcama.aciklama}",
            referans_tablo='proje_harcamalari',
            referans_id=harcama.id,
            user_id=g.current_user.id,
            commit_session=False # Ana commit dışarıda
        )
        db.session.delete(harcama)
        db.session.commit()
    except ValueError as ve: # Kasa bulunamadı vs. (Normalde olmamalı)
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Proje harcaması silinirken hata: {str(e)}'}), 500

    return jsonify({'message': 'Proje harcaması başarıyla silindi'}), 200
