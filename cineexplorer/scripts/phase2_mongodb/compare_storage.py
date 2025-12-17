from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "IMDB_DB"

# Liste des collections "Sources" qui composent un film
SOURCE_COLLS = ["Movies", "Ratings", "Genres", "Principals", "Directors", "Writers", "Titles", "Persons", "Characters"]

TARGET_COLL = "movies_complete_ALL"

def format_bytes(size):
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def compare_storage():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print(f"📊 Analyse du stockage pour {DB_NAME}...\n")

    # 1. Calcul taille Source (Flat)
    total_source_size = 0
    print("Collections Plates (Source) :")
    for coll_name in SOURCE_COLLS:
        try:
            stats = db.command("collstats", coll_name)
            size = stats['storageSize'] # Taille compressée sur disque
            total_source_size += size
            print(f"  - {coll_name:<12} : {format_bytes(size)}")
        except:
            print(f"  - {coll_name:<12} : (Non trouvée)")
    
    print(f"  ---------------------------")
    print(f"  TOTAL SOURCE   : {format_bytes(total_source_size)}\n")

    # 2. Calcul taille Cible (Structured)
    try:
        stats = db.command("collstats", TARGET_COLL)
        target_size = stats['storageSize']
        print(f"Collection Structurée (Cible) :")
        print(f"  TOTAL CIBLE    : {format_bytes(target_size)}\n")
        
        # Comparaison
        diff = target_size - total_source_size
        percent = (diff / total_source_size) * 100
        
        print("="*40)
        print("VERDICT STOCKAGE")
        if diff > 0:
            print(f"📈 Augmentation : +{percent:.2f}%")
            print("Note : C'est normal (duplication des données vs références).")
        else:
            print(f"📉 Diminution : {percent:.2f}%")
            print("Note : Possible grâce à la compression Snappy/Zstd de MongoDB.")
        print("="*40)
            
    except Exception as e:
        print(f"Erreur lecture cible : {e}")

if __name__ == "__main__":
    compare_storage()

#"Bien que la dénormalisation entraîne une redondance logique des données (duplication des noms d'acteurs, genres, etc.), la taille physique sur le disque diminue de 44%. Cela s'explique par la suppression de la surcharge administrative (overhead) de millions de petits documents (notamment dans la collection de jointure 'Principals') et par l'efficacité de la compression native de MongoDB qui gère très bien les données redondantes."


# Puisque IMDb est un site de consultation (on lit les fiches films 99% du temps, on modifie rarement le casting d'un vieux film), la complexité réduite du code de lecture en MongoDB est un immense avantage, malgré la difficulté des mises à jour.