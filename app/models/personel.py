from app import db
from app.models.cari_hesap import CariHesap # CariHesap import edildi
from sqlalchemy.orm import relationship

class Personel(db.Model):
    __tablename__ = 'personeller'

    id = db.Column(db.Integer, primary_key=True)
    ad_soyad = db.Column(db.String(150), nullable=False)
    personel_turu = db.Column(db.String(50), nullable=False)  # Türk Personel, Yerli Personel
    pozisyon = db.Column(db.String(100), nullable=True)
    ise_baslama_tarihi = db.Column(db.Date, nullable=True)
    isten_ayrilma_tarihi = db.Column(db.Date, nullable=True)
    aktif = db.Column(db.Boolean, default=True) # Personel aktif mi?

    # Opsiyonel: Her personel bir cari hesap olabilir (maaş takibi, avanslar vb. için)
    # Bu, personelin cari hesaplar arasında da listelenmesini sağlar.
    cari_hesap_id = db.Column(db.Integer, db.ForeignKey('cari_hesaplar.id'), nullable=True, unique=True)
    # `backref` yerine `back_populates` kullanarak çift yönlü ilişkiyi daha net tanımlayabiliriz.
    # CariHesap modelinde de bu ilişkiyi tanımlamak gerekebilir.
    # cari_hesap = relationship("CariHesap", backref=db.backref("personel_ref", uselist=False))
    # Şimdilik tek yönlü bırakalım, CariHesap modelini Personel'den haberdar etmeyelim.
    # Eğer CariHesap üzerinden personele ulaşmak gerekirse, o zaman düzenleriz.
    cari_hesap = relationship("CariHesap")


    # İş avansları ile ilişki (bir personel birden fazla iş avansı alabilir)
    is_avanslari = relationship("IsAvansi", back_populates="personel", lazy='dynamic')


    def __repr__(self):
        return f'<Personel {self.ad_soyad}>'

    def to_dict(self):
        return {
            'id': self.id,
            'ad_soyad': self.ad_soyad,
            'personel_turu': self.personel_turu,
            'pozisyon': self.pozisyon,
            'ise_baslama_tarihi': self.ise_baslama_tarihi.isoformat() if self.ise_baslama_tarihi else None,
            'isten_ayrilma_tarihi': self.isten_ayrilma_tarihi.isoformat() if self.isten_ayrilma_tarihi else None,
            'aktif': self.aktif,
            'cari_hesap_id': self.cari_hesap_id,
            'cari_hesap_bilgileri': self.cari_hesap.to_dict() if self.cari_hesap else None
        }
