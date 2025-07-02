from app import db
from sqlalchemy.orm import relationship
from datetime import datetime

class ProjeTuru(db.Model):
    __tablename__ = 'proje_turleri'
    id = db.Column(db.Integer, primary_key=True)
    tur_adi = db.Column(db.String(100), nullable=False, unique=True)
    aciklama = db.Column(db.Text, nullable=True)

    projeler = relationship("Proje", back_populates="proje_turu", lazy='dynamic')

    def __repr__(self):
        return f'<ProjeTuru {self.tur_adi}>'

    def to_dict(self):
        return {
            'id': self.id,
            'tur_adi': self.tur_adi,
            'aciklama': self.aciklama
        }

class ProjeHarcamasi(db.Model):
    __tablename__ = 'proje_harcamalari'
    id = db.Column(db.Integer, primary_key=True)
    proje_id = db.Column(db.Integer, db.ForeignKey('projeler.id'), nullable=False)
    kasa_id = db.Column(db.Integer, db.ForeignKey('kasalar.id'), nullable=False) # Harcamanın yapıldığı kasa
    harcama_tarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    aciklama = db.Column(db.Text, nullable=False)
    tutar = db.Column(db.Numeric(15, 2), nullable=False)
    para_birimi = db.Column(db.String(10), nullable=False) # Harcama anındaki para birimi

    # İşlemi yapan kullanıcı (opsiyonel)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    proje = relationship("Proje", back_populates="harcamalar")
    kasa = relationship("Kasa", foreign_keys=[kasa_id])
    user = relationship("User")
    mutevelli_cari_hesap = relationship("CariHesap", foreign_keys=[mutevelli_cari_id])

    # odeme_kaynagi ve mutevelli_cari_id alanları eklenecek
    odeme_kaynagi = db.Column(db.String(50), nullable=False, default="Kasa") # Kasa, Mütevelli
    mutevelli_cari_id = db.Column(db.Integer, db.ForeignKey('cari_hesaplar.id'), nullable=True)


    def __repr__(self):
        return f'<ProjeHarcamasi ID: {self.id}, Proje: {self.proje_id}, Tutar: {self.tutar}>'

    def to_dict(self):
        return {
            'id': self.id,
            'proje_id': self.proje_id,
            'proje_adi': self.proje.proje_adi if self.proje else None,
            'kasa_id': self.kasa_id,
            'kasa_adi': self.kasa.kasa_adi if self.kasa else None,
            'harcama_tarihi': self.harcama_tarihi.isoformat(),
            'aciklama': self.aciklama,
            'tutar': str(self.tutar),
            'para_birimi': self.para_birimi,
            'user_id': self.user_id,
            'kullanici_adi': self.user.username if self.user else None,
            'odeme_kaynagi': self.odeme_kaynagi,
            'mutevelli_cari_id': self.mutevelli_cari_id,
            'mutevelli_adi': self.mutevelli_cari_hesap.hesap_adi if self.mutevelli_cari_hesap else None
        }


class Proje(db.Model):
    __tablename__ = 'projeler'

    id = db.Column(db.Integer, primary_key=True)
    proje_adi = db.Column(db.String(200), nullable=False, unique=True)
    proje_aciklamasi = db.Column(db.Text, nullable=True)

    proje_turu_id = db.Column(db.Integer, db.ForeignKey('proje_turleri.id'), nullable=True) # Nullable olabilir başlangıçta
    proje_turu = relationship("ProjeTuru", back_populates="projeler")

    baslangic_tarihi = db.Column(db.Date, nullable=True, default=datetime.utcnow)
    bitis_tarihi = db.Column(db.Date, nullable=True)
    proje_butcesi = db.Column(db.Numeric(15, 2), nullable=True)
    # harcanan_tutar alanı artık dinamik olarak harcamalardan hesaplanacak
    # harcanan_tutar = db.Column(db.Numeric(15, 2), nullable=True, default=0.00)
    durum = db.Column(db.String(50), nullable=False, default='Planlandı')  # Planlandı, Devam Ediyor, Tamamlandı, İptal Edildi

    harcamalar = relationship("ProjeHarcamasi", back_populates="proje", lazy='dynamic', cascade="all, delete-orphan")

    @property
    def toplam_harcanan(self):
        # TODO: Farklı para birimlerindeki harcamalar varsa ana bir para birimine çevrilerek toplanmalı.
        # Şimdilik aynı para biriminde olduğunu varsayıyoruz veya proje bazında tek para birimi.
        # Ya da proje modeline bir 'ana_para_birimi' alanı eklenip, harcamalar o birime çevrilebilir.
        # Bu örnekte, harcamaların kendi para birimlerinde tutulduğunu ve burada sadece bir toplam gösterildiğini varsayalım.
        # Daha karmaşık bir senaryoda, her harcamanın proje ana para birimine çevrilmesi gerekir.
        total = db.session.query(db.func.sum(ProjeHarcamasi.tutar))\
                          .filter(ProjeHarcamasi.proje_id == self.id)\
                          .scalar()
        return total or 0.00

    def __repr__(self):
        return f'<Proje {self.proje_adi}>'

    def to_dict(self):
        return {
            'id': self.id,
            'proje_adi': self.proje_adi,
            'proje_aciklamasi': self.proje_aciklamasi,
            'proje_turu_id': self.proje_turu_id,
            'proje_turu_adi': self.proje_turu.tur_adi if self.proje_turu else None,
            'baslangic_tarihi': self.baslangic_tarihi.isoformat() if self.baslangic_tarihi else None,
            'bitis_tarihi': self.bitis_tarihi.isoformat() if self.bitis_tarihi else None,
            'proje_butcesi': str(self.proje_butcesi) if self.proje_butcesi is not None else None,
            'toplam_harcanan': str(self.toplam_harcanan), # Dinamik property kullanılıyor
            'durum': self.durum,
            # İsteğe bağlı olarak son N harcama da eklenebilir
            # 'son_harcamalar': [h.to_dict() for h in self.harcamalar.limit(5).all()]
        }
