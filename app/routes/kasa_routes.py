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
    Kasa.query.get_or_404(kasa_id)

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

    query = KasaHareketi.query.filter_by(kasa_id=kasa_id)

    if tarih_baslangic_str:
        try:
            tarih_baslangic = datetime.fromisoformat(tarih_baslangic_str)
            query = query.filter(KasaHareketi.tarih >= tarih_baslangic)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_baslangic formatı.'}), 400
    if tarih_bitis_str:
        try:
            tarih_bitis = datetime.fromisoformat(tarih_bitis_str).replace(hour=23, minute=59, second=59)
            query = query.filter(KasaHareketi.tarih <= tarih_bitis)
        except ValueError:
            return jsonify({'message': 'Geçersiz tarih_bitis formatı.'}), 400

    if islem_tipi_filter:
        query = query.filter(KasaHareketi.islem_tipi.ilike(f"%{islem_tipi_filter}%"))
    if referans_tablo_filter:
        query = query.filter(KasaHareketi.referans_tablo == referans_tablo_filter)
    if referans_id_filter:
        query = query.filter(KasaHareketi.referans_id == referans_id_filter)
    if user_id_filter:
        query = query.filter(KasaHareketi.user_id == user_id_filter)

    valid_sort_fields = {
        'tarih': KasaHareketi.tarih,
        'tutar': KasaHareketi.tutar,
        'islem_tipi': KasaHareketi.islem_tipi,
        'id': KasaHareketi.id
    }
    sort_column = valid_sort_fields.get(sirala_alan, KasaHareketi.tarih)
    if sirala_yon == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc(), KasaHareketi.id.desc()) # Tarih aynıysa ID'ye göre de sırala

    paginated_hareketler = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'hareketler': [h.to_dict() for h in paginated_hareketler.items],
        'total': paginated_hareketler.total,
        'page': paginated_hareketler.page,
        'per_page': paginated_hareketler.per_page,
        'total_pages': paginated_hareketler.pages
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


# --- Kasalar Arası Virman ---
@kasa_bp.route('/virman', methods=['POST'])
@token_required
# @role_required(['admin', 'accountant'])
def kasa_virman():
    data = request.get_json()
    required_fields = ['kaynak_kasa_id', 'hedef_kasa_id', 'tutar', 'para_birimi_kaynak']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'Eksik bilgi: {field} zorunludur.'}), 400

    try:
        kaynak_kasa_id = int(data['kaynak_kasa_id'])
        hedef_kasa_id = int(data['hedef_kasa_id'])
        tutar_kaynak = Decimal(data['tutar'])
        if tutar_kaynak <= 0: raise ValueError("Virman tutarı pozitif olmalı.")
    except (ValueError, TypeError):
        return jsonify({'message': 'Geçersiz ID veya tutar formatı.'}), 400

    if kaynak_kasa_id == hedef_kasa_id:
        return jsonify({'message': 'Kaynak ve hedef kasa aynı olamaz.'}), 400

    kaynak_kasa = Kasa.query.get(kaynak_kasa_id)
    hedef_kasa = Kasa.query.get(hedef_kasa_id)

    if not kaynak_kasa: return jsonify({'message': 'Kaynak kasa bulunamadı.'}), 404
    if not hedef_kasa: return jsonify({'message': 'Hedef kasa bulunamadı.'}), 404

    para_birimi_kaynak = data['para_birimi_kaynak'].upper()
    para_birimi_hedef = data.get('para_birimi_hedef', hedef_kasa.para_birimi).upper() # Hedef PB belirtilmezse hedef kasanın PB'si
    kur_str = data.get('kur') # Eğer PB'ler farklıysa kur zorunlu olacak

    if kaynak_kasa.para_birimi != para_birimi_kaynak:
        return jsonify({'message': f'Belirtilen kaynak para birimi ({para_birimi_kaynak}) ile kaynak kasanın ({kaynak_kasa.kasa_adi}) para birimi ({kaynak_kasa.para_birimi}) uyuşmuyor.'}), 400

    if kaynak_kasa.bakiye < tutar_kaynak:
        return jsonify({'message': f'Kaynak kasada ({kaynak_kasa.kasa_adi}) yeterli bakiye yok. Talep edilen: {tutar_kaynak}, Mevcut: {kaynak_kasa.bakiye}'}), 400

    tutar_hedef = tutar_kaynak
    if para_birimi_kaynak != para_birimi_hedef:
        if not kur_str:
            return jsonify({'message': 'Para birimleri farklıysa kur belirtilmelidir (1 hedef birim = X kaynak birim).'}), 400
        try:
            kur = Decimal(kur_str)
            if kur <= 0: raise ValueError("Kur pozitif olmalı.")
            # Kur tanımı: 1 hedef PB = `kur` * kaynak PB. Yani Kaynak Tutar / Kur = Hedef Tutar
            # Örnek: USD(kaynak) -> EUR(hedef). Kur=0.92 (1 EUR = 0.92 USD ise yanlış, 1 USD = 0.92 EUR olmalı)
            # Ya da: 100 USD virman yapılacak, 1 EUR = 1.08 USD. Kur = 1.08.  Hedef tutar = 100 USD / 1.08 USD/EUR = 92.59 EUR
            # Kullanıcıdan kuru "1 hedef_pb = X kaynak_pb" olarak alalım.
            # Yani, 1 EUR = 1.08 USD ise, kur = 1.08. Hedef tutar = Kaynak Tutar / Kur
            # Eğer kur "1 kaynak_pb = X hedef_pb" ise, Hedef tutar = Kaynak Tutar * Kur
            # Plandaki tanım: `kur` (1 hedef birim kaç kaynak birim ediyor) -> Bu durumda Kaynak Tutar / Kur
            # Eğer planı "1 kaynak birim kaç hedef birim ediyor" olarak anlarsak Kaynak Tutar * Kur
            # Daha açık olması için kullanıcıdan "hedef_tutar" da alınabilir veya kurun yönü netleştirilmeli.
            # Şimdilik plandaki gibi (1 hedef = X kaynak) kabul edelim: tutar_hedef = tutar_kaynak / kur
            # Veya daha basiti, eğer kur "hedef_pb / kaynak_pb" oranı ise: tutar_hedef = tutar_kaynak * kur
            # Gelen kurun neyi ifade ettiğini netleştirmek önemli.
            # Varsayım: Kullanıcı "1 Kaynak PB = X Hedef PB" olarak kur giriyor. Yani USD'den EUR'ya ise 1 USD = 0.92 EUR ise kur=0.92
            tutar_hedef = tutar_kaynak * kur
        except (ValueError, TypeError):
            return jsonify({'message': 'Geçersiz kur formatı.'}), 400
        if hedef_kasa.para_birimi != para_birimi_hedef:
             return jsonify({'message': f'Belirtilen hedef para birimi ({para_birimi_hedef}) ile hedef kasanın ({hedef_kasa.kasa_adi}) para birimi ({hedef_kasa.para_birimi}) uyuşmuyor.'}), 400
    else: # Para birimleri aynıysa kur 1'dir
        if hedef_kasa.para_birimi != para_birimi_kaynak: # Bu durum yukarıda kaynak kasa kontrolünde yakalanmalıydı ama yine de...
            return jsonify({'message': f'Hedef kasa ({hedef_kasa.kasa_adi}) para birimi ({hedef_kasa.para_birimi}), kaynak para birimiyle ({para_birimi_kaynak}) aynı olmalıydı (kur belirtilmedi).'}), 400
        kur = Decimal('1.0')


    aciklama_kaynak = data.get('aciklama', f"{hedef_kasa.kasa_adi} kasasına virman.") + f" (Hedef Kasa ID: {hedef_kasa.id})"
    aciklama_hedef = data.get('aciklama', f"{kaynak_kasa.kasa_adi} kasasından virman.") + f" (Kaynak Kasa ID: {kaynak_kasa.id})"
    if para_birimi_kaynak != para_birimi_hedef:
        aciklama_kaynak += f" Kur: {kur}"
        aciklama_hedef += f" Kur: {kur}"


    try:
        # 1. Kaynak kasadan çıkış
        h_kaynak = add_kasa_hareketi(
            kasa_id=kaynak_kasa.id,
            tutar=-tutar_kaynak, # Gider
            islem_tipi="Kasalar Arası Virman (Çıkış)",
            aciklama=aciklama_kaynak,
            referans_tablo='kasalar', # Hedef kasaya referans
            referans_id=hedef_kasa.id,
            user_id=g.current_user.id,
            commit_session=False
        )
        # 2. Hedef kasaya giriş
        h_hedef = add_kasa_hareketi(
            kasa_id=hedef_kasa.id,
            tutar=tutar_hedef, # Gelir
            islem_tipi="Kasalar Arası Virman (Giriş)",
            aciklama=aciklama_hedef,
            referans_tablo='kasalar', # Kaynak kasaya referans
            referans_id=kaynak_kasa.id,
            user_id=g.current_user.id,
            commit_session=False
        )
        db.session.commit()
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Virman işlemi sırasında hata: {str(e)}'}), 500

    return jsonify({
        'message': 'Kasalar arası virman başarıyla tamamlandı.',
        'kaynak_kasa_son_bakiye': str(kaynak_kasa.bakiye),
        'hedef_kasa_son_bakiye': str(hedef_kasa.bakiye),
        'kaynak_hareket_id': h_kaynak.id,
        'hedef_hareket_id': h_hedef.id
    }), 200
