from app import app, db
import os

print("--- Rozpoczynam inicjalizację bazy ---")
try:
    with app.app_context():
        # Ścieżka, gdzie baza powinna powstać
        db_path = os.path.join(os.getcwd(), 'local.db')
        print(f"Próbuję utworzyć bazę w: {db_path}")
        
        db.create_all()
        
        if os.path.exists(db_path):
            print("SUKCES: Plik local.db został utworzony!")
        else:
            print("BŁĄD: Plik nie powstał. Sprawdź uprawnienia folderu.")
except Exception as e:
    print(f"Wystąpił błąd krytyczny: {e}")