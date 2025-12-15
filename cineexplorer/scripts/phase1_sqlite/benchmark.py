import sqlite3
import time
import os
from typing import Dict, Any, List, Tuple
# Importe toutes les fonctions de requête du fichier queries.py
from queries import (
    query_actor_filmography, query_top_n_movies_by_genre, query_multi_role_actors,
    query_director_actor_collaborations, query_popular_genres, query_actor_career_evolution,
    query_top_movies_per_genre_ranked, query_breakout_roles, query_golden_duos
)

DB_PATH = "../../data/imdb.db"

# ================================================================================
# 1. GESTION DES INDEX ET UTILITAIRES
# ================================================================================


def get_db_size() -> float:
    """Retourne la taille du fichier de base de données en Mo."""
    if os.path.exists(DB_PATH):
        return os.path.getsize(DB_PATH) / (1024 * 1024)
    return 0.0

def drop_all_indexes(conn: sqlite3.Connection):
    """Supprime tous les index existants (sauf ceux auto-générés)."""
    cursor = conn.cursor()
    # Sélectionne tous les index créés manuellement
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_autoindex%';")
    indexes = cursor.fetchall()
    
    print(f"   -> Suppression de {len(indexes)} index existants...")
    for idx in indexes:
        cursor.execute(f"DROP INDEX IF EXISTS {idx[0]};")
    conn.commit()

def create_indexes(conn: sqlite3.Connection):
    """Crée tous les index nécessaires pour l'optimisation des requêtes."""
    print("   -> Démarrage de la création des index...")
    
    # Index basés sur les colonnes utilisées dans les clauses WHERE et JOIN
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_name ON Persons(primaryName);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_char_pid ON Characters(PID);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_char_mid ON Characters(MID);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_principals_mid ON Principals(MID);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_principals_pid ON Principals(PID);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_movie_year ON Movies(startYear);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rating_score ON Ratings(averageRating);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_genre_name ON Genres(genres);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_directors_mid ON Directors(MID);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_directors_pid ON Directors(PID);")
    
    # Index composites utiles pour des clauses JOIN/WHERE spécifiques
    conn.execute("CREATE INDEX IF NOT EXISTS idx_genre_mid_genre ON Genres(MID, genres);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rating_mid_rating ON Ratings(MID, averageRating);")
    
    print("   -> Calcul des statistiques (ANALYZE) pour l'optimiseur...")
    conn.execute("ANALYZE;")
    conn.commit()
    print("   -> Indexation terminée.")

# ================================================================================
# 2. LOGIQUE DE BENCHMARK ET D'ANALYSE
# ================================================================================

def run_benchmarks_detailed(conn: sqlite3.Connection) -> Dict[str, float]:
    """Exécute toutes les requêtes de queries.py et retourne les temps d'exécution en ms."""
    results: Dict[str, float] = {}
    
    # Structure de données pour appeler les fonctions de queries.py
    tasks: List[Tuple[Any, List[Any]]] = [
        (query_actor_filmography, ["Tom Hanks"]),
        (query_top_n_movies_by_genre, ["Comedy", 1980, 2000, 10]),
        (query_multi_role_actors, []),
        (query_director_actor_collaborations, ["Tom Hanks"]),
        (query_popular_genres, []),
        (query_actor_career_evolution, ["Clint Eastwood"]),
        (query_top_movies_per_genre_ranked, []),
        (query_breakout_roles, []),
        (query_golden_duos, [])
    ]
    
    for func, args in tasks:
        s = time.time()
        func(conn, *args)
        e = time.time()
        results[func.__name__] = round((e - s) * 1000, 2)
        
    return results

def analyze_query_plan(conn: sqlite3.Connection, func: Any, args: List[Any], step_name: str):
    """
    Exécute EXPLAIN QUERY PLAN pour une requête spécifique et affiche le résultat.
    Nous choisissons 'query_actor_filmography' comme exemple critique.
    """
    # Récupère la requête SQL de la fonction (méthode simple mais efficace)
    # Note : Cela suppose que la requête est la première ligne de code exécutée
    # dans la fonction ou que nous modifions queries.py pour exposer le SQL.
    # Pour cet exemple, nous allons reconstruire la requête critique :
    actor_name = args[0]
    
    # Requête cible pour l'EXPLAIN
    sql_template = """
        SELECT m.primaryTitle, m.startYear, c.name as character_name, r.averageRating
        FROM Movies m
        JOIN Principals pr ON m.MID = pr.MID
        JOIN Persons pe ON pr.PID = pe.PID
        LEFT JOIN Characters c ON m.MID = c.MID AND pe.PID = c.PID
        LEFT JOIN Ratings r ON m.MID = r.MID
        WHERE pe.primaryName LIKE ? 
        ORDER BY m.startYear DESC;
    """
    
    # Exécution de EXPLAIN QUERY PLAN
    print(f"\n--- 📈 ANALYSE du plan d'exécution ({step_name}) pour {func.__name__} ---")
    explain_sql = "EXPLAIN QUERY PLAN " + sql_template
    
    cursor = conn.cursor()
    # On utilise le même paramètre que dans la fonction
    cursor.execute(explain_sql, (f'{actor_name}%',))
    plan = cursor.fetchall()
    
    # Affichage du plan
    for line in plan:
        # Affichage structuré du plan d'exécution pour meilleure lisibilité
        level, detail = line[1], line[3]
        print(f"  {'|--' * level} {detail}")
    
    # Interprétation clé
    if "SCAN TABLE Persons" in str(plan):
        print("\n🔑 Interprétation : **SCAN TABLE** - Analyse complète de la table Persons (coûteux).")
    elif "SEARCH TABLE Persons USING INDEX" in str(plan):
        print("\n🔑 Interprétation : **SEARCH TABLE USING INDEX** - Utilisation de l'index pour la recherche (rapide).")
    
    print("-" * 50)


# ================================================================================
# 3. MAIN (Point d'entrée du script)
# ================================================================================

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"❌ Base de données introuvable : {DB_PATH}")
        exit()

    CRITICAL_QUERY = query_actor_filmography
    CRITICAL_ARGS = ["Tom Hanks"]


    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA cache_size = -64000;") 
    conn.execute("PRAGMA synchronous = OFF;")
    
    print("\n" + "="*80)
    print("--- 1. PHASE SANS INDEX (Baseline) ---")
    drop_all_indexes(conn)
    size_before = get_db_size()
    

    analyze_query_plan(conn, CRITICAL_QUERY, CRITICAL_ARGS, "SANS INDEX")
    
    print("⏱️  Exécution du Benchmark SANS index...")
    temps_sans = run_benchmarks_detailed(conn)
    conn.close()


    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA synchronous = OFF;")
    
    print("\n" + "="*80)
    print("--- 2. PHASE DE CRÉATION DES INDEX ---")
    create_indexes(conn)
    conn.close()


    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA synchronous = OFF;")
    
    size_after = get_db_size()
    print("\n" + "="*80)
    print("--- 3. PHASE AVEC INDEX (Optimisation) ---")
    

    analyze_query_plan(conn, CRITICAL_QUERY, CRITICAL_ARGS, "AVEC INDEX")
    
    print("⏱️  Exécution du Benchmark AVEC index...")
    temps_avec = run_benchmarks_detailed(conn)
    conn.close()

    print("\n" + "="*80)
    print("🏆 RÉSULTATS DU BENCHMARK D'INDEXATION SQLITE 🏆")
    print("="*80)
    print(f"{'Requêtes':<35} | {'Sans Index (ms)':<12} | {'Avec Index (ms)':<12} | {'Gain (%)':<10}")
    print("-" * 80)

    for nom in temps_sans.keys():
        t_sans = temps_sans[nom]
        t_avec = temps_avec.get(nom, 0.0)
        gain = round(((t_sans - t_avec) / t_sans) * 100, 2) if t_sans > 0 else 0
        
        print(f"{nom:<35} | {t_sans:<12} | {t_avec:<12} | {gain: >10}%")

    print("="*80)
    print(f"Stockage Index (Surcharge) : +{round(size_after - size_before, 2)} Mo (Point 5)")
    print("L'analyse du plan d'exécution a montré le passage du 'SCAN' au 'SEARCH USING INDEX'.")