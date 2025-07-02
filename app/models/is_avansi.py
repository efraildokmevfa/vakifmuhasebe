from app import db
from app.models.personel import Personel # Personel modelini import ediyoruz
from app.models.kasa import Kasa # Kasa modelini import ediyoruz (opsiyonel, avansın çıktığı kasayı kaydetmek için)
from sqlalchemy.orm import relationship
from datetime import datetime

class IsAvansi(db.Model):
    __tablename__ = 'is_avanslari'

    id = db.Column(db.Integer, primary_key=True)
    personel_id = db.Column(db.Integer, db.ForeignKey('personeller.id'), nullable=False)
    verilis_tarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    verilen_tutar = db.Column(db.Numeric(15, 2), nullable=False)
    para_birimi = db.Column(db.String(10), nullable=False)
    aciklama = db.Column(db.Text, nullable=True)
    avans_tipi = db.Column(db.String(20), nullable=False, default='İş') # İş, Maaş
    durum = db.Column(db.String(50), nullable=False, default='Verildi')
    # Durumlar: Verildi, Harcama Beyan Edildi, Kısmi İade, Tamamlandı (Kapandı), Kısmen Mahsup Edildi, İptal Edildi

    kasa_id = db.Column(db.Integer, db.ForeignKey('kasalar.id'), nullable=False) # Avansın çıktığı kasa zorunlu

    personel = relationship("Personel", back_populates="is_avanslari")
    kasa = relationship("Kasa")

    # Sadece "İş" tipi avanslar için harcamalar. Maaş avansları doğrudan mahsup edilir.
    harcamalar = relationship("IsAvansiHarcamasi",
                              primaryjoin="and_(IsAvansi.id==IsAvansiHarcamasi.is_avansi_id, IsAvansi.avans_tipi=='İş')",
                              back_populates="is_avansi",
                              lazy='dynamic',
                              cascade="all, delete-orphan")

    iade_edilen_tutar = db.Column(db.Numeric(15, 2), default=0.00)
    # Maaş avansları için: Maaş ödemelerinde ne kadarının mahsup edildiği.
    mahsup_edilen_toplam_tutar = db.Column(db.Numeric(15, 2), default=0.00)
    mahsuplasma_notu = db.Column(db.Text, nullable=True) # Genel mahsuplaşma notları

    # Maaş ödemeleri ile ilişki (Many-to-Many through MaasAvansMahsubu)
    maas_odemeleri_mahsup = relationship("MaasAvansMahsubu", back_populates="is_avansi", cascade="all, delete-orphan")


    @property
    def toplam_harcanan_is_avansi(self):
        if self.avans_tipi == 'İş':
            return db.session.query(db.func.sum(IsAvansiHarcamasi.harcama_tutari))\
                             .filter(IsAvansiHarcamasi.is_avansi_id == self.id)\
                             .scalar() or 0.00
        return 0.00

    @property
    def kapatilabilir_tutar(self):
        """Avansın henüz kapatılmamış (harcanmamış, iade edilmemiş, mahsup edilmemiş) tutarı"""
        if self.avans_tipi == 'İş':
            return self.verilen_tutar - self.toplam_harcanan_is_avansi - (self.iade_edilen_tutar or 0.00)
        elif self.avans_tipi == 'Maaş':
            return self.verilen_tutar - (self.mahsup_edilen_toplam_tutar or 0.00) - (self.iade_edilen_tutar or 0.00)
        return self.verilen_tutar


    def __repr__(self):
        return f'<IsAvansi ID: {self.id}, Tip: {self.avans_tipi}, Personel: {self.personel_id}, Tutar: {self.verilen_tutar} {self.para_birimi}>'

    def to_dict(self):
        return {
            'id': self.id,
            'personel_id': self.personel_id,
            'personel_ad_soyad': self.personel.ad_soyad if self.personel else None,
            'verilis_tarihi': self.verilis_tarihi.isoformat(),
            'verilen_tutar': str(self.verilen_tutar),
            'para_birimi': self.para_birimi,
            'aciklama': self.aciklama,
            'avans_tipi': self.avans_tipi,
            'durum': self.durum,
            'kasa_id': self.kasa_id,
            'kasa_adi': self.kasa.kasa_adi if self.kasa else None,
            'toplam_harcanan_is_avansi': str(self.toplam_harcanan_is_avansi),
            'iade_edilen_tutar': str(self.iade_edilen_tutar or '0.00'),
            'mahsup_edilen_toplam_tutar': str(self.mahsup_edilen_toplam_tutar or '0.00'),
            'kapatilabilir_tutar': str(self.kapatilabilir_tutar),
            'mahsuplasma_notu': self.mahsuplasma_notu,
            'harcamalar': [harcama.to_dict() for harcama in self.harcamalar.all()] if self.avans_tipi == 'İş' else []
        }


class IsAvansiHarcamasi(db.Model):
    __tablename__ = 'is_avansi_harcamalari'

    id = db.Column(db.Integer, primary_key=True)
    is_avansi_id = db.Column(db.Integer, db.ForeignKey('is_avanslari.id'), nullable=False)
    harcama_tarihi = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    harcama_tutari = db.Column(db.Numeric(15, 2), nullable=False)
    # Harcamanın yapıldığı para birimi, avansın para birimiyle aynı olmayabilir.
    # Bu durumda kur dönüşümü gerekebilir. Şimdilik avansla aynı para birimi varsayalım.
    # harcama_para_birimi = db.Column(db.String(10), nullable=False)
    harcama_aciklamasi = db.Column(db.Text, nullable=True)
    belge_no = db.Column(db.String(100), nullable=True) # Fatura, fiş no vb.
    # Proje ile ilişkilendirme (opsiyonel)
    # proje_id = db.Column(db.Integer, db.ForeignKey('projeler.id'), nullable=True)

    is_avansi = relationship("IsAvansi", back_populates="harcamalar")
    # proje = relationship("Proje") # Eğer proje_id kullanılırsa

    def __repr__(self):
        return f'<IsAvansiHarcamasi ID: {self.id}, Avans ID: {self.is_avansi_id}, Tutar: {self.harcama_tutari}>'

    def to_dict(self):
        return {
            'id': self.id,
            'is_avansi_id': self.is_avansi_id,
            'harcama_tarihi': self.harcama_tarihi.isoformat(),
            'harcama_tutari': str(self.harcama_tutari),
            'harcama_aciklamasi': self.harcama_aciklamasi,
            'belge_no': self.belge_no,
            # 'proje_id': self.proje_id
        }
