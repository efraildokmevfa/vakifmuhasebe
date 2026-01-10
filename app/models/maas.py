from app import db
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.personel import Personel
from app.models.kasa import Kasa
# IsAvansi modeli ile ilişki kurmak için import edelim (MaasAvansMahsubu üzerinden)
# from app.models.is_avansi import IsAvansi # Direkt import yerine string referans kullanılabilir ilişkide

class MaasAvansMahsubu(db.Model):
    __tablename__ = 'maas_avans_mahsubu'
    id = db.Column(db.Integer, primary_key=True)
    maas_odeme_id = db.Column(db.Integer, db.ForeignKey('maas_odemeleri.id'), nullable=False)
    is_avansi_id = db.Column(db.Integer, db.ForeignKey('is_avanslari.id'), nullable=False) # Maaş tipi avans olmalı
    mahsup_edilen_tutar = db.Column(db.Numeric(15, 2), nullable=False)
    mahsup_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    # İlişkiler (MaasOdeme ve IsAvansi modellerinde back_populates ile tanımlanacak)
    maas_odeme = relationship("MaasOdeme", back_populates="mahsup_edilen_avanslar_detay")
    is_avansi = relationship("IsAvansi", back_populates="maas_odemeleri_mahsup") # IsAvansi modelinde bu ilişki tanımlanmalı

    def to_dict(self):
        return {
            'id': self.id,
            'maas_odeme_id': self.maas_odeme_id,
            'is_avansi_id': self.is_avansi_id,
            'avans_bilgisi': self.is_avansi.to_dict() if self.is_avansi else None, # Avans detaylarını da ekleyebiliriz
            'mahsup_edilen_tutar': str(self.mahsup_edilen_tutar),
            'mahsup_tarihi': self.mahsup_tarihi.isoformat()
        }


class MaasOdeme(db.Model):
    __tablename__ = 'maas_odemeleri'

    id = db.Column(db.Integer, primary_key=True)
    personel_id = db.Column(db.Integer, db.ForeignKey('personeller.id'), nullable=False)
    donem_yil = db.Column(db.Integer, nullable=False) # Örn: 2024
    donem_ay = db.Column(db.Integer, nullable=False) # Örn: 3 (Mart)

    brut_maas = db.Column(db.Numeric(15, 2), nullable=True) # Opsiyonel, direkt net üzerinden de gidilebilir
    kesintiler_toplami = db.Column(db.Numeric(15, 2), nullable=True, default=0.00) # SGK, vergi vb.
    # mahsup_edilen_avans_tutari alanı yerine MaasAvansMahsubu ilişkisinden toplam alınacak

    odenecek_net_maas = db.Column(db.Numeric(15, 2), nullable=False) # Hesaplanan, avanslar düşülmeden önceki net
    fiili_odenen_tutar = db.Column(db.Numeric(15, 2), nullable=False) # Avanslar düşüldükten sonra kasadan çıkan net

    odeme_kasa_id = db.Column(db.Integer, db.ForeignKey('kasalar.id'), nullable=False)
    odeme_tarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    para_birimi = db.Column(db.String(10), nullable=False) # Maaşın ödendiği para birimi
    aciklama = db.Column(db.Text, nullable=True)
    durum = db.Column(db.String(50), default="Hesaplandı") # Hesaplandı, Ödendi, Kısmi Ödendi, İptal Edildi

    personel = relationship("Personel")
    kasa = relationship("Kasa")

    # Bir maaş ödemesinde birden fazla avans mahsup edilebilir
    mahsup_edilen_avanslar_detay = relationship("MaasAvansMahsubu", back_populates="maas_odeme", cascade="all, delete-orphan")

    @property
    def toplam_mahsup_edilen_avans(self):
        return db.session.query(db.func.sum(MaasAvansMahsubu.mahsup_edilen_tutar))\
                         .filter(MaasAvansMahsubu.maas_odeme_id == self.id)\
                         .scalar() or 0.00

    def __repr__(self):
        return f'<MaasOdeme ID: {self.id}, Personel: {self.personel_id}, Dönem: {self.donem_ay}/{self.donem_yil}>'

    def to_dict(self):
        return {
            'id': self.id,
            'personel_id': self.personel_id,
            'personel_adi': self.personel.ad_soyad if self.personel else None,
            'donem_yil': self.donem_yil,
            'donem_ay': self.donem_ay,
            'brut_maas': str(self.brut_maas) if self.brut_maas is not None else None,
            'kesintiler_toplami': str(self.kesintiler_toplami or '0.00'),
            'odenecek_net_maas': str(self.odenecek_net_maas),
            'toplam_mahsup_edilen_avans': str(self.toplam_mahsup_edilen_avans),
            'fiili_odenen_tutar': str(self.fiili_odenen_tutar),
            'odeme_kasa_id': self.odeme_kasa_id,
            'odeme_kasa_adi': self.kasa.kasa_adi if self.kasa else None,
            'odeme_tarihi': self.odeme_tarihi.isoformat(),
            'para_birimi': self.para_birimi,
            'aciklama': self.aciklama,
            'durum': self.durum,
            'mahsup_edilen_avanslar_detay': [m.to_dict() for m in self.mahsup_edilen_avanslar_detay]
        }
