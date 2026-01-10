from flask import request, jsonify, g
from app import db
from app.models.is_avansi import IsAvansi, IsAvansiHarcamasi
from app.models.personel import Personel
from app.models.kasa import Kasa
from app.models.cari_hesap import CariHesap
from app.routes.kasa_routes import add_kasa_hareketi
from app.routes.cari_hesap_routes import add_cari_hesap_hareketi
from . import is_avansi_bp
from app.utils.decorators import token_required, role_required # Güncellendi
from datetime import datetime
from decimal import Decimal

# --- İş Avansı ve Maaş Avansı Rotaları ---
@is_avansi_bp.route('', methods=['POST'])
@token_required
# @role_required(['admin', 'human_resources', 'manager']) # Rolleri isteğe göre ayarlayın
def create_is_avansi():
    data = request.get_json()
    required_fields = ['personel_id', 'verilen_tutar', 'para_birimi', 'kasa_id', 'avans_tipi']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'Eksik bilgi: {field} zorunludur'}), 400

    avans_tipi = data['avans_tipi']
    if avans_tipi not in ['İş', 'Maaş']:
        return jsonify({'message': "Geçersiz avans_tipi. 'İş' veya 'Maaş' olmalıdır."}), 400

    try:
        verilen_tutar_decimal = Decimal(data['verilen_tutar'])
        if verilen_tutar_decimal <= 0:
            raise ValueError("Avans tutarı pozitif olmalı")
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz verilen tutar formatı'}), 400

    personel = Personel.query.get(data['personel_id'])
    if not personel:
        return jsonify({'message': 'Personel bulunamadı'}), 404

    kaynak_kasa = Kasa.query.get(data['kasa_id'])
    if not kaynak_kasa:
        return jsonify({'message': 'Kaynak kasa bulunamadı'}), 404

    if kaynak_kasa.para_birimi.upper() != data['para_birimi'].upper():
        return jsonify({'message': f'Avans para birimi ({data["para_birimi"]}) ile kasa para birimi ({kaynak_kasa.para_birimi}) uyuşmuyor.'}), 400

    # Kasa bakiyesi kontrolü add_kasa_hareketi içinde de var ama burada ön kontrol iyi olabilir.
    if kaynak_kasa.bakiye < verilen_tutar_decimal:
        return jsonify({'message': f'Kaynak kasada ({kaynak_kasa.kasa_adi}) yeterli bakiye yok. Mevcut Bakiye: {kaynak_kasa.bakiye}'}), 400

    yeni_avans = IsAvansi(
        personel_id=data['personel_id'],
        verilis_tarihi=datetime.utcnow(),
        verilen_tutar=verilen_tutar_decimal,
        para_birimi=data['para_birimi'].upper(),
        aciklama=data.get('aciklama'),
        avans_tipi=avans_tipi,
        durum='Verildi', # Maaş avansları için de başlangıç durumu 'Verildi' olabilir.
        kasa_id=data['kasa_id']
    )

    try:
        db.session.add(yeni_avans)
        db.session.flush() # Avans ID'si oluşsun

        add_kasa_hareketi(
            kasa_id=kaynak_kasa.id,
            tutar=-verilen_tutar_decimal, # Gider
            islem_tipi=f"{avans_tipi} Avansı Verildi",
            aciklama=f"{personel.ad_soyad} adlı personele {avans_tipi.lower()} avansı. {data.get('aciklama', '')}".strip(),
            referans_tablo='is_avanslari',
            referans_id=yeni_avans.id,
            user_id=g.current_user.id,
            commit_session=False # Ana commit dışarıda
        )
        db.session.commit()
    except ValueError as ve: # Kasa bakiye yetersiz vb. (add_kasa_hareketi'nden gelebilir)
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'{avans_tipi} avansı oluşturulurken hata: {str(e)}'}), 500

    return jsonify(yeni_avans.to_dict()), 201

@is_avansi_bp.route('', methods=['GET'])
@token_required
def get_is_avanslari():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    tarih_baslangic_str = request.args.get('tarih_baslangic') # Veriliş tarihi için
    tarih_bitis_str = request.args.get('tarih_bitis') # Veriliş tarihi için
    sirala_alan = request.args.get('sirala_alan', 'verilis_tarihi')
    sirala_yon = request.args.get('sirala_yon', 'desc')

    personel_id_filter = request.args.get('personel_id', type=int)
    durum_filter = request.args.get('durum')
    avans_tipi_filter = request.args.get('avans_tipi')
    kasa_id_filter = request.args.get('kasa_id', type=int)
    min_tutar_filter = request.args.get('min_tutar', type=Decimal)
    max_tutar_filter = request.args.get('max_tutar', type=Decimal)
    para_birimi_filter = request.args.get('para_birimi')

    query = IsAvansi.query

    if tarih_baslangic_str:
        try:
            tarih_baslangic = datetime.fromisoformat(tarih_baslangic_str)
            query = query.filter(IsAvansi.verilis_tarihi >= tarih_baslangic)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_baslangic formatı.'}), 400
    if tarih_bitis_str:
        try:
            tarih_bitis = datetime.fromisoformat(tarih_bitis_str).replace(hour=23, minute=59, second=59)
            query = query.filter(IsAvansi.verilis_tarihi <= tarih_bitis)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_bitis formatı.'}), 400

    if personel_id_filter:
        query = query.filter(IsAvansi.personel_id == personel_id_filter)
    if durum_filter:
        query = query.filter(IsAvansi.durum == durum_filter)
    if avans_tipi_filter and avans_tipi_filter in ['İş', 'Maaş']:
        query = query.filter(IsAvansi.avans_tipi == avans_tipi_filter)
    if kasa_id_filter:
        query = query.filter(IsAvansi.kasa_id == kasa_id_filter)
    if min_tutar_filter is not None:
        query = query.filter(IsAvansi.verilen_tutar >= min_tutar_filter)
    if max_tutar_filter is not None:
        query = query.filter(IsAvansi.verilen_tutar <= max_tutar_filter)
    if para_birimi_filter:
        query = query.filter(IsAvansi.para_birimi == para_birimi_filter.upper())

    valid_sort_fields = {
        'verilis_tarihi': IsAvansi.verilis_tarihi,
        'verilen_tutar': IsAvansi.verilen_tutar,
        'personel_id': IsAvansi.personel_id,
        'avans_tipi': IsAvansi.avans_tipi,
        'durum': IsAvansi.durum,
        'id': IsAvansi.id
    }
    sort_column = valid_sort_fields.get(sirala_alan, IsAvansi.verilis_tarihi)

    if sirala_yon == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    paginated_avanslar = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'avanslar': [a.to_dict() for a in paginated_avanslar.items],
        'total': paginated_avanslar.total,
        'page': paginated_avanslar.page,
        'per_page': paginated_avanslar.per_page,
        'total_pages': paginated_avanslar.pages
    }), 200

@is_avansi_bp.route('/<int:avans_id>', methods=['GET'])
@token_required
def get_is_avans_by_id(avans_id):
    avans = IsAvansi.query.get_or_404(avans_id)
    return jsonify(avans.to_dict()), 200

@is_avansi_bp.route('/<int:avans_id>', methods=['PUT'])
@token_required
# @role_required(['admin', 'human_resources', 'manager'])
def update_is_avans(avans_id):
    avans = IsAvansi.query.get_or_404(avans_id)
    data = request.get_json()

    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    # Temel bilgiler (tutar, personel, kasa, avans_tipi) genellikle oluşturulduktan sonra değiştirilmez.
    # Değiştirilirse kasa hareketleri ve muhasebe kayıtları karmaşıklaşır.
    # Bu endpoint daha çok açıklama, durum (dikkatli) ve mahsuplaşma notları için.
    if 'verilen_tutar' in data or 'personel_id' in data or 'kasa_id' in data or 'avans_tipi' in data:
        return jsonify({'message': 'Avansın temel bilgileri (tutar, personel, kasa, tip) bu endpoint ile değiştirilemez.'}), 400

    avans.aciklama = data.get('aciklama', avans.aciklama)
    # Durum değişikliği dikkatli yönetilmeli, özellikle 'Tamamlandı' gibi.
    # Maaş avansları için 'Kısmen Mahsup Edildi' veya 'Tamamlandı' durumları maaş ödeme süreciyle yönetilmeli.
    if 'durum' in data and avans.avans_tipi == 'Maaş' and data['durum'] in ['Tamamlandı', 'Kısmen Mahsup Edildi']:
        if avans.kapatilabilir_tutar != 0 and data['durum'] == 'Tamamlandı':
             return jsonify({'message': 'Maaş avansı tamamen mahsup edilmeden veya iade alınmadan Tamamlandı yapılamaz.'}), 400
    avans.durum = data.get('durum', avans.durum)

    avans.mahsuplasma_notu = data.get('mahsuplasma_notu', avans.mahsuplasma_notu)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'{avans.avans_tipi} avansı güncellenirken hata: {str(e)}'}), 500

    return jsonify(avans.to_dict()), 200


# --- İş Avansı Harcamaları Rotaları (Sadece 'İş' tipi avanslar için) ---
@is_avansi_bp.route('/<int:avans_id>/harcamalar', methods=['POST'])
@token_required
# @role_required(['admin', 'manager', 'editor']) # Kullanıcı kendi iş avansına harcama ekleyebilir mi?
def add_harcama_to_avans(avans_id):
    avans = IsAvansi.query.get_or_404(avans_id)
    if avans.avans_tipi != 'İş':
        return jsonify({'message': "Sadece 'İş' tipi avanslara harcama eklenebilir."}), 400

    data = request.get_json()
    if not data or not data.get('harcama_tutari') or not data.get('harcama_aciklamasi'):
        return jsonify({'message': 'Eksik bilgi: harcama_tutari ve harcama_aciklamasi zorunludur'}), 400

    try:
        harcama_tutari_decimal = Decimal(data['harcama_tutari'])
        if harcama_tutari_decimal <= 0:
            raise ValueError("Harcama tutarı pozitif olmalı")
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz harcama tutarı formatı'}), 400

    if avans.durum not in ['Verildi', 'Harcama Beyan Edildi', 'Kısmi İade']:
         return jsonify({'message': f'Bu durumdaki ({avans.durum}) bir iş avansına harcama eklenemez.'}), 400

    yeni_harcama = IsAvansiHarcamasi(
        is_avansi_id=avans_id,
        harcama_tutari=harcama_tutari_decimal,
        harcama_aciklamasi=data['harcama_aciklamasi'],
        belge_no=data.get('belge_no')
        # user_id=g.current_user.id # Harcamayı yapan kullanıcı (opsiyonel)
    )
    if data.get('harcama_tarihi'):
        try:
            yeni_harcama.harcama_tarihi = datetime.fromisoformat(data['harcama_tarihi'].split('T')[0]).date()
        except ValueError:
            return jsonify({'message': 'Geçersiz harcama tarihi formatı. YYYY-MM-DD kullanın.'}), 400

    if avans.durum == 'Verildi':
        avans.durum = 'Harcama Beyan Edildi'

    db.session.add(yeni_harcama)
    db.session.add(avans)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'İş avansı harcaması eklenirken hata: {str(e)}'}), 500

    return jsonify(yeni_harcama.to_dict()), 201

@is_avansi_bp.route('/harcamalar/<int:harcama_id>', methods=['PUT'])
@token_required
def update_harcama(harcama_id):
    harcama = IsAvansiHarcamasi.query.get_or_404(harcama_id)
    avans = IsAvansi.query.get_or_404(harcama.is_avansi_id)

    if avans.avans_tipi != 'İş':
        return jsonify({'message': "Sadece 'İş' tipi avansların harcamaları güncellenebilir."}), 400

    data = request.get_json()
    if not data:
        return jsonify({'message': 'Güncellenecek veri bulunamadı'}), 400

    if avans.durum not in ['Verildi', 'Harcama Beyan Edildi', 'Kısmi İade']:
         return jsonify({'message': f'Bu durumdaki ({avans.durum}) bir iş avansının harcaması güncellenemez.'}), 400

    # Harcama tutarı değişirse, avansın genel durumu etkilenebilir.
    # Şimdilik sadece harcama detaylarını güncelliyoruz. Tutar değişikliği daha karmaşık bir işlem.
    if 'harcama_tutari' in data and Decimal(data.get('harcama_tutari')) != harcama.harcama_tutari:
         return jsonify({'message': 'Harcama tutarı bu endpoint ile değiştirilemez. Harcamayı silip yeniden oluşturun.'}), 400

    harcama.harcama_aciklamasi = data.get('harcama_aciklamasi', harcama.harcama_aciklamasi)
    harcama.belge_no = data.get('belge_no', harcama.belge_no)
    if data.get('harcama_tarihi'):
        try:
            harcama.harcama_tarihi = datetime.fromisoformat(data['harcama_tarihi'].split('T')[0]).date()
        except ValueError:
            return jsonify({'message': 'Geçersiz harcama tarihi formatı. YYYY-MM-DD kullanın.'}), 400

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'İş avansı harcaması güncellenirken hata: {str(e)}'}), 500

    return jsonify(harcama.to_dict()), 200

@is_avansi_bp.route('/harcamalar/<int:harcama_id>', methods=['DELETE'])
@token_required
def delete_harcama(harcama_id):
    harcama = IsAvansiHarcamasi.query.get_or_404(harcama_id)
    avans = IsAvansi.query.get_or_404(harcama.is_avansi_id)

    if avans.avans_tipi != 'İş':
        return jsonify({'message': "Sadece 'İş' tipi avansların harcamaları silinebilir."}), 400

    if avans.durum not in ['Verildi', 'Harcama Beyan Edildi', 'Kısmi İade']:
         return jsonify({'message': f'Bu durumdaki ({avans.durum}) bir iş avansının harcaması silinemez.'}), 400

    db.session.delete(harcama)

    try:
        db.session.commit()
        # Harcama silindikten sonra avansın durumu güncellenebilir.
        # Örneğin, hiç harcaması kalmadıysa 'Verildi' durumuna dönebilir.
        if not avans.harcamalar.count() and avans.durum == 'Harcama Beyan Edildi':
            avans.durum = 'Verildi'
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'İş avansı harcaması silinirken hata: {str(e)}'}), 500

    return jsonify({'message': 'İş avansı harcaması başarıyla silindi'}), 200


# --- İş Avansı Kapatma/İade (Sadece 'İş' tipi avanslar için) ---
@is_avansi_bp.route('/<int:avans_id>/kapat', methods=['POST'])
@token_required
# @role_required(['admin', 'manager'])
def close_is_avansi(avans_id):
    avans = IsAvansi.query.get_or_404(avans_id)
    data = request.get_json()

    if avans.avans_tipi != 'İş':
        return jsonify({'message': "Bu işlem sadece 'İş' tipi avanslar için geçerlidir. Maaş avansları maaş ödeme sürecinde mahsup edilir."}), 400

    if avans.durum in ['Tamamlandı', 'İptal Edildi']:
        return jsonify({'message': f'Bu iş avansı zaten "{avans.durum}" durumunda.'}), 400

    # `toplam_harcanan_is_avansi` model property'si kullanılacak.
    fark = avans.verilen_tutar - avans.toplam_harcanan_is_avansi - (avans.iade_edilen_tutar or Decimal(0))

    iade_tutari_str = data.get('iade_tutari')
    iade_kasa_id = data.get('iade_kasa_id')
    borclandir_personele = data.get('borclandir_personele', False)
    odeme_yap_personele_kasa_id = data.get('odeme_yap_personele_kasa_id')
    kapatma_notu = data.get('kapatma_notu', "")

    personel = avans.personel
    islem_yapildi = False # Herhangi bir finansal işlem yapılıp yapılmadığını takip etmek için

    try:
        db.session.begin_nested() # Tüm işlemleri tek bir transaction'da toplamak için

        if fark > 0: # Personelden iade alınması veya borç yazılması gerekiyor
            if iade_tutari_str:
                iade_edilen_tutar = Decimal(iade_tutari_str)
                if iade_edilen_tutar < 0: raise ValueError("İade tutarı negatif olamaz")
                if iade_edilen_tutar > fark:
                    raise ValueError(f'İade edilen tutar ({iade_edilen_tutar}), kalan farktan ({fark}) büyük olamaz.')
                if iade_edilen_tutar > 0 and not iade_kasa_id:
                    raise ValueError('İade tutarı girildiyse, iadenin yapılacağı kasa (iade_kasa_id) belirtilmelidir.')

                if iade_edilen_tutar > 0:
                    hedef_kasa = Kasa.query.get(iade_kasa_id)
                    if not hedef_kasa: raise ValueError('İade kasası bulunamadı')
                    if hedef_kasa.para_birimi.upper() != avans.para_birimi.upper():
                        raise ValueError(f'İade kasası para birimi ({hedef_kasa.para_birimi}) avans para birimi ({avans.para_birimi}) ile uyuşmuyor.')

                    add_kasa_hareketi(
                        kasa_id=hedef_kasa.id,
                        tutar=iade_edilen_tutar, # Gelir
                        islem_tipi="İş Avansı İadesi",
                        aciklama=f"{personel.ad_soyad} - İş Avansı ID: {avans.id} iadesi. {kapatma_notu}".strip(),
                        referans_tablo='is_avanslari',
                        referans_id=avans.id,
                        user_id=g.current_user.id,
                        commit_session=False
                    )
                    avans.iade_edilen_tutar = (avans.iade_edilen_tutar or Decimal(0)) + iade_edilen_tutar
                    fark -= iade_edilen_tutar
                    islem_yapildi = True

            if fark > 0 and borclandir_personele:
                if not personel.cari_hesap_id:
                    raise ValueError('Personelin borçlandırılması için bir cari hesabı tanımlı değil.')
                personel_cari = CariHesap.query.get(personel.cari_hesap_id)
                if not personel_cari: raise ValueError('Personelin cari hesabı bulunamadı.')
                if personel_cari.para_birimi.upper() != avans.para_birimi.upper():
                    raise ValueError(f'Personel cari hesap para birimi ({personel_cari.para_birimi}) ile avans para birimi ({avans.para_birimi}) farklı.')

                add_cari_hesap_hareketi(
                    cari_hesap_id=personel_cari.id,
                    tutar=fark, # Personele borç (cari bakiye artar)
                    islem_tipi="İş Avansı Borç Kaydı",
                    aciklama=f"İş Avansı ID: {avans.id} - Harcanmayan tutar personele borç yazıldı. {kapatma_notu}".strip(),
                    referans_tablo='is_avanslari',
                    referans_id=avans.id,
                    user_id=g.current_user.id,
                    commit_session=False
                )
                # Borçlandırılan tutar da avansın iade edilmiş gibi kapanmasını sağlar
                avans.iade_edilen_tutar = (avans.iade_edilen_tutar or Decimal(0)) + fark
                fark = Decimal(0) # Fark kapandı
                islem_yapildi = True

        elif fark < 0: # Personele ek ödeme yapılması gerekiyor
            odenecek_tutar = abs(fark)
            if not odeme_yap_personele_kasa_id:
                raise ValueError('Personele yapılacak ek ödeme için kaynak kasa (odeme_yap_personele_kasa_id) belirtilmelidir.')

            odeme_kaynak_kasa = Kasa.query.get(odeme_yap_personele_kasa_id)
            if not odeme_kaynak_kasa: raise ValueError('Ek ödeme için kaynak kasa bulunamadı.')
            if odeme_kaynak_kasa.para_birimi.upper() != avans.para_birimi.upper():
                raise ValueError(f'Ek ödeme kasası para birimi ({odeme_kaynak_kasa.para_birimi}) avans para birimi ({avans.para_birimi}) ile uyuşmuyor.')
            if odeme_kaynak_kasa.bakiye < odenecek_tutar:
                 raise ValueError(f'Ek ödeme için kaynak kasada ({odeme_kaynak_kasa.kasa_adi}) yeterli bakiye yok.')

            add_kasa_hareketi(
                kasa_id=odeme_kaynak_kasa.id,
                tutar=-odenecek_tutar, # Gider
                islem_tipi="İş Avansı Ek Ödeme",
                aciklama=f"{personel.ad_soyad} - İş Avansı ID: {avans.id} fazla harcama için ek ödeme. {kapatma_notu}".strip(),
                referans_tablo='is_avanslari',
                referans_id=avans.id,
                user_id=g.current_user.id,
                commit_session=False
            )
            # Bu durumda avansın verilen tutarı artmış gibi düşünülebilir veya sadece not alınır.
            # Şimdilik sadece kasadan çıkış yapıyoruz, avansın verilen_tutar'ını değiştirmiyoruz.
            # Fark kapanmış olur.
            fark = Decimal(0)
            islem_yapildi = True

        if fark == 0 and islem_yapildi: # Eğer fark kapandıysa ve bir işlem yapıldıysa
            avans.durum = 'Tamamlandı'
        elif fark > 0 and not islem_yapildi: # Hiçbir işlem yapılmadı ve hala fark var
             return jsonify({'message': f'Avansı kapatmak için iade alınmalı veya personele borç yazılmalı. Kalan fark: {fark} {avans.para_birimi}'}), 400
        elif fark > 0 and islem_yapildi: # İade alındı ama hala fark var ve borç yazılmadı
            avans.durum = 'Kısmi İade'

        if kapatma_notu:
            avans.mahsuplasma_notu = (avans.mahsuplasma_notu + "\n" + kapatma_notu).strip() if avans.mahsuplasma_notu else kapatma_notu

        db.session.add(avans)
        db.session.commit() # Tüm işlemleri commit et

    except ValueError as ve:
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'İş avansı kapatılırken hata: {str(e)}'}), 500

    return jsonify({'message': f'İş avansı durumu "{avans.durum}" olarak güncellendi.', 'data': avans.to_dict()}), 200
