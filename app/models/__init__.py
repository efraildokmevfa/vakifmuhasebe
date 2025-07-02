# Bu dosya app/models klasörünün bir Python paketi olduğunu belirtir.
# Modeller oluşturulduğunda buradan import edilebilirler.
from .kasa import Kasa, KasaHareketi
from .cari_hesap import CariHesap, CariHesapHareketi
from .proje import Proje, ProjeTuru, ProjeHarcamasi # ProjeTuru ve ProjeHarcamasi eklendi
from .personel import Personel
from .is_avansi import IsAvansi, IsAvansiHarcamasi
from .kurban import KurbanTuru, KurbanBagisi
from .auth import User, Role, user_roles
from .maas import MaasOdeme, MaasAvansMahsubu # Maaş modelleri eklendi

# Veya temel db objesini buradan da sağlayabiliriz:
# from app import db
