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
