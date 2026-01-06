"""
Service d'accès à MongoDB pour les requêtes sur la base IMDB.
"""
from pymongo import MongoClient, ReadPreference
from django.conf import settings


_client = None


def get_client():
    """Retourne un client MongoDB (singleton)."""
    global _client
    if _client is None:
        mongo_settings = settings.MONGODB_SETTINGS
        _client = MongoClient(
            mongo_settings['URI'],
            connectTimeoutMS=mongo_settings.get('CONNECT_TIMEOUT_MS', 5000),
            serverSelectionTimeoutMS=mongo_settings.get('SERVER_SELECTION_TIMEOUT_MS', 5000),
            read_preference=ReadPreference.PRIMARY_PREFERRED,
        )
    return _client


def get_database():
    """Retourne la base de données MongoDB."""
    client = get_client()
    return client[settings.MONGODB_SETTINGS['DATABASE']]


def get_movie_count():
    """Retourne le nombre total de films."""
    try:
        db = get_database()
        return db.Movies.with_options(read_preference=ReadPreference.SECONDARY_PREFERRED).count_documents({})
    except Exception:
        return 0


def get_person_count():
    """Retourne le nombre total de personnes."""
    try:
        db = get_database()
        return db.Persons.with_options(read_preference=ReadPreference.SECONDARY_PREFERRED).count_documents({})
    except Exception:
        return 0


def get_collection_stats():
    """Retourne des statistiques sur les collections."""
    db = get_database()
    collections = db.list_collection_names()
    stats = {}
    for coll_name in collections:
        if not coll_name.startswith('system.'):
            stats[coll_name] = db[coll_name].estimated_document_count()
    return stats


def search_movies(query, limit=10):
    """Recherche des films par titre."""
    db = get_database()
    results = db.Movies.find(
        {"primaryTitle": {"$regex": query, "$options": "i"}},
        {"MID": 1, "primaryTitle": 1, "startYear": 1, "titletype": 1}
    ).limit(limit)
    return list(results)


def get_movie_with_rating(mid):
    """Retourne un film avec son rating via une agrégation."""
    db = get_database()
    pipeline = [
        {"$match": {"MID": mid}},
        {"$lookup": {
            "from": "Ratings",
            "localField": "MID",
            "foreignField": "MID",
            "as": "rating"
        }},
        {"$unwind": {"path": "$rating", "preserveNullAndEmptyArrays": True}},
        {"$limit": 1}
    ]
    results = list(db.Movies.aggregate(pipeline))
    return results[0] if results else None


def get_movie_detail(movie_id):
    """
    Retourne tous les détails d'un film depuis les collections normalisées MongoDB.
    Les données sont stockées dans les fichiers WiredTiger (.wt).
    """
    try:
        db = get_database()
        
        # 1. Film de base depuis Movies_normalized
        movie = db.Movies_normalized.find_one({"MID": movie_id})
        if not movie:
            return None
        
        # 2. Note depuis Ratings_normalized
        rating = db.Ratings_normalized.find_one({"MID": movie_id})
        
        # 3. Genres depuis Genres_normalized
        genres = list(db.Genres_normalized.find({"MID": movie_id}))
        genres_list = [g.get('genre') for g in genres if g.get('genre')]
        
        # 4. Réalisateurs depuis Directors_normalized + Persons_normalized
        directors = list(db.Directors_normalized.find({"MID": movie_id}))
        formatted_directors = []
        for d in directors:
            pid = d.get("('pid',)") or d.get("PID")
            if pid:
                person = db.Persons_normalized.find_one({"('pid',)": pid})
                if person:
                    formatted_directors.append({
                        'PID': pid,
                        'name': person.get('primaryName', 'Unknown')
                    })
        
        # 5. Casting depuis Principals_normalized + Persons_normalized
        principals = list(db.Principals_normalized.find({
            "MID": movie_id,
            "category": {"$in": ["actor", "actress"]}
        }).sort("ordering", 1).limit(30))
        
        formatted_cast = []
        for p in principals:
            pid = p.get("('pid',)") or p.get("PID")
            if pid:
                person = db.Persons_normalized.find_one({"('pid',)": pid})
                if person:
                    # Chercher les personnages
                    characters = list(db.Characters_normalized.find({"MID": movie_id, "('pid',)": pid}))
                    char_names = [c.get('name') for c in characters if c.get('name')]
                    
                    formatted_cast.append({
                        'PID': pid,
                        'name': person.get('primaryName', 'Unknown'),
                        'category': p.get('category', 'actor'),
                        'characters': char_names,
                        'ordering': p.get('ordering', 999)
                    })
        
        # 6. Scénaristes depuis Writers_normalized + Persons_normalized
        writers = list(db.Writers_normalized.find({"MID": movie_id}))
        formatted_writers = []
        for w in writers[:10]:
            pid = w.get("('pid',)") or w.get("PID")
            if pid:
                person = db.Persons_normalized.find_one({"('pid',)": pid})
                if person:
                    formatted_writers.append({
                        'PID': pid,
                        'name': person.get('primaryName', 'Unknown')
                    })
        
        # 7. Titres alternatifs depuis Titles_normalized
        alt_titles = list(db.Titles_normalized.find({"MID": movie_id}).limit(10))
        
        # Construire le résultat
        return {
            'MID': movie_id,
            'primaryTitle': movie.get('primaryTitle', 'Unknown'),
            'originalTitle': movie.get('originalTitle'),
            'startYear': movie.get('startYear'),
            'endYear': movie.get('endYear'),
            'titletype': movie.get('titleType'),
            'runtime': movie.get('runtimeMinutes'),
            'genres': genres_list,
            'rating': rating.get('averageRating') if rating else 0,
            'votes': rating.get('numVotes') if rating else 0,
            'cast': sorted(formatted_cast, key=lambda x: x.get('ordering', 999)),
            'directors': formatted_directors,
            'writers': formatted_writers,
            'producers': [],
            'titles': alt_titles
        }
    except Exception as e:
        print(f"Erreur dans get_movie_detail: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_replica_status():
    """Retourne le statut du replica set."""
    try:
        client = get_client()
        status = client.admin.command("replSetGetStatus")
        members = []
        for m in status.get("members", []):
            members.append({
                "name": m.get("name"),
                "stateStr": m.get("stateStr"),
                "health": m.get("health"),
                "uptime": m.get("uptime", 0)
            })
        return {
            "set": status.get("set"),
            "members": members,
            "ok": status.get("ok")
        }
    except Exception as e:
        return {"error": str(e), "ok": 0}
