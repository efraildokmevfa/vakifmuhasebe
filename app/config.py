import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'cok-gizli-bir-anahtar'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://efrail:s19814@127.0.0.1/vakif_db' # Yeni yerleşik MySQL bilgileri
    SQLALCHEMY_TRACK_MODIFICATIONS = False
