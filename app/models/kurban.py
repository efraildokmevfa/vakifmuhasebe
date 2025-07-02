from app import db
from app.models.kasa import Kasa # Kasa ile ilişki için
# from app.models.cari_hesap import CariHesap # Bağışçı bir cari hesap olabilir (opsiyonel)
from sqlalchemy.orm import relationship
from datetime import datetime

class KurbanTuru(db.Model):
    __tablename__ = 'kurban_turleri'
    id = db.Column(db.Integer, primary_key=True)
    tur_adi = db.Column(db.String(100), nullable=False, unique=True) # Vacip, Sadaka, Şükür, Akika
    aciklama = db.Column(db.Text, nullable=True)

    bagislar = relationship("KurbanBagisi", back_populates="kurban_turu", lazy='dynamic')

    def __repr__(self):
        return f'<KurbanTuru {self.tur_adi}>'

    def to_dict(self):
        return {
            'id': self.id,
            'tur_adi': self.tur_adi,
            'aciklama': self.aciklama
        }

class KurbanBagisi(db.Model):
    __tablename__ = 'kurban_bagislari'

    id = db.Column(db.Integer, primary_key=True)

    # Bağışçı bilgileri
    bagisci_adi = db.Column(db.String(150), nullable=False) # Ad Soyad veya Kurum Adı
    bagisci_telefon = db.Column(db.String(20), nullable=True)
    bagisci_email = db.Column(db.String(100), nullable=True)
    # Alternatif olarak CariHesap ile ilişkilendirilebilir:
    # cari_hesap_id = db.Column(db.Integer, db.ForeignKey('cari_hesaplar.id'), nullable=True)
    # cari_hesap = relationship("CariHesap")

    bagis_tarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    bagis_tutari = db.Column(db.Numeric(15, 2), nullable=False)
    para_birimi = db.Column(db.String(10), nullable=False)

    kurban_turu_id = db.Column(db.Integer, db.ForeignKey('kurban_turleri.id'), nullable=False)
    kurban_turu = relationship("KurbanTuru", back_populates="bagislar")

    hayvan_turu = db.Column(db.String(50), nullable=False)  # Küçükbaş, Büyükbaş Hisse
    hisse_adedi = db.Column(db.Integer, nullable=False, default=1) # Küçükbaş için 1, Büyükbaş için 1-7

    # Kurban vekaleti verenlerin isimleri (birden fazla olabilir, özellikle hisselerde)
    # Basit bir çözüm olarak string içinde virgülle ayrılmış isimler veya JSON listesi olabilir.
    # Daha gelişmiş bir çözüm için ayrı bir VekaletSahibi modeli oluşturulabilir.
    vekalet_sahipleri = db.Column(db.Text, nullable=True) # Örn: "Ahmet Yılmaz, Ayşe Kaya"

    kesim_durumu = db.Column(db.Boolean, default=False) # Kesildi mi?
    kesim_tarihi = db.Column(db.DateTime, nullable=True)
    kesim_yeri = db.Column(db.String(200), nullable=True)
    kesim_masrafi = db.Column(db.Numeric(15, 2), nullable=True, default=0.00)
    # Kesim masrafının hangi kasadan ödendiği (opsiyonel)
    kesim_masraf_kasa_id = db.Column(db.Integer, db.ForeignKey('kasalar.id'), nullable=True)

    sahibine_bilgi_verildi = db.Column(db.Boolean, default=False)
    bilgilendirme_tarihi = db.Column(db.DateTime, nullable=True)

    aciklama = db.Column(db.Text, nullable=True) # Genel açıklamalar, notlar

    # Bağışın hangi kasaya girdiği
    gelir_kasa_id = db.Column(db.Integer, db.ForeignKey('kasalar.id'), nullable=False)

    gelir_kasa = relationship("Kasa", foreign_keys=[gelir_kasa_id])
    kesim_masraf_kasa = relationship("Kasa", foreign_keys=[kesim_masraf_kasa_id])


    def __repr__(self):
        return f'<KurbanBagisi ID: {self.id}, Bağışçı: {self.bagisci_adi}, Tutar: {self.bagis_tutari} {self.para_birimi}>'

    def to_dict(self):
        return {
            'id': self.id,
            'bagisci_adi': self.bagisci_adi,
            'bagisci_telefon': self.bagisci_telefon,
            'bagisci_email': self.bagisci_email,
            # 'cari_hesap_id': self.cari_hesap_id,
            'bagis_tarihi': self.bagis_tarihi.isoformat(),
            'bagis_tutari': str(self.bagis_tutari),
            'para_birimi': self.para_birimi,
            'kurban_turu_id': self.kurban_turu_id,
            'kurban_turu_adi': self.kurban_turu.tur_adi if self.kurban_turu else None,
            'hayvan_turu': self.hayvan_turu,
            'hisse_adedi': self.hisse_adedi,
            'vekalet_sahipleri': self.vekalet_sahipleri,
            'kesim_durumu': self.kesim_durumu,
            'kesim_tarihi': self.kesim_tarihi.isoformat() if self.kesim_tarihi else None,
            'kesim_yeri': self.kesim_yeri,
            'kesim_masrafi': str(self.kesim_masrafi) if self.kesim_masrafi is not None else '0.00',
            'kesim_masraf_kasa_id': self.kesim_masraf_kasa_id,
            'kesim_masraf_kasa_adi': self.kesim_masraf_kasa.kasa_adi if self.kesim_masraf_kasa else None,
            'sahibine_bilgi_verildi': self.sahibine_bilgi_verildi,
            'bilgilendirme_tarihi': self.bilgilendirme_tarihi.isoformat() if self.bilgilendirme_tarihi else None,
            'aciklama': self.aciklama,
            'gelir_kasa_id': self.gelir_kasa_id,
            'gelir_kasa_adi': self.gelir_kasa.kasa_adi if self.gelir_kasa else None
        }
