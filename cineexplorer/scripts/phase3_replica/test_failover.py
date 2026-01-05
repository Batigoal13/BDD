import time
import subprocess
import socket
from dataclasses import dataclass
from typing import Dict, List, Tuple

from pymongo import MongoClient, ReadPreference
from pymongo.write_concern import WriteConcern
from pymongo.errors import ConnectionFailure, OperationFailure, AutoReconnect


PRIMARY_SEED = ["mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0"]  # Tous les nœuds pour découverte
DB_NAME = "IMDB_DB"
TEST_COLL = "failover_test"
INSERT_COUNT = 5
READ_TIMEOUT_MS = 5_000

# Configuration des chemins pour redémarrer mongod
MONGOD_CONFIGS = {
	"27017": {
		"port": 27017,
		"dbpath": "data/mongo/db-1",
		"logpath": "data/mongo/logs/mongod-27017.log"
	},
	"27018": {
		"port": 27018,
		"dbpath": "data/mongo/db-2",
		"logpath": "data/mongo/logs/mongod-27018.log"
	},
	"27019": {
		"port": 27019,
		"dbpath": "data/mongo/db-3",
		"logpath": "data/mongo/logs/mongod-27019.log"
	}
}


@dataclass
class MemberState:
	name: str
	state_str: str
	health: int


def get_client(uri: str) -> MongoClient:
	return MongoClient(uri, serverSelectionTimeoutMS=READ_TIMEOUT_MS)


def get_rs_status(client: MongoClient) -> Dict:
	return client.admin.command("replSetGetStatus")


def describe_members(status: Dict) -> List[MemberState]:
	members = []
	for m in status.get("members", []):
		members.append(MemberState(name=m.get("name", ""), state_str=m.get("stateStr", ""), health=m.get("health", 0)))
	return members


def find_primary_and_secondaries(status: Dict) -> Tuple[str, List[str]]:
	primary = ""
	secondaries: List[str] = []
	for m in status.get("members", []):
		if m.get("stateStr") == "PRIMARY":
			primary = m.get("name", "")
		elif m.get("stateStr") == "SECONDARY":
			secondaries.append(m.get("name", ""))
	return primary, secondaries


def insert_docs(client: MongoClient, n: int) -> int:
	coll = client[DB_NAME].get_collection(TEST_COLL, write_concern=WriteConcern("majority"))
	docs = [{"_id": int(time.time() * 1000) + i, "payload": f"doc-{i}"} for i in range(n)]
	result = coll.insert_many(docs, ordered=True)
	return len(result.inserted_ids)


def insert_one_majority(client: MongoClient, payload: str) -> bool:
	coll = client[DB_NAME].get_collection(TEST_COLL, write_concern=WriteConcern("majority"))
	try:
		coll.insert_one({"_id": int(time.time() * 1000), "payload": payload})
		return True
	except Exception as exc:  # OperationFailure attendu quand pas de quorum
		print(f"Écriture bloquée (pas de quorum): {exc}")
		return False


def count_from_node(uri: str) -> int:
	client = get_client(uri)
	return client[DB_NAME][TEST_COLL].with_options(read_preference=ReadPreference.SECONDARY_PREFERRED).count_documents({})


def step_down_primary(client: MongoClient, stepdown_secs: int = 30):
	try:
		client.admin.command("replSetStepDown", stepdown_secs, secondaryCatchUpPeriodSecs=0)
	except (AutoReconnect, OperationFailure):
		pass  # attendu pendant le stepdown


def wait_for_primary(uri: str, timeout: float = 60.0, exclude_node: str = None) -> str:
	start = time.time()
	while time.time() - start < timeout:
		try:
			# Créer un nouveau client avec la seed complète pour découvrir le nouveau PRIMARY
			new_client = MongoClient(
				uri,
				serverSelectionTimeoutMS=2000,
				connectTimeoutMS=2000,
			)
			hello = new_client.admin.command("hello")
			if hello.get("isWritablePrimary"):
				primary = hello.get("me", "")
				# Si on exclut un nœud, vérifier que ce n'est pas celui-ci
				if exclude_node and primary == exclude_node:
					# Ancien PRIMARY toujours présent comme "PRIMARY", continuer à attendre
					time.sleep(1)
					continue
				return primary
		except ConnectionFailure:
			pass
		time.sleep(1)
	raise TimeoutError("Aucun PRIMARY détecté dans le délai imparti")


def shutdown_node(uri: str):
	try:
		# Timeout court pour éviter d'attendre trop longtemps
		client = MongoClient(uri, serverSelectionTimeoutMS=2000, connectTimeoutMS=2000, socketTimeoutMS=2000)
		# Envoyer la commande shutdown - elle ne retournera pas, exception attendue
		client.admin.command("shutdown", maxTimeMS=2000)
	except Exception:
		pass  # la connexion sera coupée, c'est normal


def restart_mongod(port: int) -> bool:
	"""Redémarre un nœud mongod sur le port spécifié"""
	port_str = str(port)
	if port_str not in MONGOD_CONFIGS:
		print(f"⚠️ Configuration inconnue pour le port {port}")
		return False
	
	# Attendre que le port soit vraiment libéré (quiesce mode peut prendre ~10-15s)
	print(f"Attente de la libération du port {port}...")
	for i in range(20):  # Attendre jusqu'à 20 secondes
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			result = s.connect_ex(('localhost', port))
			s.close()
			if result != 0:  # Port libre
				print(f"Port {port} libéré après {i+1} secondes")
				break
			time.sleep(1)
		except Exception:
			break
	else:
		print(f"⚠️ Timeout: port {port} toujours occupé après 20 secondes")
	
	config = MONGOD_CONFIGS[port_str]
	cmd = [
		"mongod",
		"--replSet", "rs0",
		"--port", str(config["port"]),
		"--dbpath", config["dbpath"],
		"--bind_ip", "localhost",
		"--fork",
		"--logpath", config["logpath"]
	]
	
	try:
		result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
		if result.returncode == 0:
			print(f"✅ mongod redémarré sur le port {port}")
			return True
		else:
			print(f"⚠️ Erreur lors du redémarrage de mongod:{port}: {result.stderr}")
			return False
	except Exception as e:
		print(f"⚠️ Exception lors du redémarrage: {e}")
		return False


def wait_for_secondary(client: MongoClient, node: str, timeout: float = 60.0) -> bool:
	"""Attend qu'un nœud devienne SECONDARY dans le replica set"""
	start = time.time()
	while time.time() - start < timeout:
		try:
			status = get_rs_status(client)
			for member in status.get("members", []):
				if member.get("name") == node and member.get("stateStr") == "SECONDARY":
					return True
		except Exception:
			pass
		time.sleep(2)
	return False


def main(double_failure: bool = False, hard_failure: bool = False):
	seed = PRIMARY_SEED[0]
	client = get_client(seed)

	print("[1] État initial")
	status = get_rs_status(client)
	primary, secondaries = find_primary_and_secondaries(status)
	for m in describe_members(status):
		print(f"- {m.name}: {m.state_str} (health={m.health})")

	if not primary:
		raise RuntimeError("Aucun PRIMARY détecté")

	print(f"PRIMARY: {primary}")
	print(f"SECONDARIES: {secondaries}")

	print("\n[2] Nettoyage de la collection de test")
	client[DB_NAME][TEST_COLL].drop()
	print(f"Collection {TEST_COLL} réinitialisée")

	print("\n[3] Insertion de documents avec writeConcern=majority")
	inserted = insert_docs(client, INSERT_COUNT)
	print(f"Insérés: {inserted}")
	time.sleep(2)

	print("\n[4] Vérification sur les secondaires")
	for sec in secondaries:
		uri = f"mongodb://{sec}/{DB_NAME}"
		count = count_from_node(uri)
		print(f"{sec} -> {count} documents dans {TEST_COLL}")

	# Vérifier que le PRIMARY est bien accessible avant de le tuer
	try:
		primary_client = get_client(f"mongodb://{primary}")
		hello = primary_client.admin.command("hello")
		if not hello.get("isWritablePrimary"):
			print(f"⚠️ {primary} n'est pas PRIMARY, vérifiez l'état du cluster")
			return
	except Exception as e:
		print(f"⚠️ Impossible de se connecter au PRIMARY {primary}: {e}")
		return
	
	failure_type = "SHUTDOWN (panne brutale)" if hard_failure else "STEPDOWN (gracieux)"
	print(f"\n[5] Panne du PRIMARY ({failure_type})")
	
	t0 = time.time()
	if hard_failure:
		print(f"Arrêt brutal du PRIMARY: {primary}")
		shutdown_node(f"mongodb://{primary}")
		# Le timer tourne - on mesure jusqu'à l'élection du nouveau PRIMARY
		print(f"Attente de l'élection du nouveau PRIMARY (heartbeat timeout + élection)...")
	else:
		print(f"Stepdown gracieux du PRIMARY: {primary}")
		step_down_primary(client)
	
	print(f"Mesure du temps d'élection...")
	new_primary = wait_for_primary(seed, timeout=60, exclude_node=primary if hard_failure else None)
	failover_time = time.time() - t0
	print(f"Nouveau PRIMARY: {new_primary} (failover ~{failover_time:.1f}s)")

	print("\n[6] Vérification des données après élection")
	new_client = get_client(seed)
	count_primary = new_client[DB_NAME][TEST_COLL].count_documents({})
	print(f"Count sur PRIMARY: {count_primary}")

	# Section 8: Redémarrage du nœud arrêté (hard_failure uniquement)
	if hard_failure:
		print(f"\n[8] Redémarrage du nœud arrêté: {primary}")
		# Extraire le numéro de port du PRIMARY arrêté
		port = int(primary.split(':')[1]) if ':' in primary else 27017
		
		if restart_mongod(port):
			print(f"Attente de la reconnexion de {primary} en tant que SECONDARY...")
			reconnected = wait_for_secondary(new_client, primary, timeout=60)
			
			if reconnected:
				print(f"✅ {primary} reconnecté en tant que SECONDARY")
				
				# Vérifier la synchronisation des données
				print("Vérification de la synchronisation des données...")
				time.sleep(3)  # Laisser le temps à la synchronisation initiale
				try:
					uri = f"mongodb://{primary}/{DB_NAME}"
					count_reconnected = count_from_node(uri)
					print(f"{primary} -> {count_reconnected} documents (après reconnexion)")
					
					if count_reconnected == count_primary:
						print(f"✅ Données synchronisées correctement")
					else:
						print(f"⚠️ Désynchronisation: {count_reconnected} vs {count_primary}")
				except Exception as e:
					print(f"⚠️ Erreur lors de la lecture depuis le nœud reconnecté: {e}")
			else:
				print(f"⚠️ Timeout: {primary} ne s'est pas reconnecté comme SECONDARY dans le délai imparti")
		else:
			print(f"⚠️ Échec du redémarrage de {primary}")

	print("\n[7] Relire sur un secondary")
	status_after = get_rs_status(new_client)
	_, secondaries_after = find_primary_and_secondaries(status_after)
	if secondaries_after:
		uri = f"mongodb://{secondaries_after[0]}/{DB_NAME}"
		try:
			count_sec = count_from_node(uri)
			print(f"{secondaries_after[0]} -> {count_sec} documents")
		except Exception as e:
			print(f"⚠️ Impossible de lire depuis {secondaries_after[0]}: {e}")

	if double_failure:
		print("\n[9] Simulation double panne: arrêt des deux SECONDARY, puis tentative d'écriture")
		if len(secondaries_after) < 2:
			print("⚠️ Moins de 2 secondaires détectés, la double panne ne sera pas représentative.")
		for sec in secondaries_after:
			shutdown_node(f"mongodb://{sec}")
			print(f"Secondary {sec} arrêté")
		time.sleep(2)
		success = insert_one_majority(new_client, "no-quorum-test")
		if success:
			print("⚠️ Écriture acceptée alors que le quorum devrait être perdu")
		else:
			print("✅ Écriture refusée (quorum indisponible)")

	print("\nTerminé.")


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description="Test de failover MongoDB replica set")
	parser.add_argument("--double-failure", action="store_true", help="Simuler une double panne (arrêt secondary + stepdown)")
	parser.add_argument("--hard-failure", action="store_true", help="Tester avec shutdown brutal du PRIMARY au lieu de stepdown gracieux")
	args = parser.parse_args()

	main(double_failure=args.double_failure, hard_failure=args.hard_failure)
