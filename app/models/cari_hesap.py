from app import db
from sqlalchemy.orm import relationship
from datetime import datetime

class CariHesapHareketi(db.Model):
    __tablename__ = 'cari_hesap_hareketleri'

    id = db.Column(db.Integer, primary_key=True)
    cari_hesap_id = db.Column(db.Integer, db.ForeignKey('cari_hesaplar.id'), nullable=False)
    tarih = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    islem_tipi = db.Column(db.String(100), nullable=False)
    # Örn: "Fatura", "Ödeme", "Tahsilat", "Avans Mahsubu", "Maaş Ödemesi", "Manuel Borç", "Manuel Alacak"
    aciklama = db.Column(db.Text, nullable=True)
    # Tutar: Pozitif ise cari borçlanır (bizim alacağımız artar), Negatif ise cari alacaklanır (bizim borcumuz artar).
    # VEYA: 'borc_tutari' ve 'alacak_tutari' diye iki ayrı kolon olabilir.
    # Tek 'tutar' kolonu ve 'islem_yonu' (borc/alacak) kolonu da olabilir.
    # Şimdilik tek 'tutar' kullanalım: Pozitif = Cari Borçlandı, Negatif = Cari Alacaklandı.
    tutar = db.Column(db.Numeric(15, 2), nullable=False)

    # İşlemin kaynağını/referansını belirtmek için
    referans_tablo = db.Column(db.String(50), nullable=True) # Örn: 'faturalar', 'odemeler', 'is_avanslari'
    referans_id = db.Column(db.Integer, nullable=True)

    # İşlemi yapan kullanıcı (opsiyonel)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    cari_hesap = relationship("CariHesap", back_populates="hareketler")
    user = relationship("User")

    def __repr__(self):
        return f'<CariHesapHareketi ID: {self.id}, Cari ID: {self.cari_hesap_id}, Tutar: {self.tutar}>'

    def to_dict(self):
        return {
            'id': self.id,
            'cari_hesap_id': self.cari_hesap_id,
            'cari_hesap_adi': self.cari_hesap.hesap_adi if self.cari_hesap else None,
            'tarih': self.tarih.isoformat(),
            'islem_tipi': self.islem_tipi,
            'aciklama': self.aciklama,
            'tutar': str(self.tutar), # Pozitif: Borç, Negatif: Alacak
            'referans_tablo': self.referans_tablo,
            'referans_id': self.referans_id,
            'user_id': self.user_id,
            'kullanici_adi': self.user.username if self.user else None
        }


class CariHesap(db.Model):
    __tablename__ = 'cari_hesaplar'

    id = db.Column(db.Integer, primary_key=True)
    hesap_adi = db.Column(db.String(150), nullable=False)
    hesap_turu = db.Column(db.String(50), nullable=False)  # Tedarikçi, Bağışçı, Personel, Diğer
    bakiye = db.Column(db.Numeric(15, 2), nullable=False, default=0.00) # Bu bakiye, hareketlerden hesaplanarak güncellenmeli
    # Bakiye: Pozitif ise cari bize borçlu, Negatif ise biz cariye borçluyuz.
    para_birimi = db.Column(db.String(10), nullable=False, default='TRY') # Varsayılan TRY
    vergi_no = db.Column(db.String(20), nullable=True)
    adres = db.Column(db.String(255), nullable=True)
    telefon = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    aktif = db.Column(db.Boolean, default=True) # Cari hesap aktif mi?

    # Personel ile birebir ilişki (opsiyonel)
    # Bir personel bir cari hesap olabilir ama bir cari hesap birden fazla personel olamaz.
    # Bu ilişki Personel modelinde tanımlanacak. (Personel.cari_hesap -> CariHesap)
    # Personel modeli bu cari hesaba Personel.cari_hesap_id ile bağlanır.
    # Eğer CariHesap'tan Personel'e ulaşmak gerekirse:
    # personel_ref = relationship("Personel", back_populates="cari_hesap", uselist=False)


    hareketler = relationship("CariHesapHareketi", back_populates="cari_hesap", lazy='dynamic', order_by="desc(CariHesapHareketi.tarih)")

    def __repr__(self):
        return f'<CariHesap {self.hesap_adi} ({self.hesap_turu})>'

    def to_dict(self):
        return {
            'id': self.id,
            'hesap_adi': self.hesap_adi,
            'hesap_turu': self.hesap_turu,
            'bakiye': str(self.bakiye),
            'para_birimi': self.para_birimi,
            'vergi_no': self.vergi_no,
            'adres': self.adres,
            'telefon': self.telefon,
            'email': self.email,
            'aktif': self.aktif
        }
