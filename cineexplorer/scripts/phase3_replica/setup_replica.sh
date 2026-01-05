set -euo pipefail

# Script de démarrage des 3 nœuds et d'initialisation du replica set.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DB1="$ROOT/data/mongo/db-1"
DB2="$ROOT/data/mongo/db-2"
DB3="$ROOT/data/mongo/db-3"
LOG_DIR="$ROOT/data/mongo/logs"

mkdir -p "$LOG_DIR"

command -v mongod >/dev/null || { echo "❌ mongod introuvable dans le PATH"; exit 1; }
command -v mongosh >/dev/null || { echo "❌ mongosh introuvable dans le PATH"; exit 1; }

start_node() {
	local port="$1" dbpath="$2" logfile="$3"

	if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
		echo "ℹ️  mongod déjà présent sur le port $port, on ne relance pas."
		return 0
	fi

	echo "🚀 Démarrage mongod port $port (dbpath=$dbpath)"
	mongod --replSet rs0 --port "$port" --dbpath "$dbpath" --bind_ip localhost \
				 --fork --logpath "$logfile"
}

start_node 27017 "$DB1" "$LOG_DIR/mongod-27017.log"
start_node 27018 "$DB2" "$LOG_DIR/mongod-27018.log"
start_node 27019 "$DB3" "$LOG_DIR/mongod-27019.log"

RS_NAME="$(mongosh --quiet --port 27017 --eval 'db.hello().setName || ""')"
if [[ -z "$RS_NAME" ]]; then
	echo "🛠 Initialisation du replica set rs0"
	mongosh --quiet --port 27017 --eval 'rs.initiate({_id:"rs0",members:[{_id:0,host:"localhost:27017"},{_id:1,host:"localhost:27018"},{_id:2,host:"localhost:27019"}]})'
else
	echo "ℹ️  Replica set déjà configuré ($RS_NAME), pas de rs.initiate."
fi

# Attente que le PRIMARY soit élu
echo "⏳ Attente du PRIMARY..."
mongosh --quiet --port 27017 --eval 'while(!db.hello().isWritablePrimary){ sleep(200); } ; printjson(db.hello())'

echo "✅ Replica set prêt."
