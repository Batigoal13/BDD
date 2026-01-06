#!/usr/bin/env python3
"""
Créer la collection movies_complete_ALL avec documents structurés
à partir des collections normalisées
"""
from pymongo import MongoClient
from typing import List, Generator
import time

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "IMDB_DB"

def get_pipeline(batch_mids: List[str]) -> List[dict]:
    """Pipeline d'agrégation pour créer des documents structurés"""
    return [
        {"$match": {"MID": {"$in": batch_mids}}},

        # 1. Joindre avec Ratings_normalized
        {"$lookup": {
            "from": "Ratings_normalized",
            "localField": "MID",
            "foreignField": "MID",
            "as": "ratings"
        }},

        # 2. Joindre avec Directors_normalized + Persons_normalized
        {"$lookup": {
            "from": "Directors_normalized",
            "let": {"mid": "$MID"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$MID", "$$mid"]}}},
                {"$lookup": {
                    "from": "Persons_normalized",
                    "localField": "('pid',)",
                    "foreignField": "primaryName",
                    "as": "person"
                }},
                {"$unwind": {"path": "$person", "preserveNullAndEmptyArrays": True}},
                {"$project": {
                    "_id": 0,
                    "id": "$('pid',)",
                    "name": {"$ifNull": ["$person.primaryName", "Unknown"]}
                }}
            ],
            "as": "directors"
        }},

        # 3. Joindre avec Principals_normalized (casting) limité à 30
        {"$lookup": {
            "from": "Principals_normalized",
            "let": {"mid": "$MID"},
            "pipeline": [
                {"$match": {
                    "$expr": {
                        "$and": [
                            {"$eq": ["$MID", "$$mid"]},
                            {"$in": ["$category", ["actor", "actress"]]}
                        ]
                    }
                }},
                {"$limit": 30},
                {"$lookup": {
                    "from": "Persons_normalized",
                    "localField": "('pid',)",
                    "foreignField": "primaryName",
                    "as": "person"
                }},
                {"$unwind": {"path": "$person", "preserveNullAndEmptyArrays": True}},
                {"$project": {
                    "_id": 0,
                    "id": "$('pid',)",
                    "name": {"$ifNull": ["$person.primaryName", "Unknown"]},
                    "ordering": "$ordering",
                    "category": "$category"
                }},
                {"$sort": {"ordering": 1}}
            ],
            "as": "cast"
        }},

        # 4. Projection finale - créer la structure complète
        {"$project": {
            "_id": "$MID",
            "type": "$titleType",
            "title": "$primaryTitle",
            "original_title": "$originalTitle",
            "year": "$startYear",
            "end_year": "$endYear",
            "runtime": "$runtimeMinutes",
            "rating": {
                "average": {"$arrayElemAt": ["$ratings.averageRating", 0]},
                "votes": {"$arrayElemAt": ["$ratings.numVotes", 0]}
            },
            "directors": 1,
            "cast": 1
        }}
    ]

def batch_generator(cursor, batch_size: int) -> Generator[List[str], None, None]:
    """Générateur par batch"""
    batch = []
    for doc in cursor:
        batch.append(doc["MID"])
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

def create_structured_collection():
    """Créer la collection structurée"""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    print("\n🏗️  Création de la collection structurée movies_complete_ALL")
    print("=" * 60)
    
    # Drop
    db["movies_complete_ALL"].drop()
    print("✅ Collection vidée")
    
    # Compter
    total = db["Movies_normalized"].estimated_document_count()
    print(f"📋 Documents à traiter: {total:,}")
    
    # Créer par batch
    batch_size = 500
    cursor = db["Movies_normalized"].find({}, {"MID": 1})
    
    start_time = time.time()
    processed = 0
    
    for batch_mids in batch_generator(cursor, batch_size):
        pipeline = get_pipeline(batch_mids)
        
        try:
            docs = list(db["Movies_normalized"].aggregate(pipeline))
            if docs:
                db["movies_complete_ALL"].insert_many(docs, ordered=False)
            processed += len(batch_mids)
            
            pct = 100 * processed / total
            speed = processed / (time.time() - start_time)
            remaining = (total - processed) / speed if speed > 0 else 0
            
            print(f"⏳ {pct:5.1f}% ({processed:7,}/{total:7,}) | {speed:6.0f} docs/s | Reste: {remaining/60:5.1f}min", end='\r')
            
        except Exception as e:
            print(f"\n⚠️  Erreur: {e}")
            continue
    
    duration = time.time() - start_time
    result_count = db["movies_complete_ALL"].count_documents({})
    
    print(f"\n{'='*60}")
    print(f"✅ Collection créée!")
    print(f"   📊 Documents: {result_count:,}")
    print(f"   ⏱️  Durée: {duration/60:.1f} minutes")
    
    # Afficher un exemple
    if result_count > 0:
        example = db["movies_complete_ALL"].find_one()
        print(f"\n📄 Exemple de document structuré:")
        print(f"   _id (MID): {example.get('_id')}")
        print(f"   title: {example.get('title')}")
        print(f"   year: {example.get('year')}")
        print(f"   type: {example.get('type')}")
        print(f"   genres: {example.get('genres')}")
        rating = example.get('rating', {})
        print(f"   rating: {rating.get('average')}/10 ({rating.get('votes'):,} votes)")
        print(f"   directors: {len(example.get('directors', []))} directeurs")
        print(f"   cast: {len(example.get('cast', []))} acteurs")

if __name__ == "__main__":
    create_structured_collection()
