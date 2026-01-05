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
