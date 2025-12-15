import sqlite3
import pandas as pd
from typing import List, Tuple, Any

def query_actor_filmography(conn: sqlite3.Connection, actor_name: str) -> List[Tuple]:
    """
    Récupère la filmographie d'un acteur donné.
    OPTIMISATION : '{actor_name}%' au lieu de '%{actor_name}%' pour utiliser l'index.
    """
    sql = """
        SELECT m.primaryTitle, m.startYear, c.name as character_name, r.averageRating
        FROM Movies m
        JOIN Principals pr ON m.MID = pr.MID
        JOIN Persons pe ON pr.PID = pe.PID
        LEFT JOIN Characters c ON m.MID = c.MID AND pe.PID = c.PID
        LEFT JOIN Ratings r ON m.MID = r.MID
        WHERE pe.primaryName LIKE ? 
        ORDER BY m.startYear DESC;
    """
    return conn.execute(sql, (f'{actor_name}%',)).fetchall()

def query_top_n_movies_by_genre(conn: sqlite3.Connection, genre: str, start_year: int, end_year: int, n: int) -> List[Tuple]:
    """Récupère les N meilleurs films pour un genre et une période donnés."""
    sql = """
        SELECT m.primaryTitle, m.startYear, r.averageRating, g.genres
        FROM Movies m
        JOIN Genres g ON m.MID = g.MID
        JOIN Ratings r ON m.MID = r.MID
        WHERE g.genres = ? AND m.startYear BETWEEN ? AND ?
        ORDER BY r.averageRating DESC
        LIMIT ?;
    """
    return conn.execute(sql, (genre, start_year, end_year, n)).fetchall()

def query_multi_role_actors(conn: sqlite3.Connection) -> List[Tuple]:
    """Trouve les acteurs ayant plusieurs rôles (characters) dans le même film."""
    sql = """
        SELECT p.primaryName, m.primaryTitle, COUNT(c.name) as role_count
        FROM Persons p
        JOIN Characters c ON p.PID = c.PID
        JOIN Movies m ON c.MID = m.MID
        GROUP BY p.PID, m.MID
        HAVING role_count > 1
        ORDER BY role_count DESC
        LIMIT 20;
    """
    return conn.execute(sql).fetchall()

def query_director_actor_collaborations(conn: sqlite3.Connection, actor_name: str) -> List[Tuple]:
    """
    Compte le nombre de films réalisés par différents directeurs avec l'acteur donné.
    OPTIMISATION : '{actor_name}%'.
    """
    sql = """
        SELECT p_dir.primaryName as director_name, COUNT(d.MID) as movie_count
        FROM Directors d
        JOIN Persons p_dir ON d.PID = p_dir.PID
        WHERE d.MID IN (
            SELECT c.MID FROM Characters c
            JOIN Persons p_act ON c.PID = p_act.PID
            WHERE p_act.primaryName LIKE ?
        )
        GROUP BY p_dir.PID
        ORDER BY movie_count DESC;
    """
    return conn.execute(sql, (f'{actor_name}%',)).fetchall()

def query_popular_genres(conn: sqlite3.Connection) -> List[Tuple]:
    """Calcule le score moyen et le nombre de films par genre populaire."""
    sql = """
        SELECT g.genres, ROUND(AVG(r.averageRating), 2) as avg_rating, COUNT(g.MID) as movie_count
        FROM Genres g
        JOIN Movies m ON g.MID = m.MID
        JOIN Ratings r ON g.MID = r.MID
        WHERE m.titletype = 'movie'
        GROUP BY g.genres
        HAVING avg_rating > 7.0 AND movie_count > 50
        ORDER BY avg_rating DESC;
    """
    return conn.execute(sql).fetchall()

def query_actor_career_evolution(conn: sqlite3.Connection, actor_name: str) -> List[Tuple]:
    """Analyse l'évolution de carrière d'un acteur par décennie (nombre de films, note moyenne)."""
    sql = """
        WITH UserMovies AS (
            SELECT m.startYear, r.averageRating
            FROM Persons p
            JOIN Principals pr ON p.PID = pr.PID
            JOIN Movies m ON pr.MID = m.MID
            LEFT JOIN Ratings r ON m.MID = r.MID
            WHERE p.primaryName LIKE ? AND m.startYear IS NOT NULL
        )
        SELECT (startYear / 10) * 10 as decade, COUNT(*) as nb_films, ROUND(AVG(averageRating), 2) as avg_rating
        FROM UserMovies
        GROUP BY decade
        ORDER BY decade ASC;
    """
    return conn.execute(sql, (f'{actor_name}%',)).fetchall()

def query_top_movies_per_genre_ranked(conn: sqlite3.Connection) -> List[Tuple]:
    """Utilise une fonction de fenêtre (ROW_NUMBER) pour classer les meilleurs films par genre."""
    sql = """
        WITH RankedMovies AS (
            SELECT g.genres, m.primaryTitle, r.averageRating,
                ROW_NUMBER() OVER (PARTITION BY g.genres ORDER BY r.averageRating DESC, r.numVotes DESC) as rank
            FROM Movies m
            JOIN Genres g ON m.MID = g.MID
            JOIN Ratings r ON m.MID = r.MID
            WHERE r.numVotes > 10000 and m.titletype = 'movie'
        )
        SELECT genres, primaryTitle, averageRating, rank
        FROM RankedMovies WHERE rank <= 3 ORDER BY genres, rank;
    """
    return conn.execute(sql).fetchall()

def query_breakout_roles(conn: sqlite3.Connection) -> List[Tuple]:
    """Tente d'identifier les rôles qui ont été un 'saut de carrière' (breakthrough) pour les acteurs."""
    sql = """
        WITH Carriere AS (
            SELECT p.PID, p.primaryName as Nom, m.primaryTitle as Film, m.startYear, r.numVotes,
                ROW_NUMBER() OVER (PARTITION BY p.PID ORDER BY m.startYear ASC) as FilmNum
            FROM Persons p
            JOIN Characters c ON c.PID = p.PID
            JOIN Movies m ON c.MID = m.MID
            JOIN Ratings r ON m.MID = r.MID
            WHERE m.titletype = 'movie'
        ),
        Breakthrough AS (
            SELECT PID, Nom, Film, startYear, FilmNum
            FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY PID ORDER BY startYear ASC) as PremierSucces
                FROM Carriere WHERE numVotes > 200000
            ) 
            WHERE PremierSucces = 1
        )
        SELECT b.Nom, b.Film
        FROM Breakthrough b
        WHERE b.FilmNum > 1
        AND NOT EXISTS (
            SELECT 1 FROM Carriere c
            WHERE c.PID = b.PID AND c.startYear < b.startYear AND c.numVotes < 200000
        )
        ORDER BY b.Nom ASC
        LIMIT 20;
    """
    return conn.execute(sql).fetchall()

def query_golden_duos(conn: sqlite3.Connection) -> List[Tuple]:
    """Trouve les duos réalisateur/acteur ayant collaboré au moins 3 fois avec un score moyen élevé."""
    sql = """
        SELECT dir_p.primaryName as Director, act_p.primaryName as Actor,
            COUNT(m.MID) as collab_count, ROUND(AVG(r.averageRating), 2) as avg_score
        FROM Movies m
        JOIN Ratings r ON m.MID = r.MID
        JOIN Directors d ON m.MID = d.MID
        JOIN Persons dir_p ON d.PID = dir_p.PID
        JOIN Principals pr ON m.MID = pr.MID
        JOIN Persons act_p ON pr.PID = act_p.PID
        WHERE pr.category IN ('actor', 'actress')
        GROUP BY dir_p.PID, act_p.PID
        HAVING collab_count >= 3
        ORDER BY avg_score DESC
        LIMIT 20;
    """
    return conn.execute(sql).fetchall()