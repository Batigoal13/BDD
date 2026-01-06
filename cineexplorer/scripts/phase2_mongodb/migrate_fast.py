#!/usr/bin/env python3
"""
Script RAPIDE pour créer les documents structurés MongoDB
Skip des index pour aller plus vite - les index seront créés après
"""
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
TARGET_COLL = "movies_complete_ALL"
BATCH_SIZE = 500

def skip_indexes(db):
    """Skip la création d'index pour aller plus vite"""
    print("⏭️  Skip de la création d'index")
    print("   ℹ️  Les index seront créés après la migration")

def get_pipeline(batch_mids: List[str]) -> List[dict]:
    """Pipeline d'agrégation SANS filtre de type."""
    return [
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

        # 5. JOINTURE DIRECTORS (optimisée avec pipeline)
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
                {"$limit": 30},  # Limiter pour performance
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
            "type": "$titletype",
            "title": "$primaryTitle",
            "original_title": "$originalTitle",
            "year": "$startYear",
            "endYear": "$endYear",
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
    
    bar_length = 40
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    
    speed_str = f"{avg_speed:.0f} docs/sec"
    remaining_str = f"{remaining/60:.1f} min" if remaining > 60 else f"{remaining:.0f} sec"
    
    sys.stdout.write(f'\r|{bar}| {percent:5.1f}% ({current:6d}/{total:6d}) | ⏱️  {speed_str} | ⏳ {remaining_str}')
    sys.stdout.flush()

def migrate_embedded_fast():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    print(f"\n🏗️  MIGRATION RAPIDE - Documents structurés MongoDB")
    print(f"    Cible : {TARGET_COLL}")
    print(f"    Mode : RAPIDE (skip des index)")

    skip_indexes(db)

    print(f"\n🧹 Nettoyage de la collection cible {TARGET_COLL}...")
    db[TARGET_COLL].drop()

    # 1. Compte total
    print("📊 Estimation du volume total...")
    total_docs = db[COLL_MOVIES].estimated_document_count()
    print(f"📋 Documents à traiter : {total_docs:,}")
    
    # 2. Curseur sur tout
    cursor = db[COLL_MOVIES].find({}, {"MID": 1}) 
    
    start_time = time.time()
    processed_count = 0
    batch_num = 0

    for batch_mids in batch_generator(cursor, BATCH_SIZE):
        batch_num += 1
        pipeline = get_pipeline(batch_mids)
        
        try:
            transformed_docs = list(db[COLL_MOVIES].aggregate(pipeline))
            
            if transformed_docs:
                db[TARGET_COLL].insert_many(transformed_docs, ordered=False)
            
            processed_count += len(batch_mids)
            print_progress(processed_count, total_docs, start_time)
            
        except Exception as e:
            print(f"\n⚠️  Erreur batch {batch_num}: {e}")
            continue

    duration = time.time() - start_time
    total_in_target = db[TARGET_COLL].count_documents({})
    
    print(f"\n\n✅ Migration terminée!")
    print(f"   ⏱️  Durée: {duration/60:.1f} minutes")
    print(f"   📊 Documents créés: {total_in_target:,}/{total_docs:,}")
    
    if total_in_target > 0:
        print(f"\n🔍 Création des index pour performance...")
        print(f"   📍 Index sur _id (PRIMARY)...", end='', flush=True)
        db[TARGET_COLL].create_index([("_id", ASCENDING)])
        print(" ✅")
        
        print(f"   📍 Index sur type...", end='', flush=True)
        db[TARGET_COLL].create_index([("type", ASCENDING)])
        print(" ✅")
        
        print(f"\n✅ Les documents structurés sont prêts!")
        print(f"   Accédez-les via: db.{TARGET_COLL}.find_one({{'_id': 'tt1234567'}})")

if __name__ == "__main__":
    migrate_embedded_fast()
