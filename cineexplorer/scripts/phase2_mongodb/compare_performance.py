import time
import random
from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "IMDB_DB"

def benchmark_read():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # 1. Récupérer un échantillon de 1000 IDs de films existants dans la nouvelle collection
    # (pour être sûr qu'on compare la même chose)
    print("🎲 Récupération de 1000 IDs aléatoires...")
    sample_docs = list(db["movies_complete_ALL"].aggregate([{"$sample": {"size": 1000}}, {"$project": {"_id": 1}}]))
    sample_mids = [d["_id"] for d in sample_docs]

    # --- MÉTHODE 1 : APPROCHE "RELATIONNELLE" (N REQUÊTES) ---
    print(f"\n🐢 Test Approche 'Plate' (N requêtes par film)...")
    start_time = time.time()
    
    for mid in sample_mids:
        # Requête 1 : Infos film
        movie = db["Movies"].find_one({"MID": mid})
        # Requête 2 : Ratings
        rating = db["Ratings"].find_one({"MID": mid})
        # Requête 3 : Récupérer les liens (Principals)
        principals = list(db["Principals"].find({"MID": mid}))
        
        # Requête 4 à N : Récupérer les noms des personnes (Simulation simple)
        # Dans une vraie appli SQL, on ferait des JOINs, mais en NoSQL plat, on fait souvent ça :
        pids = [p["PID"] for p in principals]
        persons = list(db["Persons"].find({"PID": {"$in": pids}}))
        
        # Assemblage Python (coût CPU négligeable par rapport au réseau)
        full_movie = {**movie, "rating": rating, "cast_data": persons}

    duration_flat = time.time() - start_time
    avg_flat = (duration_flat / 1000) * 1000 # en ms

    # --- MÉTHODE 2 : APPROCHE "DOCUMENT" (1 REQUÊTE) ---
    print(f"🐇 Test Approche 'Structurée' (1 requête par film)...")
    start_time = time.time()

    for mid in sample_mids:
        # UNE SEULE REQUÊTE
        full_movie = db["movies_complete"].find_one({"_id": mid})

    duration_struct = time.time() - start_time
    avg_struct = (duration_struct / 1000) * 1000 # en ms

    # --- RÉSULTATS ---
    print("\n" + "="*40)
    print(f"RÉSULTATS (Moyenne sur 1000 lectures)")
    print("="*40)
    print(f"🐢 N Requêtes (Flat)    : {avg_flat:.2f} ms / film")
    print(f"🐇 1 Requête (Struct)   : {avg_struct:.2f} ms / film")
    print("-" * 40)
    if avg_struct > 0:
        ratio = avg_flat / avg_struct
        print(f"🚀 Gain de performance : x{ratio:.1f} plus rapide")
    print("="*40)

if __name__ == "__main__":
    benchmark_read()