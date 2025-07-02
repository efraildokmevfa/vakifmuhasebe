from app import db
from sqlalchemy.orm import relationship
from datetime import datetime

class KasaHareketi(db.Model):
    __tablename__ = 'kasa_hareketleri'

    id = db.Column(db.Integer, primary_key=True)
    kasa_id = db.Column(db.Integer, db.ForeignKey('kasalar.id'), nullable=False)
    tarih = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    islem_tipi = db.Column(db.String(100), nullable=False)
    # Örn: "Kurban Bağışı", "İş Avansı Verildi", "İş Avansı İade", "Proje Harcaması", "Maaş Ödemesi", "Manuel Giriş", "Manuel Çıkış"
    aciklama = db.Column(db.Text, nullable=True)
    tutar = db.Column(db.Numeric(15, 2), nullable=False) # Pozitif: gelir, Negatif: gider

    # İşlemin kaynağını/referansını belirtmek için (opsiyonel ama çok faydalı)
    # Örneğin bir KurbanBagisi ID'si, IsAvansi ID'si, ProjeHarcamasi ID'si vb.
    referans_tablo = db.Column(db.String(50), nullable=True) # Örn: 'kurban_bagislari', 'is_avanslari'
    referans_id = db.Column(db.Integer, nullable=True)

    # İşlemi yapan kullanıcı (opsiyonel, eğer User modeli varsa)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    kasa = relationship("Kasa", back_populates="hareketler")
    user = relationship("User") # Eğer user_id kullanılıyorsa

    def __repr__(self):
        return f'<KasaHareketi ID: {self.id}, Kasa: {self.kasa_id}, Tutar: {self.tutar}, Tip: {self.islem_tipi}>'

    def to_dict(self):
        return {
            'id': self.id,
            'kasa_id': self.kasa_id,
            'kasa_adi': self.kasa.kasa_adi if self.kasa else None,
            'tarih': self.tarih.isoformat(),
            'islem_tipi': self.islem_tipi,
            'aciklama': self.aciklama,
            'tutar': str(self.tutar),
            'referans_tablo': self.referans_tablo,
            'referans_id': self.referans_id,
            'user_id': self.user_id,
            'kullanici_adi': self.user.username if self.user else None
        }


class Kasa(db.Model):
    __tablename__ = 'kasalar'

    id = db.Column(db.Integer, primary_key=True)
    kasa_adi = db.Column(db.String(100), nullable=False, unique=True)
    para_birimi = db.Column(db.String(10), nullable=False)
    bakiye = db.Column(db.Numeric(15, 2), nullable=False, default=0.00) # Bu bakiye, hareketlerden hesaplanarak güncellenmeli

    hareketler = relationship("KasaHareketi", back_populates="kasa", lazy='dynamic', order_by="desc(KasaHareketi.tarih)")

    def __repr__(self):
        return f'<Kasa {self.kasa_adi} ({self.para_birimi})>'

    def to_dict(self):
        return {
            'id': self.id,
            'kasa_adi': self.kasa_adi,
            'para_birimi': self.para_birimi,
            'bakiye': str(self.bakiye) # JSON uyumluluğu için string'e çevir
        }
