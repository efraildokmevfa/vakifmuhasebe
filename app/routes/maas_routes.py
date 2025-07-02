from flask import request, jsonify, g
from app import db
from app.models.personel import Personel
from app.models.kasa import Kasa
from app.models.is_avansi import IsAvansi # Maaş avanslarını bulmak için
from app.models.maas import MaasOdeme, MaasAvansMahsubu
from app.routes.kasa_routes import add_kasa_hareketi
from app.routes.cari_hesap_routes import add_cari_hesap_hareketi
from . import maas_bp
from app.utils.decorators import token_required, role_required # Güncellendi
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

@maas_bp.route('/hesapla-ve-kaydet', methods=['POST'])
@token_required
# @role_required(['admin', 'human_resources'])
def hesapla_ve_kaydet_maas():
    data = request.get_json()
    required_fields = [
        'personel_id', 'donem_yil', 'donem_ay',
        'odenecek_net_maas', 'para_birimi', 'odeme_kasa_id'
    ]
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'Eksik bilgi: {field} zorunludur'}), 400

    try:
        personel_id = int(data['personel_id'])
        donem_yil = int(data['donem_yil'])
        donem_ay = int(data['donem_ay'])
        odenecek_net_maas = Decimal(data['odenecek_net_maas'])
        brut_maas_str = data.get('brut_maas')
        brut_maas = Decimal(brut_maas_str) if brut_maas_str else None
        kesintiler_str = data.get('kesintiler_toplami')
        kesintiler_toplami = Decimal(kesintiler_str) if kesintiler_str else Decimal('0.00')
        odeme_kasa_id = int(data['odeme_kasa_id'])
        para_birimi = data['para_birimi'].upper()
        aciklama = data.get('aciklama')
        mahsup_edilecek_avanslar = data.get('mahsup_edilecek_avanslar', []) # [{is_avansi_id: X, mahsup_tutari: Y}, ...]
    except (ValueError, TypeError) as e:
        return jsonify({'message': f'Geçersiz veri formatı: {e}'}), 400

    if odenecek_net_maas <= 0:
        return jsonify({'message': 'Ödenecek net maaş pozitif olmalıdır.'}), 400

    personel = Personel.query.get(personel_id)
    if not personel: return jsonify({'message': 'Personel bulunamadı.'}), 404

    odeme_kasa = Kasa.query.get(odeme_kasa_id)
    if not odeme_kasa: return jsonify({'message': 'Ödeme kasası bulunamadı.'}), 404
    if odeme_kasa.para_birimi != para_birimi:
        return jsonify({'message': f'Ödeme kasası para birimi ({odeme_kasa.para_birimi}) ile maaş para birimi ({para_birimi}) uyuşmuyor.'}), 400

    # Aynı personel için aynı döneme ait maaş kaydı var mı kontrolü
    existing_maas = MaasOdeme.query.filter_by(
        personel_id=personel_id,
        donem_yil=donem_yil,
        donem_ay=donem_ay
    ).first()
    if existing_maas and existing_maas.durum != 'İptal Edildi':
        return jsonify({'message': f'{personel.ad_soyad} için {donem_ay}/{donem_yil} dönemine ait aktif bir maaş kaydı zaten var (ID: {existing_maas.id}).'}), 409

    toplam_mahsup_tutari_bu_odeme_icin = Decimal('0.00')
    avans_mahsup_islemleri = [] # (IsAvansi objesi, mahsup_tutari_decimal)

    for mahsup_info in mahsup_edilecek_avanslar:
        avans_id = mahsup_info.get('is_avansi_id')
        mahsup_tutari_str = mahsup_info.get('mahsup_tutari')
        if not avans_id or not mahsup_tutari_str:
            return jsonify({'message': 'Mahsup edilecek avanslar listesinde eksik bilgi (is_avansi_id veya mahsup_tutari).'}), 400

        try:
            mahsup_tutari_decimal = Decimal(mahsup_tutari_str)
            if mahsup_tutari_decimal <= 0:
                raise ValueError("Mahsup tutarı pozitif olmalı.")
        except (ValueError, TypeError):
            return jsonify({'message': f'Avans ID {avans_id} için geçersiz mahsup tutarı.'}), 400

        avans = IsAvansi.query.get(avans_id)
        if not avans:
            return jsonify({'message': f'Mahsup için belirtilen avans ID {avans_id} bulunamadı.'}), 404
        if avans.personel_id != personel_id:
            return jsonify({'message': f'Avans ID {avans_id}, belirtilen personele ait değil.'}), 400
        if avans.avans_tipi != 'Maaş':
            return jsonify({'message': f"Avans ID {avans_id} bir 'Maaş' avansı değil, mahsup edilemez."}), 400
        if avans.para_birimi != para_birimi:
            return jsonify({'message': f'Avans ID {avans_id} para birimi ({avans.para_birimi}) maaş para birimi ({para_birimi}) ile uyuşmuyor.'}), 400

        kapatilabilir_avans_tutari = avans.kapatilabilir_tutar
        if mahsup_tutari_decimal > kapatilabilir_avans_tutari:
            return jsonify({'message': f'Avans ID {avans_id} için mahsup edilecek tutar ({mahsup_tutari_decimal}), avansın kapatılabilir kalanından ({kapatilabilir_avans_tutari}) fazla olamaz.'}), 400

        avans_mahsup_islemleri.append({'avans_obj': avans, 'mahsup_tutari': mahsup_tutari_decimal})
        toplam_mahsup_tutari_bu_odeme_icin += mahsup_tutari_decimal

    fiili_odenecek_tutar_kasa_cikis = odenecek_net_maas - toplam_mahsup_tutari_bu_odeme_icin
    if fiili_odenecek_tutar_kasa_cikis < 0:
        # Bu durum normalde olmamalı, çünkü mahsup tutarı net maaştan fazla olamaz (veya bu iş kuralı olarak eklenmeli)
        return jsonify({'message': 'Toplam mahsup tutarı, ödenecek net maaştan fazla olamaz.'}), 400

    if odeme_kasa.bakiye < fiili_odenecek_tutar_kasa_cikis:
        return jsonify({'message': f'Ödeme kasasında ({odeme_kasa.kasa_adi}) yeterli bakiye yok. Gerekli: {fiili_odenecek_tutar_kasa_cikis}, Mevcut: {odeme_kasa.bakiye}'}), 400

    yeni_maas_odeme = MaasOdeme(
        personel_id=personel_id,
        donem_yil=donem_yil,
        donem_ay=donem_ay,
        brut_maas=brut_maas,
        kesintiler_toplami=kesintiler_toplami,
        odenecek_net_maas=odenecek_net_maas,
        fiili_odenen_tutar=fiili_odenecek_tutar_kasa_cikis,
        odeme_kasa_id=odeme_kasa_id,
        para_birimi=para_birimi,
        aciklama=aciklama,
        durum='Ödendi' # Direkt ödendi kabul ediyoruz bu endpointte
    )

    try:
        db.session.add(yeni_maas_odeme)
        db.session.flush() # MaasOdeme ID'si oluşsun

        # Kasa hareketi (Maaş ödemesi için net çıkış)
        if fiili_odenecek_tutar_kasa_cikis > 0:
            add_kasa_hareketi(
                kasa_id=odeme_kasa.id,
                tutar=-fiili_odenecek_tutar_kasa_cikis, # Gider
                islem_tipi="Maaş Ödemesi",
                aciklama=f"{personel.ad_soyad} - {donem_ay}/{donem_yil} Maaş Ödemesi. {aciklama or ''}".strip(),
                referans_tablo='maas_odemeleri',
                referans_id=yeni_maas_odeme.id,
                user_id=g.current_user.id,
                commit_session=False
            )

        # Avans mahsup kayıtlarını ve avans güncellemelerini yap
        for islem in avans_mahsup_islemleri:
            avans_obj = islem['avans_obj']
            mahsup_tutari = islem['mahsup_tutari']

            mahsup_kaydi = MaasAvansMahsubu(
                maas_odeme_id=yeni_maas_odeme.id,
                is_avansi_id=avans_obj.id,
                mahsup_edilen_tutar=mahsup_tutari
            )
            db.session.add(mahsup_kaydi)

            avans_obj.mahsup_edilen_toplam_tutar = (avans_obj.mahsup_edilen_toplam_tutar or Decimal(0)) + mahsup_tutari
            if avans_obj.kapatilabilir_tutar == 0:
                avans_obj.durum = 'Tamamlandı' # Maaş avansı tamamen mahsup edildi
            else:
                avans_obj.durum = 'Kısmen Mahsup Edildi'
            db.session.add(avans_obj)

        db.session.commit()
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Maaş ödemesi kaydedilirken hata: {str(e)}'}), 500

    return jsonify(yeni_maas_odeme.to_dict()), 201


@maas_bp.route('/odemeler', methods=['GET'])
@token_required
def get_maas_odemeleri():
    personel_id = request.args.get('personel_id', type=int)
    donem_yil = request.args.get('donem_yil', type=int)
    donem_ay = request.args.get('donem_ay', type=int)

    query = MaasOdeme.query
    if personel_id:
        query = query.filter(MaasOdeme.personel_id == personel_id)
    if donem_yil:
        query = query.filter(MaasOdeme.donem_yil == donem_yil)
    if donem_ay:
        query = query.filter(MaasOdeme.donem_ay == donem_ay)

    odemeler = query.order_by(MaasOdeme.donem_yil.desc(), MaasOdeme.donem_ay.desc(), MaasOdeme.odeme_tarihi.desc()).all()
    return jsonify([o.to_dict() for o in odemeler]), 200

@maas_bp.route('/odemeler/<int:odeme_id>', methods=['GET'])
@token_required
def get_maas_odeme_by_id(odeme_id):
    odeme = MaasOdeme.query.get_or_404(odeme_id)
    return jsonify(odeme.to_dict()), 200

@maas_bp.route('/personel/<int:personel_id>/acik-maas-avanslari', methods=['GET'])
@token_required
def get_personel_acik_maas_avanslari(personel_id):
    personel = Personel.query.get_or_404(personel_id)

    # Sadece 'Maaş' tipi olan ve henüz 'Tamamlandı' veya 'İptal Edildi' durumunda olmayan avanslar
    acik_avanslar = IsAvansi.query.filter(
        IsAvansi.personel_id == personel_id,
        IsAvansi.avans_tipi == 'Maaş',
        IsAvansi.durum.notin_(['Tamamlandı', 'İptal Edildi'])
    ).order_by(IsAvansi.verilis_tarihi.asc()).all()

    result = []
    for avans in acik_avanslar:
        kapatilabilir = avans.kapatilabilir_tutar
        if kapatilabilir > 0:
            result.append({
                'is_avansi_id': avans.id,
                'verilis_tarihi': avans.verilis_tarihi.isoformat(),
                'verilen_tutar': str(avans.verilen_tutar),
                'para_birimi': avans.para_birimi,
                'aciklama': avans.aciklama,
                'mahsup_edilen_toplam_tutar': str(avans.mahsup_edilen_toplam_tutar or '0.00'),
                'iade_edilen_tutar': str(avans.iade_edilen_tutar or '0.00'),
                'kapatilabilir_tutar': str(kapatilabilir),
                'durum': avans.durum
            })

    return jsonify(result), 200

# TODO: Maaş ödemesi iptali (Bu işlem kasa ve avans hareketlerini geri almayı gerektirir, dikkatli yapılmalı)
# @maas_bp.route('/odemeler/<int:odeme_id>/iptal', methods=['POST'])
# @token_required
# @role_required(['admin', 'human_resources'])
# def iptal_maas_odeme(odeme_id):
#     pass
