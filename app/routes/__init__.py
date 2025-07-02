# Bu dosya app/routes klasörünün bir Python paketi olduğunu belirtir.
# Blueprint'ler veya route modülleri buradan yönetilebilir.

from flask import Blueprint

# Kasa modülü için blueprint
kasa_bp = Blueprint('kasa', __name__, url_prefix='/api/v1/kasalar')
from . import kasa_routes


# Cari Hesap modülü için blueprint
cari_hesap_bp = Blueprint('cari_hesap', __name__, url_prefix='/api/v1/cari-hesaplar')
from . import cari_hesap_routes


# Proje modülü için blueprint
proje_bp = Blueprint('proje', __name__, url_prefix='/api/v1/projeler')
from . import proje_routes


# Personel modülü için blueprint
personel_bp = Blueprint('personel', __name__, url_prefix='/api/v1/personeller')
from . import personel_routes


# İş Avansı modülü için blueprint
is_avansi_bp = Blueprint('is_avansi', __name__, url_prefix='/api/v1/is-avanslari')
from . import is_avansi_routes


# Kurban modülü için blueprint
kurban_bp = Blueprint('kurban', __name__, url_prefix='/api/v1/kurbanlar')
from . import kurban_routes


# Auth modülü için blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')
from . import auth_routes


# Maaş modülü için blueprint
maas_bp = Blueprint('maas', __name__, url_prefix='/api/v1/maas')
from . import maas_routes


# Diğer modüller için de benzer blueprint tanımlamaları burada veya
# kendi route dosyalarında yapılabilir.
