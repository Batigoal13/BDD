import sqlite3
import os
from pymongo import MongoClient
import time

# --- CONFIGURATION ---
SQLITE_DB_PATH = "../../data/imdb.db"
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "IMDB_DB"
BATCH_SIZE = 10000  # Nombre de lignes traitées à la fois (évite de saturer la RAM)

def get_sqlite_path():
    """Gère le chemin absolu pour éviter les erreurs 'unable to open database file'"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, SQLITE_DB_PATH)

def migrate():
    # 1. Connexion MongoDB
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    print(f"🔌 Connecté à MongoDB : {DB_NAME}")

    # 2. Connexion SQLite
    db_path = get_sqlite_path()
    if not os.path.exists(db_path):
        print(f"❌ Erreur : Base SQLite introuvable à : {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(f"📂 Connecté à SQLite : {db_path}")

    # Liste des tables à migrer
    tables = [
        'Movies', 'Characters', 'Directors', 'Episodes', 'Genres',
        'KnownForMovies', 'Persons', 'Principals', 'Ratings', 
        'Professions', 'Titles', 'Writers'
    ]

    start_total = time.time()

    for table in tables:
        print(f"\n🚀 Migration de la table : {table}...")
        
        # On vide la collection avant d'importer pour éviter les doublons si on relance
        # db[table].drop() 
        # (Décommentez la ligne du dessus si vous voulez écraser les données existantes)

        cursor.execute(f"SELECT * FROM {table}")
        
        # Récupération des noms de colonnes
        columns = [description[0] for description in cursor.description]
        
        total_cred = 0
        
        while True:
            # On ne prend que 10 000 lignes à la fois
            rows = cursor.fetchmany(BATCH_SIZE)
            
            if not rows:
                break  # Plus de données, on passe à la table suivante
            
            # Conversion en liste de dictionnaires
            documents = [dict(zip(columns, row)) for row in rows]
            
            # Insertion dans MongoDB
            if documents:
                db[table].insert_many(documents)
                total_inserted += len(documents)
                
                # Petit affichage de progression
                print(f"   ↳ {total_inserted} lignes insérées...", end='\r')

        print(f"✅ {table} terminée : {total_inserted} documents totaux.")

    conn.close()
    client.close()
    
    duration = time.time() - start_total
    print(f"\n🏁 Migration terminée avec succès en {duration:.2f} secondes.")

if __name__ == "__main__":
    migrate()