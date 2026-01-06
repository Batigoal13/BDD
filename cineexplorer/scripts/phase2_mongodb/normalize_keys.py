#!/usr/bin/env python3
"""
Étape 1: Normaliser les clés des documents MongoDB
Convertir les clés tuple strings en clés simples
"""
import time
from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "IMDB_DB"

# Mapping des clés tuple → clés simples
KEY_MAPPING = {
    "('mid',)": "MID",
    "('titleType',)": "titleType",
    "('primaryTitle',)": "primaryTitle",
    "('originalTitle',)": "originalTitle",
    "('startYear',)": "startYear",
    "('endYear',)": "endYear",
    "('runtimeMinutes',)": "runtimeMinutes",
    "('genres',)": "genres",
    "('rating',)": "rating",
    "('votes',)": "votes",
    "('name',)": "name",
    "('category',)": "category",
    "('job',)": "job",
    "('characters',)": "characters",
    "('region',)": "region",
    "('languages',)": "languages",
    "('premiered',)": "premiered",
    "('genre',)": "genre",
    "('region',)": "region",
    "('title',)": "title",
    "('primaryName',)": "primaryName",
    "('birthYear',)": "birthYear",
    "('deathYear',)": "deathYear",
    "('primaryProfession',)": "primaryProfession",
    "('ordering',)": "ordering",
    "('nconst',)": "PID",
    "('tconst',)": "MID",
    "('averageRating',)": "averageRating",
    "('numVotes',)": "numVotes",
}

def normalize_keys(doc):
    """Convertir toutes les clés tuple en clés simples"""
    if doc is None:
        return None
    
    normalized = {}
    for old_key, value in doc.items():
        if old_key == "_id":
            normalized["_id"] = value
        elif old_key in KEY_MAPPING:
            new_key = KEY_MAPPING[old_key]
            normalized[new_key] = value
        else:
            # Garder les clés inconnues
            normalized[old_key] = value
    
    return normalized

def normalize_collection(db, source_coll, target_coll):
    """Normaliser toute une collection"""
    print(f"\n📊 Normalisation {source_coll} → {target_coll}")
    
    # Compter
    total = db[source_coll].estimated_document_count()
    print(f"   📋 Documents : {total:,}")
    
    if total == 0:
        print(f"   ⚠️  Collection vide, skip")
        return
    
    # Drop cible
    db[target_coll].drop()
    
    start_time = time.time()
    batch = []
    batch_num = 0
    
    for i, doc in enumerate(db[source_coll].find(), 1):
        normalized = normalize_keys(doc)
        batch.append(normalized)
        
        if i % 1000 == 0:
            db[target_coll].insert_many(batch)
            batch = []
            batch_num += 1
            pct = 100 * i / total
            elapsed = time.time() - start_time
            speed = i / elapsed
            remaining = (total - i) / speed if speed > 0 else 0
            print(f"   ⏳ {pct:5.1f}% ({i:7,}/{total:7,}) | {speed:6.0f} docs/sec | Temps restant: {remaining/60:5.1f}min")
    
    if batch:
        db[target_coll].insert_many(batch)
    
    duration = time.time() - start_time
    result_count = db[target_coll].count_documents({})
    print(f"   ✅ Terminé en {duration/60:.1f}min - {result_count:,} documents")
    
    return result_count

def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    print("🔧 NORMALISATION DES CLÉS MongoDB")
    print("=" * 50)
    
    collections_to_normalize = [
        ("Movies", "Movies_normalized"),
        ("Ratings", "Ratings_normalized"),
        ("Genres", "Genres_normalized"),
        ("Persons", "Persons_normalized"),
        ("Directors", "Directors_normalized"),
        ("Writers", "Writers_normalized"),
        ("Principals", "Principals_normalized"),
        ("Characters", "Characters_normalized"),
        ("Titles", "Titles_normalized"),
    ]
    
    total_normalized = 0
    for source, target in collections_to_normalize:
        count = normalize_collection(db, source, target)
        if count:
            total_normalized += count
    
    print(f"\n{'='*50}")
    print(f"✅ NORMALISATION COMPLÈTE")
    print(f"   Total documents normalisés: {total_normalized:,}")
    print(f"   Collections: {len(collections_to_normalize)}")
    print(f"\nProchaine étape: Créer movies_complete_ALL avec les clés normalisées")

if __name__ == "__main__":
    main()
