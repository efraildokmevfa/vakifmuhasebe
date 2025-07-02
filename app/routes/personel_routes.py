from flask import request, jsonify
from app import db
from app.models.personel import Personel
from app.models.cari_hesap import CariHesap # Cari Hesap oluşturmak için
from . import personel_bp # app/routes/__init__.py dosyasında tanımlanacak blueprint
from datetime import datetime

@personel_bp.route('', methods=['POST'])
def create_personel():
    data = request.get_json()
    if not data or not data.get('ad_soyad') or not data.get('personel_turu'):
        return jsonify({'message': 'Eksik bilgi: ad_soyad ve personel_turu zorunludur'}), 400

    # Yeni personel için otomatik cari hesap oluşturma (opsiyonel)
    # Eğer 'otomatik_cari_hesap_olustur' true ise ve personel için bir cari hesap yoksa oluştur.
    # Ya da 'cari_hesap_id' doğrudan verilebilir.

    cari_hesap_id = data.get('cari_hesap_id')
    otomatik_cari_olustur = data.get('otomatik_cari_hesap_olustur', False) # Default False

    if cari_hesap_id and otomatik_cari_olustur:
        return jsonify({'message': 'Hem cari_hesap_id hem de otomatik_cari_hesap_olustur aynı anda belirtilemez.'}), 400

    personel_cari_hesap = None
    if cari_hesap_id:
        personel_cari_hesap = CariHesap.query.get(cari_hesap_id)
        if not personel_cari_hesap:
            return jsonify({'message': f'Belirtilen cari_hesap_id ({cari_hesap_id}) bulunamadı.'}), 404
        # Bu cari hesabın başka bir personele atanıp atanmadığını kontrol et
        existing_personel_with_cari = Personel.query.filter_by(cari_hesap_id=cari_hesap_id).first()
        if existing_personel_with_cari:
            return jsonify({'message': f'Bu cari hesap ({cari_hesap_id}) zaten başka bir personele atanmış.'}), 409


    elif otomatik_cari_olustur:
        # Personel adına bir cari hesap oluştur
        # Varsayılan para birimi TRY veya konfigürasyondan alınabilir.
        # Para birimi request'ten de alınabilir: data.get('personel_cari_para_birimi', 'TRY')
        personel_cari_hesap = CariHesap(
            hesap_adi=f"{data['ad_soyad']} (Personel)",
            hesap_turu='Personel', # Sabit olarak Personel
            para_birimi=data.get('personel_cari_para_birimi', 'TRY').upper(), # Request'ten alınabilir
            aktif=True
        )
        db.session.add(personel_cari_hesap)
        # Cari hesap ID'si commit sonrası oluşacağı için, personel kaydından önce flush edilebilir
        # veya personel kaydı sonrası cari_hesap_id güncellenebilir.
        # Şimdilik flush ile ID almayı deneyelim.
        try:
            db.session.flush() # ID'nin atanması için
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': f'Personel için cari hesap oluşturulurken hata: {str(e)}'}), 500


    yeni_personel = Personel(
        ad_soyad=data['ad_soyad'],
        personel_turu=data['personel_turu'],
        pozisyon=data.get('pozisyon'),
        aktif=data.get('aktif', True)
    )

    if data.get('ise_baslama_tarihi'):
        try:
            yeni_personel.ise_baslama_tarihi = datetime.fromisoformat(data['ise_baslama_tarihi'].split('T')[0]).date()
        except ValueError:
            db.session.rollback() # Eğer cari hesap için flush yapıldıysa geri al
            return jsonify({'message': 'Geçersiz işe başlama tarihi formatı. YYYY-MM-DD kullanın.'}), 400

    if personel_cari_hesap:
        yeni_personel.cari_hesap_id = personel_cari_hesap.id
        yeni_personel.cari_hesap = personel_cari_hesap


    db.session.add(yeni_personel)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Personel kaydedilirken hata: {str(e)}'}), 500

    return jsonify(yeni_personel.to_dict()), 201

@personel_bp.route('', methods=['GET'])
def get_personeller():
    aktif_filter = request.args.get('aktif')
    personel_turu_filter = request.args.get('personel_turu')

    query = Personel.query
    if aktif_filter is not None:
        query = query.filter(Personel.aktif == (aktif_filter.lower() == 'true'))
    if personel_turu_filter:
        query = query.filter(Personel.personel_turu == personel_turu_filter)

    personeller = query.order_by(Personel.ad_soyad).all()
    return jsonify([p.to_dict() for p in personeller]), 200

@personel_bp.route('/<int:personel_id>', methods=['GET'])
def get_personel_by_id(personel_id):
    personel = Personel.query.get_or_404(personel_id)
    return jsonify(personel.to_dict()), 200

@personel_bp.route('/<int:personel_id>', methods=['PUT'])
def update_personel(personel_id):
    personel = Personel.query.get_or_404(personel_id)
    data = request.get_json()

    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    personel.ad_soyad = data.get('ad_soyad', personel.ad_soyad)
    personel.personel_turu = data.get('personel_turu', personel.personel_turu)
    personel.pozisyon = data.get('pozisyon', personel.pozisyon)
    personel.aktif = data.get('aktif', personel.aktif)

    if data.get('ise_baslama_tarihi'):
        try:
            personel.ise_baslama_tarihi = datetime.fromisoformat(data['ise_baslama_tarihi'].split('T')[0]).date()
        except ValueError:
            return jsonify({'message': 'Geçersiz işe başlama tarihi formatı. YYYY-MM-DD kullanın.'}), 400

    if data.get('isten_ayrilma_tarihi'):
        try:
            personel.isten_ayrilma_tarihi = datetime.fromisoformat(data['isten_ayrilma_tarihi'].split('T')[0]).date()
        except ValueError:
            return jsonify({'message': 'Geçersiz işten ayrılma tarihi formatı. YYYY-MM-DD kullanın.'}), 400
    else: # Tarihi null yapmak için
        personel.isten_ayrilma_tarihi = data.get('isten_ayrilma_tarihi', personel.isten_ayrilma_tarihi)


    # Cari Hesap ID güncellemesi
    new_cari_hesap_id = data.get('cari_hesap_id')
    if new_cari_hesap_id is not None: # 0 da geçerli bir ID olamayacağı için (genelde 1'den başlar)
        if new_cari_hesap_id == 0: # Cari hesabı kaldırmak için
             personel.cari_hesap_id = None
             personel.cari_hesap = None
        else:
            yeni_cari_hesap = CariHesap.query.get(new_cari_hesap_id)
            if not yeni_cari_hesap:
                return jsonify({'message': f'Belirtilen cari_hesap_id ({new_cari_hesap_id}) bulunamadı.'}), 404

            # Bu yeni cari hesabın başka bir personele atanıp atanmadığını kontrol et (kendisi hariç)
            existing_personel_with_cari = Personel.query.filter(Personel.cari_hesap_id == new_cari_hesap_id, Personel.id != personel_id).first()
            if existing_personel_with_cari:
                 return jsonify({'message': f'Bu cari hesap ({new_cari_hesap_id}) zaten başka bir personele atanmış.'}), 409

            personel.cari_hesap_id = yeni_cari_hesap.id
            personel.cari_hesap = yeni_cari_hesap

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Personel güncellenirken hata: {str(e)}'}), 500

    return jsonify(personel.to_dict()), 200

@personel_bp.route('/<int:personel_id>', methods=['DELETE'])
def delete_personel(personel_id):
    personel = Personel.query.get_or_404(personel_id)
    # İleride personele bağlı iş avansı vs. varsa silinmesini engellemek gibi kontroller eklenebilir.
    # if personel.is_avanslari.count() > 0:
    #    return jsonify({'message': 'Personele ait iş avansları bulunduğu için silinemez'}), 400

    # Personel silinirken ilişkili cari hesap silinmemeli, sadece bağlantı koparılmalı.
    # Cari hesap ayrıca silinebilir.

    db.session.delete(personel)
    db.session.commit()
    return jsonify({'message': 'Personel başarıyla silindi'}), 200
