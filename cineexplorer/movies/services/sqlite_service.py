"""
Service d'accès à SQLite pour les requêtes sur la base IMDB.
"""
import sqlite3
from pathlib import Path
from django.conf import settings


def get_connection():
    """Retourne une connexion SQLite."""
    db_path = settings.DATABASES['default']['NAME']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Pour accéder aux colonnes par nom
    return conn


def get_movie_count():
    """Retourne le nombre total de films."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM Movies")
    result = cursor.fetchone()
    conn.close()
    return result['count'] if result else 0


def get_person_count():
    """Retourne le nombre total de personnes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM Persons")
    result = cursor.fetchone()
    conn.close()
    return result['count'] if result else 0


def get_rating_stats():
    """Retourne des statistiques sur les ratings."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as count,
            AVG(averageRating) as avg_rating,
            MIN(averageRating) as min_rating,
            MAX(averageRating) as max_rating
        FROM Ratings
    """)
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else {}


def search_movies(query, limit=10):
    """Recherche des films par titre."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MID, primaryTitle, startYear, titletype
        FROM Movies
        WHERE primaryTitle LIKE ?
        ORDER BY primaryTitle
        LIMIT ?
    """, (f"%{query}%", limit))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def search_people(query, limit=10):
    """Recherche des personnes par nom."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT PID, primaryName, birthYear, deathYear
        FROM Persons
        WHERE primaryName LIKE ?
        ORDER BY primaryName
        LIMIT ?
    """, (f"%{query}%", limit))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_movies_by_person(person_id, limit=50):
    """Retourne tous les films auxquels une personne a participé (acteur, réalisateur, scénariste)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Utiliser UNION pour combiner les films où la personne est acteur, réalisateur ou scénariste
    cursor.execute("""
        SELECT DISTINCT 
            m.MID, 
            m.primaryTitle, 
            m.startYear, 
            m.titletype,
            r.averageRating,
            CASE 
                WHEN d.PID IS NOT NULL THEN 'director'
                WHEN w.PID IS NOT NULL THEN 'writer'
                WHEN p.PID IS NOT NULL THEN 'actor'
                ELSE 'other'
            END as role
        FROM Movies m
        LEFT JOIN Ratings r ON m.MID = r.MID
        LEFT JOIN Directors d ON m.MID = d.MID AND d.PID = ?
        LEFT JOIN Writers w ON m.MID = w.MID AND w.PID = ?
        LEFT JOIN Principals p ON m.MID = p.MID AND p.PID = ? AND p.category IN ('actor', 'actress')
        WHERE d.PID = ? OR w.PID = ? OR p.PID = ?
        ORDER BY m.startYear DESC, r.averageRating DESC
        LIMIT ?
    """, (person_id, person_id, person_id, person_id, person_id, person_id, limit))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_movie_details(mid):
    """Retourne les détails d'un film avec son rating."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.*, r.averageRating, r.numVotes
        FROM Movies m
        LEFT JOIN Ratings r ON m.MID = r.MID
        WHERE m.MID = ?
    """, (mid,))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None


def get_top_rated_movies(limit=10):
    """Retourne les films les mieux notés."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.MID, m.primaryTitle, m.startYear, r.averageRating, r.numVotes
        FROM Movies m
        JOIN Ratings r ON m.MID = r.MID
        WHERE r.numVotes >= 1000
        ORDER BY r.averageRating DESC, r.numVotes DESC
        LIMIT ?
    """, (limit,))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_filtered_movies(genre=None, year_min=None, year_max=None, rating_min=0, sort_by='title'):
    """Retourne une liste de films filtrée et triée."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT DISTINCT m.MID, m.primaryTitle, m.startYear, r.averageRating, r.numVotes
        FROM Movies m
        LEFT JOIN Ratings r ON m.MID = r.MID
        LEFT JOIN Genres g ON m.MID = g.MID
        WHERE 1=1
    """
    params = []
    
    if genre:
        query += " AND g.genres = ?"
        params.append(genre)
    
    if year_min:
        query += " AND m.startYear >= ?"
        params.append(int(year_min))
    
    if year_max:
        query += " AND m.startYear <= ?"
        params.append(int(year_max))
    
    if rating_min:
        query += " AND r.averageRating >= ?"
        params.append(float(rating_min))
    
    # Tri
    if sort_by == 'title':
        query += " ORDER BY m.primaryTitle ASC"
    elif sort_by == 'year':
        query += " ORDER BY m.startYear DESC"
    elif sort_by == 'rating':
        query += " ORDER BY r.averageRating DESC"
    
    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_all_genres():
    """Retourne la liste de tous les genres."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT genres FROM Genres ORDER BY genres")
    results = [row['genres'] for row in cursor.fetchall()]
    conn.close()
    return results


def get_similar_movies(genre=None, limit=6, exclude_id=None):
    """Retourne des films similaires (même genre)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if not genre:
        return []
    
    query = """
        SELECT m.MID, m.primaryTitle, m.startYear, r.averageRating as rating
        FROM Movies m
        JOIN Genres g ON m.MID = g.MID
        LEFT JOIN Ratings r ON m.MID = r.MID
        WHERE g.genres = ?
    """
    params = [genre]
    
    if exclude_id:
        query += " AND m.MID != ?"
        params.append(exclude_id)
    
    query += " ORDER BY r.averageRating DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_movies_by_genre():
    """Retourne le nombre de films par genre (pour graphique)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT genres, COUNT(DISTINCT MID) as count
        FROM Genres
        GROUP BY genres
        ORDER BY count DESC
        LIMIT 10
    """)
    results = [{'genre': row['genres'], 'count': row['count']} for row in cursor.fetchall()]
    conn.close()
    return results


def get_movies_by_decade():
    """Retourne le nombre de films par décennie (pour graphique)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            (startYear / 10 * 10) as decade,
            COUNT(*) as count
        FROM Movies
        WHERE startYear IS NOT NULL
        GROUP BY decade
        ORDER BY decade
    """)
    results = [{'decade': f"{row['decade']}s", 'count': row['count']} for row in cursor.fetchall()]
    conn.close()
    return results


def get_rating_distribution():
    """Retourne la distribution des notes (pour histogramme)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            ROUND(averageRating, 0) as rating,
            COUNT(*) as count
        FROM Ratings
        WHERE averageRating IS NOT NULL
        GROUP BY ROUND(averageRating, 0)
        ORDER BY rating
    """)
    results = [{'rating': row['rating'], 'count': row['count']} for row in cursor.fetchall()]
    conn.close()
    return results


def get_top_actors(limit=10):
    """Retourne les acteurs avec le plus de films."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.PID, p.primaryName, COUNT(DISTINCT pk.MID) as film_count
        FROM Persons p
        JOIN Principals pk ON p.PID = pk.PID
        WHERE pk.category = 'actor' OR pk.category = 'actress'
        GROUP BY p.PID, p.primaryName
        ORDER BY film_count DESC
        LIMIT ?
    """, (limit,))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_actor_count():
    """Retourne le nombre d'acteurs/actrices distincts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT p.PID) as count
        FROM Persons p
        JOIN Principals pk ON p.PID = pk.PID
        WHERE pk.category = 'actor' OR pk.category = 'actress'
    """)
    result = cursor.fetchone()
    conn.close()
    return result['count'] if result else 0


def get_director_count():
    """Retourne le nombre de réalisateurs distincts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT p.PID) as count
        FROM Persons p
        JOIN Principals pk ON p.PID = pk.PID
        WHERE pk.category = 'director'
    """)
    result = cursor.fetchone()
    conn.close()
    return result['count'] if result else 0


def get_recent_movies(limit=12):
    """Retourne les films les plus récents."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.MID, m.primaryTitle, m.startYear, r.averageRating, r.numVotes
        FROM Movies m
        LEFT JOIN Ratings r ON m.MID = r.MID
        WHERE m.startYear IS NOT NULL AND m.startYear >= 2015
        ORDER BY m.startYear DESC, r.numVotes DESC
        LIMIT ?
    """, (limit,))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results
