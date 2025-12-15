import sqlite3
import pandas as pd
import time
import re
import os
from typing import List, Tuple, Set

# --- CONFIGURATION ---
DB_PATH = "../../data/imdb.db"
CSV_DIR = "../../data/csv/"

# Liste ordonnée
TABLE_CONFIG: List[Tuple[str, str]] = [
    ("Movies", "movies.csv"),
    ("Persons", "persons.csv"),
    ("Genres", "genres.csv"),
    ("Professions", "professions.csv"),
    ("Ratings", "ratings.csv"),
    ("Episodes", "episodes.csv"),
    ("Titles", "titles.csv"),
    ("KnownForMovies", "knownformovies.csv"),
    ("Directors", "directors.csv"),
    ("Writers", "writers.csv"),
    ("Principals", "principals.csv"),
    ("Characters", "characters.csv"),
]

def get_valid_ids(conn: sqlite3.Connection) -> Tuple[Set[str], Set[str]]:
    """Récupère tous les MID et PID existants pour filtrer les orphelins."""
    print("🔄 Chargement des IDs valides (MID/PID) pour le filtrage...")
    
    # On utilise des set() pour une recherche instantanée (O(1))
    try:
        mids = set(row[0] for row in conn.execute("SELECT MID FROM Movies"))
        pids = set(row[0] for row in conn.execute("SELECT PID FROM Persons"))
        print(f"   ℹ️ {len(mids)} Films valides et {len(pids)} Personnes valides chargés en mémoire.")
        return mids, pids
    except Exception as e:
        print(f"⚠️ Impossible de charger les IDs (tables vides ?) : {e}")
        return set(), set()

def clean_column_names(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    new_columns = []
    global_mapping = {
        'mid': 'MID', 'pid': 'PID', 'tconst': 'MID', 'nconst': 'PID',
        'parentmid': 'parentMID', 'parenttconst': 'parentMID',
        'titletype': 'titletype', 'primarytitle': 'primaryTitle',
        'originaltitle': 'originalTitle', 'isadult': 'isAdult',
        'startyear': 'startYear', 'endyear': 'endYear',
        'runtimeminutes': 'runtimeMinutes', 'primaryname': 'primaryName',
        'birthyear': 'birthYear', 'deathyear': 'deathYear',
        'averagerating': 'averageRating', 'numvotes': 'numVotes',
        'seasonnumber': 'seasonNumber', 'episodenumber': 'episodeNumber',
        'isoriginaltitle': 'isOriginalTitle',
        'genre': 'genres'
    }

    for col in df.columns:
        clean_col = re.sub(r"[()',]", "", str(col)).strip().lower()
        final_name = global_mapping.get(clean_col, clean_col)
        
        if table_name == 'Titles' and clean_col in ['ordering', 'ordre']:
            final_name = 'ordre'
        elif table_name == 'Principals' and clean_col in ['ordering', 'ordre']:
            final_name = 'ordering'
        elif table_name == 'Characters' and clean_col in ['character', 'name', 'characters']:
            final_name = 'name'
        elif table_name == 'Professions' and clean_col in ['jobname', 'profession', 'primaryprofession']:
            final_name = 'jobname'
            
        new_columns.append(final_name)
    df.columns = new_columns
    return df

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Conversion Booléens
    for col in ['isAdult', 'isOriginalTitle']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    # 2. Conversion Entiers (avec support NULL)
    int_cols = ['startYear', 'endYear', 'runtimeMinutes', 'birthYear', 'deathYear', 
                'numVotes', 'seasonNumber', 'episodeNumber', 'ordre', 'ordering']
    for col in int_cols:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors='coerce').astype('Int64')
            df[col] = s.astype(object).where(s.notnull(), None)

    return df.where(pd.notnull(df), None)

def filter_orphans(df: pd.DataFrame, table_name: str, valid_mids: Set[str], valid_pids: Set[str]) -> pd.DataFrame:
    """Supprime les lignes qui font référence à des IDs inexistants."""
    original_len = len(df)
    
    # Filtrer sur MID (Film ID)
    if 'MID' in df.columns and valid_mids:
        df = df[df['MID'].isin(valid_mids)]
    
    # Filtrer sur PID (Person ID)
    if 'PID' in df.columns and valid_pids:
        df = df[df['PID'].isin(valid_pids)]
        
    # Cas spécial Episodes : parentMID doit aussi être un film valide
    if table_name == 'Episodes' and 'parentMID' in df.columns and valid_mids:
        df = df[df['parentMID'].isin(valid_mids)]
        
    filtered_len = len(df)
    diff = original_len - filtered_len
    if diff > 0:
        print(f"   ✂️ {diff} orphelins supprimés (Clés étrangères invalides).")
        
    return df

def import_table(conn: sqlite3.Connection, table_name: str, filename: str, valid_mids: Set[str], valid_pids: Set[str]) -> int:
    csv_path = os.path.join(CSV_DIR, filename)
    if not os.path.exists(csv_path):
        print(f"⚠️  Fichier introuvable : {filename}")
        return 0

    print(f"📥 Import de {table_name}...")
    start_t = time.time()
    
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        df = clean_column_names(df, table_name)
        df = clean_data(df)
        
        # --- NOUVEAUTÉ : FILTRAGE DES ORPHELINS ---
        # On ne filtre pas Movies/Persons car ce sont les parents
        if table_name not in ['Movies', 'Persons']:
            df = filter_orphans(df, table_name, valid_mids, valid_pids)

        # Récupération des colonnes valides SQL
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        valid_columns = [row[1] for row in cursor.fetchall()]
        common_cols = [c for c in df.columns if c in valid_columns]
        
        if not common_cols:
            print(f"❌ Erreur: Aucune colonne valide pour {table_name}.")
            return 0
            
        df_final = df[common_cols]
        
        # Requête SQL
        cols_str = ", ".join(common_cols)
        placeholders = ", ".join(["?"] * len(common_cols))
        sql = f"INSERT OR IGNORE INTO {table_name} ({cols_str}) VALUES ({placeholders})"
        
        data = [tuple(x) for x in df_final.to_numpy()]
        conn.executemany(sql, data)
        conn.commit()
        
        elapsed = time.time() - start_t
        print(f"✅ {len(data)} lignes insérées dans {table_name} ({elapsed:.2f}s)")
        return len(data)

    except Exception as e:
        print(f"❌ Erreur critique sur {table_name}: {e}")
        conn.rollback()
        return 0

def main():
    if not os.path.exists(DB_PATH):
        print("❌ Erreur: Base introuvable. Lancez create_schema.py.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA foreign_keys = ON")
    
    print(f"🚀 Démarrage de l'importation...")
    print("=" * 60)

    total_rows = 0
    t_start = time.time()

    # 1. On charge d'abord les Parents
    parents = [t for t in TABLE_CONFIG if t[0] in ['Movies', 'Persons']]
    others = [t for t in TABLE_CONFIG if t[0] not in ['Movies', 'Persons']]
    
    # Variables pour stocker les IDs valides
    valid_mids = set()
    valid_pids = set()

    # Import des Parents
    for table, file in parents:
        rows = import_table(conn, table, file, set(), set()) # Pas de filtrage pour les parents
        total_rows += rows

    # 2. Une fois Movies et Persons remplis, on charge leurs IDs en mémoire
    # C'est CRUCIAL pour nettoyer les tables suivantes
    valid_mids, valid_pids = get_valid_ids(conn)

    # Import des Enfants (avec filtrage)
    for table, file in others:
        rows = import_table(conn, table, file, valid_mids, valid_pids)
        total_rows += rows

    conn.close()
    print("=" * 60)
    print(f"🏁 Terminé ! Total : {total_rows} lignes importées en {time.time() - t_start:.2f}s.")

if __name__ == "__main__":
    main()