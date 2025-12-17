import time
import sys
from pymongo import MongoClient, ASCENDING
from typing import List, Generator

# --- CONFIGURATION ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "IMDB_DB"

# Collections sources
COLL_MOVIES = "Movies"
COLL_RATINGS = "Ratings"
COLL_GENRES = "Genres"
COLL_TITLES = "Titles"
COLL_DIRECTORS = "Directors"
COLL_WRITERS = "Writers"
COLL_PRINCIPALS = "Principals"
COLL_PERSONS = "Persons"
COLL_CHARACTERS = "Characters"

# Cible
TARGET_COLL = "movies_complete_ALL" # J'ai renommé la collection pour ne pas écraser l'autre test
BATCH_SIZE = 1000

def ensure_indexes(db):
    """
    Indexation critique pour la performance.
    """
    print("🛠 Vérification des index...")
    # Index principaux
    db[COLL_MOVIES].create_index([("MID", ASCENDING)]) # Plus besoin de l'index composé avec titletype
    db[COLL_RATINGS].create_index("MID")
    db[COLL_GENRES].create_index("MID")
    db[COLL_TITLES].create_index("MID")
    
    # Tables de liaison
    db[COLL_DIRECTORS].create_index("MID")
    db[COLL_DIRECTORS].create_index("PID")
    db[COLL_WRITERS].create_index("MID")
    db[COLL_WRITERS].create_index("PID")
    db[COLL_PRINCIPALS].create_index("MID")
    db[COLL_PRINCIPALS].create_index("PID")
    
    # Personnes
    db[COLL_PERSONS].create_index("PID")
    db[COLL_CHARACTERS].create_index([("MID", ASCENDING), ("PID", ASCENDING)])
    print("✅ Index opérationnels.")

def get_pipeline(batch_mids: List[str]) -> List[dict]:
    """Pipeline d'agrégation SANS filtre de type."""
    return [
        # 1. FILTRE : Sélection par IDs uniquement (TOUT TYPE CONFONDU)
        {"$match": {
            "MID": {"$in": batch_mids}
        }},

        # 2. JOINTURE RATINGS
        {"$lookup": {
            "from": COLL_RATINGS,
            "localField": "MID",
            "foreignField": "MID",
            "as": "rating_info"
        }},
        
        # 3. JOINTURE GENRES
        {"$lookup": {
            "from": COLL_GENRES,
            "localField": "MID",
            "foreignField": "MID",
            "as": "genres_list"
        }},

        # 4. JOINTURE TITLES
        {"$lookup": {
            "from": COLL_TITLES,
            "localField": "MID",
            "foreignField": "MID",
            "as": "titles_list"
        }},

        # 5. JOINTURE DIRECTORS
        {"$lookup": {
            "from": COLL_DIRECTORS,
            "let": {"mid": "$MID"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$MID", "$$mid"]}}},
                {"$lookup": { 
                    "from": COLL_PERSONS,
                    "localField": "PID",
                    "foreignField": "PID",
                    "as": "person"
                }},
                {"$unwind": "$person"},
                {"$project": {"_id": 0, "id": "$PID", "name": "$person.primaryName"}}
            ],
            "as": "directors"
        }},

        # 6. JOINTURE WRITERS
        {"$lookup": {
            "from": COLL_WRITERS,
            "let": {"mid": "$MID"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$MID", "$$mid"]}}},
                {"$lookup": {
                    "from": COLL_PERSONS,
                    "localField": "PID",
                    "foreignField": "PID",
                    "as": "person"
                }},
                {"$unwind": "$person"},
                {"$project": {"_id": 0, "id": "$PID", "name": "$person.primaryName"}}
            ],
            "as": "writers"
        }},

        # 7. JOINTURE CASTING
        {"$lookup": {
            "from": COLL_PRINCIPALS,
            "let": {"mid": "$MID"},
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$MID", "$$mid"]},
                    {"$in": ["$category", ["actor", "actress"]]}
                ]}}},
                {"$lookup": {
                    "from": COLL_PERSONS,
                    "localField": "PID",
                    "foreignField": "PID",
                    "as": "person"
                }},
                {"$unwind": "$person"},
                {"$lookup": {
                    "from": COLL_CHARACTERS,
                    "let": {"pid": "$PID", "mid": "$MID"},
                    "pipeline": [
                        {"$match": {"$expr": {"$and": [
                            {"$eq": ["$MID", "$$mid"]},
                            {"$eq": ["$PID", "$$pid"]}
                        ]}}}
                    ],
                    "as": "char_info"
                }},
                {"$project": {
                    "_id": 0,
                    "id": "$PID",
                    "name": "$person.primaryName",
                    "ordering": "$ordering",
                    "characters": {"$map": {"input": "$char_info", "as": "c", "in": "$$c.name"}}
                }},
                {"$sort": {"ordering": 1}}
            ],
            "as": "cast"
        }},

        # 8. PROJECTION FINALE
        {"$project": {
            "_id": "$MID",
            "type": "$titletype",  # Ajout du type pour pouvoir filtrer plus tard si besoin
            "title": "$primaryTitle",
            "original_title": "$originalTitle",
            "year": "$startYear",
            "endYear": "$endYear", # Utile pour les séries
            "runtime": "$runtimeMinutes",
            "genres": "$genres_list.genre",
            "rating": {
                "average": {"$arrayElemAt": ["$rating_info.averageRating", 0]},
                "votes": {"$arrayElemAt": ["$rating_info.numVotes", 0]}
            },
            "directors": 1,
            "writers": 1,
            "cast": 1,
            "titles": {
                "$map": {
                    "input": "$titles_list",
                    "as": "t",
                    "in": {"region": "$$t.region", "title": "$$t.title"}
                }
            }
        }}
    ]

def batch_generator(cursor, batch_size: int) -> Generator[List[str], None, None]:
    batch = []
    for doc in cursor:
        batch.append(doc["MID"])
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

def print_progress(current, total, start_time):
    percent = 100 * (current / float(total))
    elapsed = time.time() - start_time
    avg_speed = current / elapsed if elapsed > 0 else 0
    remaining = (total - current) / avg_speed if avg_speed > 0 else 0
    
    bar_length = 30
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    
    sys.stdout.write(f'\rProgress: |{bar}| {percent:.1f}% ({current}/{total}) - ⏳ Reste env. {remaining/60:.1f} min')
    sys.stdout.flush()

def migrate_embedded():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    print(f"🏗️  Démarrage de la MIGRATION COMPLÈTE (TOUT INCLUS)")
    print(f"    Cible : {TARGET_COLL}")

    ensure_indexes(db)

    print(f"🧹 Nettoyage de la collection cible {TARGET_COLL}...")
    db[TARGET_COLL].drop()

    # 1. Compte total (estimé pour la rapidité)
    print("📊 Estimation du volume total...")
    total_docs = db[COLL_MOVIES].estimated_document_count()
    print(f"📋 Documents à traiter : {total_docs}")
    
    # 2. Curseur sur TOUT (pas de filtre)
    # On trie par MID pour une lecture séquentielle potentiellement plus stable, mais optionnel
    cursor = db[COLL_MOVIES].find({}, {"MID": 1}) 
    
    start_time = time.time()
    processed_count = 0

    for batch_mids in batch_generator(cursor, BATCH_SIZE):
        pipeline = get_pipeline(batch_mids)
        
        try:
            transformed_docs = list(db[COLL_MOVIES].aggregate(pipeline))
            
            if transformed_docs:
                db[TARGET_COLL].insert_many(transformed_docs, ordered=False)
            
            processed_count += len(batch_mids)
            print_progress(processed_count, total_docs, start_time)
            
        except Exception as e:
            print(f"\n⚠️ Erreur batch : {e}")

    duration = time.time() - start_time
    print(f"\n\n✅ Migration terminée en {duration:.2f} secondes.")
    print(f"📊 Total documents : {db[TARGET_COLL].count_documents({})}")

if __name__ == "__main__":
    migrate_embedded()