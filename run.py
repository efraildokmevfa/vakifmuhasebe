from app import create_app, db

app = create_app()

if __name__ == '__main__':
    # Veritabanı tablolarını oluşturmak için (eğer henüz yoksa)
    # with app.app_context():
    #     db.create_all()
    app.run(debug=True)
