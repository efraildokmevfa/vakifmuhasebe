from flask import request, jsonify
from app import db
from flask import request, jsonify, g
from app import db
from app.models.kurban import KurbanTuru, KurbanBagisi
from app.models.kasa import Kasa
from app.routes.kasa_routes import add_kasa_hareketi
from . import kurban_bp
from app.utils.decorators import token_required, role_required # Güncellendi
from datetime import datetime
from decimal import Decimal

# --- Kurban Türü Rotaları ---
@kurban_bp.route('/turler', methods=['POST'])
def create_kurban_turu():
    data = request.get_json()
    if not data or not data.get('tur_adi'):
        return jsonify({'message': 'Eksik bilgi: tur_adi zorunludur'}), 400

    if KurbanTuru.query.filter_by(tur_adi=data['tur_adi']).first():
        return jsonify({'message': 'Bu kurban türü zaten mevcut'}), 409

    yeni_tur = KurbanTuru(
        tur_adi=data['tur_adi'],
        aciklama=data.get('aciklama')
    )
    db.session.add(yeni_tur)
    db.session.commit()
    return jsonify(yeni_tur.to_dict()), 201

@kurban_bp.route('/turler', methods=['GET'])
@token_required
def get_kurban_turleri():
    turler = KurbanTuru.query.order_by(KurbanTuru.tur_adi).all()
    return jsonify([tur.to_dict() for tur in turler]), 200

@kurban_bp.route('/turler/<int:tur_id>', methods=['GET'])
@token_required
def get_kurban_turu_by_id(tur_id):
    tur = KurbanTuru.query.get_or_404(tur_id)
    return jsonify(tur.to_dict()), 200

@kurban_bp.route('/turler/<int:tur_id>', methods=['PUT'])
@token_required
@role_required(['admin', 'editor']) # Yetkilendirme örneği
def update_kurban_turu(tur_id):
    tur = KurbanTuru.query.get_or_404(tur_id)
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    new_tur_adi = data.get('tur_adi')
    if new_tur_adi and new_tur_adi != tur.tur_adi:
        if KurbanTuru.query.filter_by(tur_adi=new_tur_adi).first():
            return jsonify({'message': 'Bu kurban türü adı zaten mevcut'}), 409
        tur.tur_adi = new_tur_adi

    tur.aciklama = data.get('aciklama', tur.aciklama)
    db.session.commit()
    return jsonify(tur.to_dict()), 200

@kurban_bp.route('/turler/<int:tur_id>', methods=['DELETE'])
@token_required
@role_required(['admin']) # Yetkilendirme örneği
def delete_kurban_turu(tur_id):
    tur = KurbanTuru.query.get_or_404(tur_id)
    if tur.bagislar.count() > 0:
        return jsonify({'message': 'Bu kurban türüne ait bağışlar bulunduğu için silinemez.'}), 400
    db.session.delete(tur)
    db.session.commit()
    return jsonify({'message': 'Kurban türü başarıyla silindi'}), 200


# --- Kurban Bağışı Rotaları ---
@kurban_bp.route('/bagislar', methods=['POST'])
@token_required
# @role_required(['admin', 'editor', 'data_entry'])
def create_kurban_bagisi():
    data = request.get_json()
    # alinan_sekli ve ona bağlı olarak gelir_kasa_id veya mutevelli_cari_id kontrolü eklenecek
    required_fields = ['bagisci_adi', 'bagis_tutari', 'para_birimi', 'kurban_turu_id', 'hayvan_turu', 'hisse_adedi', 'alinan_sekli']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'Eksik bilgi: {field} zorunludur'}), 400

    alinan_sekli = data['alinan_sekli']
    gelir_kasa_id = data.get('gelir_kasa_id')
    mutevelli_cari_id = data.get('mutevelli_cari_id')

    if alinan_sekli in ["Nakit Kasa", "Banka"] and not gelir_kasa_id:
        return jsonify({'message': 'Alınan şekli Kasa veya Banka ise gelir_kasa_id zorunludur.'}), 400
    if alinan_sekli == "Mütevelli Üzerinden" and not mutevelli_cari_id:
        return jsonify({'message': 'Alınan şekli Mütevelli Üzerinden ise mutevelli_cari_id zorunludur.'}), 400
    if alinan_sekli not in ["Nakit Kasa", "Banka", "Mütevelli Üzerinden"]:
        return jsonify({'message': 'Geçersiz alınan_sekli değeri.'}), 400

    try:
        bagis_tutari_decimal = Decimal(data['bagis_tutari'])
        hisse_adedi_int = int(data['hisse_adedi'])
        if bagis_tutari_decimal <= 0 or hisse_adedi_int <= 0:
            raise ValueError("Tutar ve hisse adedi pozitif olmalı")
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz bağış tutarı veya hisse adedi formatı'}), 400

    if not KurbanTuru.query.get(data['kurban_turu_id']):
        return jsonify({'message': 'Geçersiz kurban türü ID'}), 404

    gelir_kasa = None
    if alinan_sekli in ["Nakit Kasa", "Banka"]:
        gelir_kasa = Kasa.query.get(gelir_kasa_id)
        if not gelir_kasa:
            return jsonify({'message': 'Gelir kasası bulunamadı.'}), 404
        if gelir_kasa.para_birimi.upper() != data['para_birimi'].upper():
            return jsonify({'message': f'Bağış para birimi ({data["para_birimi"]}) ile kasa para birimi ({gelir_kasa.para_birimi}) uyuşmuyor.'}), 400

    mutevelli_cari = None
    if alinan_sekli == "Mütevelli Üzerinden":
        from app.models.cari_hesap import CariHesap # Döngüsel importu önlemek için burada import
        mutevelli_cari = CariHesap.query.get(mutevelli_cari_id)
        if not mutevelli_cari:
            return jsonify({'message': 'Mütevelli cari hesabı bulunamadı.'}), 404
        if mutevelli_cari.hesap_turu != "Mütevelli": # Opsiyonel kontrol
            return jsonify({'message': 'Belirtilen cari hesap bir mütevelli hesabı değil.'}), 400
        if mutevelli_cari.para_birimi.upper() != data['para_birimi'].upper():
            return jsonify({'message': f'Bağış para birimi ({data["para_birimi"]}) ile mütevelli cari para birimi ({mutevelli_cari.para_birimi}) uyuşmuyor.'}), 400

    # Hisse adedi kontrolü
    if data['hayvan_turu'] == 'Küçükbaş' and hisse_adedi_int != 1:
        return jsonify({'message': 'Küçükbaş kurban için hisse adedi 1 olmalıdır.'}), 400
    if data['hayvan_turu'] == 'Büyükbaş Hisse' and not (1 <= hisse_adedi_int <= 7):
        return jsonify({'message': 'Büyükbaş hisse için hisse adedi 1 ile 7 arasında olmalıdır.'}), 400

    yeni_bagis = KurbanBagisi(
        bagisci_adi=data['bagisci_adi'],
        bagisci_telefon=data.get('bagisci_telefon'),
        bagisci_email=data.get('bagisci_email'),
        bagis_tarihi=datetime.utcnow(),
        bagis_tutari=bagis_tutari_decimal,
        para_birimi=data['para_birimi'].upper(),
        kurban_turu_id=data['kurban_turu_id'],
        hayvan_turu=data['hayvan_turu'],
        hisse_adedi=hisse_adedi_int,
        vekalet_sahipleri=data.get('vekalet_sahipleri'),
        aciklama=data.get('aciklama'),
        alinan_sekli=alinan_sekli,
        gelir_kasa_id=gelir_kasa_id if alinan_sekli in ["Nakit Kasa", "Banka"] else None,
        mutevelli_cari_id=mutevelli_cari_id if alinan_sekli == "Mütevelli Üzerinden" else None
    )

    try:
        db.session.add(yeni_bagis)
        db.session.flush() # Yeni bağış ID'si oluşsun

        if alinan_sekli in ["Nakit Kasa", "Banka"]:
            if not gelir_kasa:
                raise ValueError("Gelir kasası geçerli değil.")
            add_kasa_hareketi(
                kasa_id=gelir_kasa.id,
                tutar=bagis_tutari_decimal, # Gelir
                islem_tipi="Kurban Bağışı",
                aciklama=f"{yeni_bagis.bagisci_adi} - {yeni_bagis.kurban_turu.tur_adi if yeni_bagis.kurban_turu else ''} Kurban Bağışı",
                referans_tablo='kurban_bagislari',
                referans_id=yeni_bagis.id,
                user_id=g.current_user.id,
                commit_session=False
            )
        elif alinan_sekli == "Mütevelli Üzerinden":
            if not mutevelli_cari:
                raise ValueError("Mütevelli cari hesabı geçerli değil.")
            from app.routes.cari_hesap_routes import add_cari_hesap_hareketi
            add_cari_hesap_hareketi(
                cari_hesap_id=mutevelli_cari.id,
                tutar=bagis_tutari_decimal, # Mütevelli borçlandı (vakfın alacağı arttı)
                islem_tipi="Mütevelli Üzerinden Kurban Bağışı",
                aciklama=f"{yeni_bagis.bagisci_adi} adına alınan kurban bağışı.",
                referans_tablo='kurban_bagislari',
                referans_id=yeni_bagis.id,
                user_id=g.current_user.id,
                commit_session=False
            )

        db.session.commit()
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Kurban bağışı oluşturulurken hata: {str(e)}'}), 500

    return jsonify(yeni_bagis.to_dict()), 201

@kurban_bp.route('/bagislar', methods=['GET'])
@token_required
def get_kurban_bagislari():
    # Filtreleme seçenekleri
    # Filtreleme seçenekleri
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)

    tarih_baslangic_str = request.args.get('tarih_baslangic') # YYYY-MM-DD
    tarih_bitis_str = request.args.get('tarih_bitis') # YYYY-MM-DD
    sirala_alan = request.args.get('sirala_alan', 'bagis_tarihi')
    sirala_yon = request.args.get('sirala_yon', 'desc')

    kesim_durumu_filter = request.args.get('kesim_durumu') # true, false, null (belirsiz)
    kurban_turu_id_filter = request.args.get('kurban_turu_id', type=int)
    hayvan_turu_filter = request.args.get('hayvan_turu')
    bagisci_adi_filter = request.args.get('bagisci_adi') # LIKE ile arama
    vekalet_sahibi_filter = request.args.get('vekalet_sahibi') # LIKE ile arama
    alinan_sekli_filter = request.args.get('alinan_sekli')
    mutevelli_cari_id_filter = request.args.get('mutevelli_cari_id', type=int)
    gelir_kasa_id_filter = request.args.get('gelir_kasa_id', type=int)


    query = KurbanBagisi.query

    if tarih_baslangic_str:
        try:
            tarih_baslangic = datetime.fromisoformat(tarih_baslangic_str)
            query = query.filter(KurbanBagisi.bagis_tarihi >= tarih_baslangic)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_baslangic formatı. YYYY-MM-DD kullanın.'}), 400
    if tarih_bitis_str:
        try:
            tarih_bitis = datetime.fromisoformat(tarih_bitis_str).replace(hour=23, minute=59, second=59)
            query = query.filter(KurbanBagisi.bagis_tarihi <= tarih_bitis)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_bitis formatı. YYYY-MM-DD kullanın.'}), 400

    if kesim_durumu_filter is not None:
        if kesim_durumu_filter.lower() == 'true':
            query = query.filter(KurbanBagisi.kesim_durumu == True)
        elif kesim_durumu_filter.lower() == 'false':
            query = query.filter(KurbanBagisi.kesim_durumu == False)
        # 'null' veya başka bir değer gelirse filtre uygulanmaz veya isteğe bağlı olarak IS NULL eklenebilir.

    if kurban_turu_id_filter:
        query = query.filter(KurbanBagisi.kurban_turu_id == kurban_turu_id_filter)
    if hayvan_turu_filter:
        query = query.filter(KurbanBagisi.hayvan_turu == hayvan_turu_filter)
    if bagisci_adi_filter:
        query = query.filter(KurbanBagisi.bagisci_adi.ilike(f"%{bagisci_adi_filter}%"))
    if vekalet_sahibi_filter: # vekalet_sahipleri alanı Text olduğu için LIKE ile arama
        query = query.filter(KurbanBagisi.vekalet_sahipleri.ilike(f"%{vekalet_sahibi_filter}%"))
    if alinan_sekli_filter:
        query = query.filter(KurbanBagisi.alinan_sekli == alinan_sekli_filter)
    if mutevelli_cari_id_filter:
        query = query.filter(KurbanBagisi.mutevelli_cari_id == mutevelli_cari_id_filter)
    if gelir_kasa_id_filter:
        query = query.filter(KurbanBagisi.gelir_kasa_id == gelir_kasa_id_filter)

    # Sıralama
    valid_sort_fields = {
        'bagis_tarihi': KurbanBagisi.bagis_tarihi,
        'bagisci_adi': KurbanBagisi.bagisci_adi,
        'bagis_tutari': KurbanBagisi.bagis_tutari,
        'kesim_tarihi': KurbanBagisi.kesim_tarihi,
        'id': KurbanBagisi.id
    }
    sort_column = valid_sort_fields.get(sirala_alan, KurbanBagisi.bagis_tarihi)
    if sirala_yon == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    paginated_bagislar = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'bagislar': [b.to_dict() for b in paginated_bagislar.items],
        'total': paginated_bagislar.total,
        'page': paginated_bagislar.page,
        'per_page': paginated_bagislar.per_page,
        'total_pages': paginated_bagislar.pages
    }), 200

@kurban_bp.route('/bagislar/<int:bagis_id>', methods=['GET'])
@token_required
def get_kurban_bagisi_by_id(bagis_id):
    bagis = KurbanBagisi.query.get_or_404(bagis_id)
    return jsonify(bagis.to_dict()), 200

@kurban_bp.route('/bagislar/<int:bagis_id>', methods=['PUT'])
@token_required
# @role_required(['admin', 'editor'])
def update_kurban_bagisi(bagis_id):
    bagis = KurbanBagisi.query.get_or_404(bagis_id)
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    # Temel bağışçı ve bağış miktarı bilgileri genellikle değiştirilmez.
    # Daha çok kesim bilgileri, vekalet sahipleri, açıklama güncellenir.
    bagis.bagisci_adi = data.get('bagisci_adi', bagis.bagisci_adi)
    bagis.bagisci_telefon = data.get('bagisci_telefon', bagis.bagisci_telefon)
    bagis.bagisci_email = data.get('bagisci_email', bagis.bagisci_email)
    bagis.vekalet_sahipleri = data.get('vekalet_sahipleri', bagis.vekalet_sahipleri)
    bagis.aciklama = data.get('aciklama', bagis.aciklama)

    # Kesim Bilgileri Güncelleme
    if 'kesim_durumu' in data: # Sadece varlığı kontrol ediliyor, True/False olabilir
        bagis.kesim_durumu = data['kesim_durumu']
        if bagis.kesim_durumu and not bagis.kesim_tarihi and not data.get('kesim_tarihi'):
            bagis.kesim_tarihi = datetime.utcnow() # Kesim tarihi otomatik atanabilir

    if data.get('kesim_tarihi'):
        try:
            bagis.kesim_tarihi = datetime.fromisoformat(data['kesim_tarihi'])
        except ValueError:
            return jsonify({'message': 'Geçersiz kesim tarihi formatı.'}), 400
    elif data.get('kesim_tarihi') == None and 'kesim_tarihi' in data: # Tarihi null yapmak için
        bagis.kesim_tarihi = None


    bagis.kesim_yeri = data.get('kesim_yeri', bagis.kesim_yeri)

    if data.get('kesim_masrafi') is not None:
        try:
            kesim_masrafi_decimal = Decimal(data['kesim_masrafi'])
            if kesim_masrafi_decimal < 0: raise ValueError("Kesim masrafı negatif olamaz")

            # Eğer masraf kasadan ödenecekse ve kasa değişiyorsa veya ilk kez atanıyorsa
            eski_masraf = bagis.kesim_masrafi or Decimal(0)
            eski_masraf_kasa_id = bagis.kesim_masraf_kasa_id

            yeni_masraf_kasa_id = data.get('kesim_masraf_kasa_id', bagis.kesim_masraf_kasa_id)

            if kesim_masrafi_decimal > 0 and not yeni_masraf_kasa_id:
                 return jsonify({'message': 'Kesim masrafı girildiyse, masraf kasası (kesim_masraf_kasa_id) belirtilmelidir.'}), 400

            if yeni_masraf_kasa_id:
                masraf_kasa = Kasa.query.get(yeni_masraf_kasa_id)
                if not masraf_kasa:
                    return jsonify({'message': 'Kesim masraf kasası bulunamadı'}), 404
                if masraf_kasa.para_birimi.upper() != bagis.para_birimi.upper(): # Masrafın da bağışla aynı para biriminde olduğunu varsayıyoruz
                    return jsonify({'message': f'Kesim masraf kasası para birimi ({masraf_kasa.para_birimi}) bağış para birimi ({bagis.para_birimi}) ile uyuşmuyor.'}), 400

            try:
                db.session.begin_nested() # Kasa hareketleri için savepoint

                # 1. Eski masraf varsa ve kasa değiştiyse veya masraf tutarı değiştiyse, eski hareketi tersine çevir
                if eski_masraf_kasa_id and eski_masraf > 0 and \
                   (eski_masraf_kasa_id != yeni_masraf_kasa_id or eski_masraf != kesim_masrafi_decimal or kesim_masrafi_decimal == 0):
                    add_kasa_hareketi(
                        kasa_id=eski_masraf_kasa_id,
                        tutar=eski_masraf, # İade (pozitif)
                        islem_tipi="Kurban Kesim Masrafı Düzeltme (İade)",
                        aciklama=f"Düzeltme: Bağış ID {bagis.id} - Eski kesim masrafı iadesi",
                        referans_tablo='kurban_bagislari',
                        referans_id=bagis.id,
                        user_id=g.current_user.id,
                        commit_session=False
                    )

                # 2. Yeni masraf varsa, yeni kasa hareketini ekle
                if kesim_masrafi_decimal > 0 and yeni_masraf_kasa_id:
                    # Kasa bakiyesi add_kasa_hareketi içinde kontrol edilecek.
                    add_kasa_hareketi(
                        kasa_id=yeni_masraf_kasa_id,
                        tutar=-kesim_masrafi_decimal, # Gider (negatif)
                        islem_tipi="Kurban Kesim Masrafı",
                        aciklama=f"Bağış ID {bagis.id} - {bagis.bagisci_adi} - Kesim Masrafı",
                        referans_tablo='kurban_bagislari',
                        referans_id=bagis.id,
                        user_id=g.current_user.id,
                        commit_session=False
                    )

                bagis.kesim_masrafi = kesim_masrafi_decimal
                bagis.kesim_masraf_kasa_id = yeni_masraf_kasa_id if kesim_masrafi_decimal > 0 else None

                # db.session.commit() # Ana commit dışarıda yapılacak
            except ValueError as ve: # Kasa bakiye yetersiz vb.
                db.session.rollback() # Sadece iç içe transaction'ı rollback et
                return jsonify({'message': str(ve)}), 400
            # Diğer exceptionlar ana try-except bloğunda yakalanacak.

        except (ValueError, TypeError): # Bu kesim_masrafi_decimal = Decimal(...) için
            return jsonify({'message': 'Geçersiz kesim masrafı formatı'}), 400

    if 'sahibine_bilgi_verildi' in data:
        bagis.sahibine_bilgi_verildi = data['sahibine_bilgi_verildi']
        if bagis.sahibine_bilgi_verildi and not bagis.bilgilendirme_tarihi and not data.get('bilgilendirme_tarihi'):
            bagis.bilgilendirme_tarihi = datetime.utcnow()

    if data.get('bilgilendirme_tarihi'):
        try:
            bagis.bilgilendirme_tarihi = datetime.fromisoformat(data['bilgilendirme_tarihi'])
        except ValueError:
            return jsonify({'message': 'Geçersiz bilgilendirme tarihi formatı.'}), 400
    elif data.get('bilgilendirme_tarihi') == None and 'bilgilendirme_tarihi' in data:
        bagis.bilgilendirme_tarihi = None

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Kurban bağışı güncellenirken hata: {str(e)}'}), 500

    return jsonify(bagis.to_dict()), 200

@kurban_bp.route('/bagislar/<int:bagis_id>', methods=['DELETE'])
@token_required
@role_required(['admin']) # Yetkilendirme örneği
def delete_kurban_bagisi(bagis_id):
    bagis = KurbanBagisi.query.get_or_404(bagis_id)

    try:
        db.session.begin_nested() # İşlemleri grupla

        # 1. Gelir hareketini veya cari hareketi tersine çevir
        if bagis.alinan_sekli in ["Nakit Kasa", "Banka"] and bagis.gelir_kasa_id:
            add_kasa_hareketi(
                kasa_id=bagis.gelir_kasa_id,
                tutar=-bagis.bagis_tutari, # Bağış tutarını çıkar (negatif)
                islem_tipi="Kurban Bağışı İptali (Kasa)",
                aciklama=f"İptal: Bağış ID {bagis.id} - {bagis.bagisci_adi}",
                referans_tablo='kurban_bagislari',
                referans_id=bagis.id,
                user_id=g.current_user.id,
                commit_session=False
            )
        elif bagis.alinan_sekli == "Mütevelli Üzerinden" and bagis.mutevelli_cari_id:
            from app.routes.cari_hesap_routes import add_cari_hesap_hareketi
            add_cari_hesap_hareketi(
                cari_hesap_id=bagis.mutevelli_cari_id,
                tutar=-bagis.bagis_tutari, # Mütevellinin borcunu azalt (alacak kaydı)
                islem_tipi="Kurban Bağışı İptali (Mütevelli)",
                aciklama=f"İptal: Bağış ID {bagis.id} - {bagis.bagisci_adi}",
                referans_tablo='kurban_bagislari',
                referans_id=bagis.id,
                user_id=g.current_user.id,
                commit_session=False
            )

        # 2. Eğer kesim masrafı yapıldıysa, masraf hareketini tersine çevir (kasaya iade)
        if bagis.kesim_masrafi and bagis.kesim_masrafi > 0 and bagis.kesim_masraf_kasa_id:
            add_kasa_hareketi(
                kasa_id=bagis.kesim_masraf_kasa_id,
                tutar=bagis.kesim_masrafi, # Masrafı iade et (pozitif)
                islem_tipi="Kurban Kesim Masrafı İptali",
                aciklama=f"İptal: Bağış ID {bagis.id} - Kesim masrafı iadesi",
                referans_tablo='kurban_bagislari',
                referans_id=bagis.id,
                user_id=g.current_user.id,
                commit_session=False
            )

        db.session.delete(bagis)
        db.session.commit() # Tüm işlemleri commit et

    except ValueError as ve: # Kasa bulunamadı veya bakiye yetersiz (iade durumunda pek olmaz)
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Kurban bağışı silinirken hata: {str(e)}'}), 500

    return jsonify({'message': 'Kurban bağışı ve ilgili kasa hareketleri (iptal) başarıyla silindi'}), 200
