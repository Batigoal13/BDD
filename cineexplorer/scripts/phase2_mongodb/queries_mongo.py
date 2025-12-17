from pymongo import MongoClient
import time
import re

# --- CONFIGURATION ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "IMDB_DB"

def get_database():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

# ==================================================================================
# 0. CRÉATION DES INDEX (INDISPENSABLE POUR $LOOKUP)
# ==================================================================================
def create_indexes(db):
    print("🏗️  Création des index MongoDB (nécessaire pour les performances)...")
    # Pour les $lookup (Jointures)
    db.Movies.create_index("MID")
    db.Persons.create_index("PID")
    db.Persons.create_index("primaryName") # Pour la recherche par nom
    db.Principals.create_index("MID")
    db.Principals.create_index("PID")
    db.Ratings.create_index("MID")
    db.Ratings.create_index("averageRating")
    db.Genres.create_index("MID")
    db.Genres.create_index("genres")
    db.Characters.create_index("MID")
    db.Characters.create_index("PID")
    db.Directors.create_index("MID")
    db.Directors.create_index("PID")
    print("✅ Index créés.")

# ==================================================================================
# 1. FILMOGRAPHIE D'UN ACTEUR (JOIN Movies, Principals, Persons, Ratings)
# ==================================================================================
def query_actor_filmography(db, actor_name):
    pipeline = [
        # 1. Trouver l'acteur (WHERE name LIKE '...')
        {"$match": {"primaryName": {"$regex": f"^{actor_name}", "$options": "i"}}},
        
        # 2. Joindre Principals (ON Persons.PID = Principals.PID)
        {"$lookup": {
            "from": "Principals",
            "localField": "PID",
            "foreignField": "PID",
            "as": "roles"
        }},
        {"$unwind": "$roles"},
        
        # 3. Joindre Movies (ON Principals.MID = Movies.MID)
        {"$lookup": {
            "from": "Movies",
            "localField": "roles.MID",
            "foreignField": "MID",
            "as": "movie"
        }},
        {"$unwind": "$movie"},
        
        # 4. Joindre Ratings (ON Movies.MID = Ratings.MID)
        {"$lookup": {
            "from": "Ratings",
            "localField": "movie.MID",
            "foreignField": "MID",
            "as": "rating"
        }},
        
        # Gestion du LEFT JOIN pour rating (peut être vide)
        {"$addFields": {
            "rating_val": {"$arrayElemAt": ["$rating.averageRating", 0]}
        }},

        # 5. Projection (SELECT ...)
        {"$project": {
            "_id": 0,
            "Titre": "$movie.primaryTitle",
            "Année": "$movie.startYear",
            "Note": "$rating_val"
        }},
        {"$sort": {"Année": -1}}
    ]
    return list(db.Persons.aggregate(pipeline))

# ==================================================================================
# 2. TOP N FILMS PAR GENRE (JOIN Genres, Movies, Ratings)
# ==================================================================================
def query_top_n_movies_by_genre(db, genre, start_year, end_year, n):
    pipeline = [
        # 1. Filtrer par Genre
        {"$match": {"genres": genre}},
        
        # 2. Joindre Movies
        {"$lookup": {
            "from": "Movies",
            "localField": "MID",
            "foreignField": "MID",
            "as": "movie"
        }},
        {"$unwind": "$movie"},
        
        # 3. Filtrer par année
        {"$match": {"movie.startYear": {"$gte": start_year, "$lte": end_year}}},
        
        # 4. Joindre Ratings
        {"$lookup": {
            "from": "Ratings",
            "localField": "MID",
            "foreignField": "MID",
            "as": "rating"
        }},
        {"$unwind": "$rating"},
        
        # 5. Trier et Limiter
        {"$sort": {"rating.averageRating": -1}},
        {"$limit": n},
        
        {"$project": {
            "_id": 0,
            "Titre": "$movie.primaryTitle",
            "Année": "$movie.startYear",
            "Note": "$rating.averageRating"
        }}
    ]
    return list(db.Genres.aggregate(pipeline))

# ==================================================================================
# 3. ACTEURS MULTI-RÔLES (GROUP BY PID, MID HAVING COUNT > 1)
# ==================================================================================
def query_multi_role_actors(db):
    pipeline = [
        # 1. Group by PID, MID
        {"$group": {
            "_id": {"PID": "$PID", "MID": "$MID"},
            "role_count": {"$sum": 1}
        }},
        # 2. Having count > 1
        {"$match": {"role_count": {"$gt": 1}}},
        {"$sort": {"role_count": -1}},
        {"$limit": 20}, # Limite pour l'affichage
        
        # 3. Récupérer les noms (Lookup Persons et Movies)
        {"$lookup": {
            "from": "Persons",
            "localField": "_id.PID",
            "foreignField": "PID",
            "as": "person"
        }},
        {"$lookup": {
            "from": "Movies",
            "localField": "_id.MID",
            "foreignField": "MID",
            "as": "movie"
        }},
        {"$project": {
            "Acteur": {"$arrayElemAt": ["$person.primaryName", 0]},
            "Film": {"$arrayElemAt": ["$movie.primaryTitle", 0]},
            "Nb Roles": "$role_count"
        }}
    ]
    return list(db.Characters.aggregate(pipeline))

# ==================================================================================
# 4. COLLABORATIONS DIRECTEUR/ACTEUR
# ==================================================================================
def query_director_actor_collaborations(db, actor_name):
    # Stratégie : Trouver l'PID de l'acteur -> Trouver ses Films -> Trouver les Directors -> Group
    
    # 1. Récupérer le PID de l'acteur (Appel simple pour éviter un pipeline monstrueux)
    actor = db.Persons.find_one({"primaryName": {"$regex": f"^{actor_name}", "$options": "i"}})
    if not actor: return []
    actor_pid = actor['PID']

    pipeline = [
        # 1. Partir des rôles de l'acteur
        {"$match": {"PID": actor_pid, "category": {"$in": ["actor", "actress"]}}},
        
        # 2. Joindre Directors sur le MID
        {"$lookup": {
            "from": "Directors",
            "localField": "MID",
            "foreignField": "MID",
            "as": "director_link"
        }},
        {"$unwind": "$director_link"},
        
        # 3. Joindre Persons pour avoir le nom du directeur
        {"$lookup": {
            "from": "Persons",
            "localField": "director_link.PID",
            "foreignField": "PID",
            "as": "director_info"
        }},
        {"$unwind": "$director_info"},
        
        # 4. Group by Director
        {"$group": {
            "_id": "$director_info.primaryName",
            "collab_count": {"$sum": 1}
        }},
        {"$sort": {"collab_count": -1}}
    ]
    return list(db.Principals.aggregate(pipeline))

# ==================================================================================
# 5. GENRES POPULAIRES (AVG > 7.0, COUNT > 50)
# ==================================================================================
def query_popular_genres(db):
    pipeline = [
        # 1. Partir des Movies pour filtrer type='movie'
        {"$match": {"titletype": "movie"}},
        
        # 2. Joindre Ratings
        {"$lookup": {
            "from": "Ratings",
            "localField": "MID",
            "foreignField": "MID",
            "as": "rating"
        }},
        {"$unwind": "$rating"},
        
        # 3. Joindre Genres
        {"$lookup": {
            "from": "Genres",
            "localField": "MID",
            "foreignField": "MID",
            "as": "genre_link"
        }},
        {"$unwind": "$genre_link"},
        
        # 4. Group by Genre
        {"$group": {
            "_id": "$genre_link.genres",
            "avg_rating": {"$avg": "$rating.averageRating"},
            "movie_count": {"$sum": 1}
        }},
        
        # 5. Having...
        {"$match": {
            "avg_rating": {"$gt": 7.0},
            "movie_count": {"$gt": 50}
        }},
        {"$sort": {"avg_rating": -1}}
    ]
    return list(db.Movies.aggregate(pipeline))

# ==================================================================================
# 6. ÉVOLUTION CARRIÈRE (GROUP BY DECADE)
# ==================================================================================
def query_actor_career_evolution(db, actor_name):
    pipeline = [
        {"$match": {"primaryName": {"$regex": f"^{actor_name}", "$options": "i"}}},
        
        # Lookup Principals -> Movies -> Ratings
        {"$lookup": {
            "from": "Principals",
            "localField": "PID",
            "foreignField": "PID",
            "as": "roles"
        }},
        {"$unwind": "$roles"},
        {"$match": {"roles.category": {"$in": ["actor", "actress"]}}}, # Filtre acteur uniquement
        
        {"$lookup": {
            "from": "Movies",
            "localField": "roles.MID",
            "foreignField": "MID",
            "as": "movie"
        }},
        {"$unwind": "$movie"},
        
        {"$lookup": {
            "from": "Ratings",
            "localField": "movie.MID",
            "foreignField": "MID",
            "as": "rating"
        }},
        {"$unwind": "$rating"},
        
        # Calcul de la décennie et Groupement
        {"$project": {
            "year": "$movie.startYear",
            "rating": "$rating.averageRating",
            "decade": {
                "$subtract": ["$movie.startYear", {"$mod": ["$movie.startYear", 10]}]
            }
        }},
        {"$group": {
            "_id": "$decade",
            "avg_rating": {"$avg": "$rating"},
            "nb_films": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    return list(db.Persons.aggregate(pipeline))

# ==================================================================================
# 7. CLASSEMENT PAR GENRE (Version optimisée GROUP + SLICE)
# ==================================================================================
def query_top_movies_per_genre_ranked(db):
    pipeline = [
        # 1. Filtre initial (Films populaires)
        {"$match": {"numVotes": {"$gt": 10000}}},
        
        # 2. Joindre Movies (Titre + Type)
        {"$lookup": {
            "from": "Movies",
            "localField": "MID",
            "foreignField": "MID",
            "as": "movie"
        }},
        {"$unwind": "$movie"},
        {"$match": {"movie.titletype": "movie"}},
        
        # 3. Joindre Genres
        {"$lookup": {
            "from": "Genres",
            "localField": "MID",
            "foreignField": "MID",
            "as": "genre_link"
        }},
        {"$unwind": "$genre_link"},
        
        # 4. Trier GLOBALEMENT avant de grouper (Note DESC, Votes DESC)
        {"$sort": {"averageRating": -1, "numVotes": -1}},
        
        # 5. Grouper par Genre et garder les 3 premiers (Pattern "Top N per Group")
        {"$group": {
            "_id": "$genre_link.genres",
            "top_films": {
                "$push": {
                    "Titre": "$movie.primaryTitle",
                    "Note": "$averageRating"
                }
            }
        }},
        
        # 6. Ne garder que les 3 premiers éléments du tableau
        {"$project": {
            "Genre": "$_id",
            "top_3": {"$slice": ["$top_films", 3]}
        }},
        
        # 7. Dérouler pour l'affichage propre
        {"$unwind": "$top_3"},
        {"$project": {
            "_id": 0,
            "Genre": 1,
            "Titre": "$top_3.Titre",
            "Note": "$top_3.Note"
        }},
        {"$sort": {"Genre": 1, "Note": -1}}
    ]
    return list(db.Ratings.aggregate(pipeline))

# ==================================================================================
# 8. BREAKOUT ROLES (Très complexe en Aggregation Flat -> Version simplifiée)
# ==================================================================================
def query_breakout_roles(db):
    # NOTE : Faire une requête "EXISTS previous movie < 200k" est très lourd en pur Mongo Flat.
    # On va simuler en récupérant les carrières complètes des acteurs ayant un blockbuster.
    
    pipeline = [
        # 1. Garder uniquement les films > 200k votes
        {"$match": {"numVotes": {"$gt": 200000}}},
        
        # 2. Remonter aux acteurs
        {"$lookup": {
            "from": "Principals",
            "localField": "MID",
            "foreignField": "MID",
            "as": "role"
        }},
        {"$unwind": "$role"},
        {"$match": {"role.category": {"$in": ["actor", "actress"]}}},
        
        # 3. Récupérer TOUS les films de ces acteurs (C'est ici que ça coûte cher)
        {"$lookup": {
            "from": "Principals",
            "localField": "role.PID",
            "foreignField": "PID",
            "as": "all_roles"
        }},
        
        # 4. Projection pour analyse
        {"$project": {
            "PID": "$role.PID",
            "BreakoutMovieID": "$MID",
            "AllMovieIDs": "$all_roles.MID"
        }},
        {"$limit": 10} # On limite drastiquement pour l'exercice car c'est O(N^2)
    ]
    # Note : La logique complète "AND NOT EXISTS" est souvent gérée côté applicatif (Python)
    # avec MongoDB quand le schéma n'est pas optimisé.
    return list(db.Ratings.aggregate(pipeline))

# ==================================================================================
# 9. DUOS EN OR
# ==================================================================================
def query_golden_duos(db):
    pipeline = [
        # Partir des Films
        {"$match": {"titletype": "movie"}},
        
        # Joindre Réalisateurs
        {"$lookup": {"from": "Directors", "localField": "MID", "foreignField": "MID", "as": "dirs"}},
        {"$unwind": "$dirs"},
        
        # Joindre Acteurs
        {"$lookup": {"from": "Principals", "localField": "MID", "foreignField": "MID", "as": "actors"}},
        {"$unwind": "$actors"},
        {"$match": {"actors.category": {"$in": ["actor", "actress"]}}},
        
        # Joindre Ratings
        {"$lookup": {"from": "Ratings", "localField": "MID", "foreignField": "MID", "as": "rating"}},
        {"$unwind": "$rating"},
        
        # Groupement
        {"$group": {
            "_id": {"DirPID": "$dirs.PID", "ActPID": "$actors.PID"},
            "count": {"$sum": 1},
            "avg_rating": {"$avg": "$rating.averageRating"}
        }},
        
        # Filtre
        {"$match": {"count": {"$gte": 3}}},
        {"$sort": {"avg_rating": -1}},
        {"$limit": 20},
        
        # Récupération des noms (Cosmétique, coûteux)
        {"$lookup": {"from": "Persons", "localField": "_id.DirPID", "foreignField": "PID", "as": "dir_info"}},
        {"$lookup": {"from": "Persons", "localField": "_id.ActPID", "foreignField": "PID", "as": "act_info"}},
        
        {"$project": {
            "Director": {"$arrayElemAt": ["$dir_info.primaryName", 0]},
            "Actor": {"$arrayElemAt": ["$act_info.primaryName", 0]},
            "Count": "$count",
            "Rating": "$avg_rating"
        }}
    ]
    return list(db.Movies.aggregate(pipeline))

# ==================================================================================
# FONCTION DE TEST GÉNÉRIQUE
# ==================================================================================
def run_benchmark():
    db = get_database()
    create_indexes(db)
    
    tasks = [
        (query_actor_filmography, ["Tom Hanks"], "1. Filmographie"),
        (query_top_n_movies_by_genre, ["Sci-Fi", 1980, 2020, 10], "2. Top N Films"),
        (query_multi_role_actors, [], "3. Multi-Rôles"),
        (query_director_actor_collaborations, ["Tom Hanks"], "4. Collaborations"),
        (query_popular_genres, [], "5. Genres Populaires"),
        (query_actor_career_evolution, ["Clint Eastwood"], "6. Carrière"),
        (query_top_movies_per_genre_ranked, [], "7. Classement par Genre (Window)"),
        (query_breakout_roles, [], "8. Breakout Roles (Limit 10)"),
        (query_golden_duos, [], "9. Duos en Or")
    ]
    
    print("\n" + "="*60)
    print(f"{'Requête MongoDB':<40} | {'Temps (ms)':<10} | {'Résultats'}")
    print("-" * 60)
    
    for func, args, label in tasks:
        start = time.time()
        try:
            res = func(db, *args)
            count = len(res)
            status = f"✅ {count}"
        except Exception as e:
            status = f"❌ Erreur: {e}"
        
        duration = (time.time() - start) * 1000 # ms
        print(f"{label:<40} | {duration:>10.2f} | {status}")

if __name__ == "__main__":
    run_benchmark()