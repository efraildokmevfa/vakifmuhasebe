from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # Eklendi
from app.config import Config

db = SQLAlchemy()
migrate = Migrate() # Eklendi

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db) # Eklendi

    # Blueprint'leri ve route'ları burada kaydedeceğiz
    # Örneğin:
    # from app.routes.main import bp as main_bp
    # app.register_blueprint(main_bp)

    # Kasa Rotaları
    from app.routes import kasa_bp # app.routes.__init__ dosyasından import ediyoruz
    app.register_blueprint(kasa_bp) # Prefix zaten blueprint tanımında mevcut

    # Cari Hesap Rotaları
    from app.routes import cari_hesap_bp # app.routes.__init__ dosyasından import ediyoruz
    app.register_blueprint(cari_hesap_bp) # Prefix zaten blueprint tanımında mevcut

    # Proje Rotaları
    from app.routes import proje_bp
    app.register_blueprint(proje_bp)

    # Personel Rotaları
    from app.routes import personel_bp
    app.register_blueprint(personel_bp)

    # İş Avansı Rotaları
    from app.routes import is_avansi_bp
    app.register_blueprint(is_avansi_bp)

    # Kurban Rotaları
    from app.routes import kurban_bp
    app.register_blueprint(kurban_bp)

    # Auth Rotaları
    from app.routes import auth_bp
    app.register_blueprint(auth_bp)

    # Maaş Rotaları
    from app.routes import maas_bp
    app.register_blueprint(maas_bp)

    # Diğer modüllerin blueprint'leri eklenecek...

    @app.route('/')
    def hello():
        return "Muhasebe Uygulaması Ana Sayfa!"

    return app
