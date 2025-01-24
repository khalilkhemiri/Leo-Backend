from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
# MongoDB connection
client = MongoClient('mongodb+srv://khalilleo:khalilleo@cluster0.bfwkb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0', serverSelectionTimeoutMS=5000)
db = client["khalilleo"]
collection_cotisations = db["cotisations"]
collection_caisse_membre = db["caisse_membre"]
collection_actions = db["actions"]
def initialize_collections():
    dummy_data = {"init": True}
    if collection_cotisations.count_documents({}) == 0:
        collection_cotisations.insert_one(dummy_data)
    if collection_caisse_membre.count_documents({}) == 0:
        collection_caisse_membre.insert_one(dummy_data)
    if collection_actions.count_documents({}) == 0:
        collection_actions.insert_one(dummy_data)

initialize_collections()
# Add a cotisation
@app.route('/ajouter_cotisation', methods=['POST'])
def ajouter_cotisation():
    try:
        data = request.json
        nom = data.get('nom')
        montant = data.get('montant')
        
        membre = collection_cotisations.find_one({"nom": nom})
        if membre:
            nouveau_montant = float(membre.get("cotisation", 0)) + montant
            collection_cotisations.update_one({"nom": nom}, {"$set": {"cotisation": nouveau_montant}})
        else:
            numero = collection_cotisations.count_documents({}) + 1
            collection_cotisations.insert_one({"numero": numero, "nom": nom, "cotisation": montant})

        total_cotisations = sum(membre["cotisation"] for membre in collection_cotisations.find())
        collection_caisse_membre.delete_many({"libelle": {"$regex": "Total des cotisations"}})
        transaction = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "libelle": f"Total des cotisations : {total_cotisations:.2f} DT",
            "entree": montant,
            "sortie": 0,
            "total": total_cotisations,
        }
        collection_caisse_membre.insert_one(transaction)

        return jsonify({"status": "success", "message": "Cotisation enregistrée avec succès !"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur lors de l'ajout de la cotisation : {str(e)}"})

# Refresh cotisations
@app.route('/rafraichir_cotisations', methods=['GET'])
def rafraichir_cotisations():
    try:
        cotisations = list(collection_cotisations.find().sort("_id", -1).limit(100))
        return jsonify([{"numero": m["numero"], "nom": m["nom"], "cotisation": m["cotisation"]} for m in cotisations])
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur lors du rafraîchissement des cotisations : {str(e)}"})

# Add a caisse member transaction
@app.route('/ajouter_transaction_caisse_membre', methods=['POST'])
def ajouter_transaction_caisse_membre():
    try:
        data = request.json
        libelle = data.get('libelle')
        montant = data.get('montant')
        type_transaction = data.get('type_transaction')

        if type_transaction not in ["entrée", "sortie"]:
            return jsonify({"status": "error", "message": "Type invalide. Veuillez choisir 'entrée' ou 'sortie'."})

        derniere_transaction = collection_caisse_membre.find_one(sort=[("_id", -1)])
        total_actuel = derniere_transaction["total"] if derniere_transaction else 0
        if type_transaction == "entrée":
            total_actuel += montant
        else:
            total_actuel -= montant

        transaction = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "libelle": libelle,
            "entree": montant if type_transaction == "entrée" else 0,
            "sortie": montant if type_transaction == "sortie" else 0,
            "total": total_actuel,
        }
        collection_caisse_membre.insert_one(transaction)

        return jsonify({"status": "success", "message": "Transaction enregistrée avec succès !"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur lors de l'ajout de la transaction : {str(e)}"})

# Refresh caisse membre
@app.route('/rafraichir_caisse_membre', methods=['GET'])
def rafraichir_caisse_membre():
    try:
        transactions = list(collection_caisse_membre.find().sort("date", -1).limit(100))
        return jsonify([{
            "date": t["date"],
            "libelle": t["libelle"],
            "entree": t["entree"],
            "sortie": t["sortie"],
            "total": t["total"]
        } for t in transactions])
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur lors du rafraîchissement de la caisse membre : {str(e)}"})


@app.route('/ajouter_transaction', methods=['POST'])
def ajouter_transaction_action():
    try:
        data = request.get_json()
        action = data.get('action')
        libelle = data.get('libelle')
        montant = data.get('montant')
        type_transaction = data.get('type_transaction')

        # Debug: Print received data
        print(f"Received data - Action: {action}, Libellé: {libelle}, Montant: {montant}, Type: {type_transaction}")

        # Validate the transaction type
        if type_transaction not in ["entrée", "sortie"]:
            return jsonify({"error": "Type invalide. Veuillez choisir 'entrée' ou 'sortie'."}), 400

        # Create the transaction document
        transaction = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "libelle": libelle,
            "montant": montant,
            "type": type_transaction,
        }

        # Insert the transaction into the database
        result = collection_actions.insert_one(transaction)

        # Verify that the transaction was inserted
        if result.inserted_id:
            print("Transaction successfully inserted into MongoDB.")
            return jsonify({"message": "Transaction enregistrée avec succès !"}), 200
        else:
            return jsonify({"error": "Failed to insert transaction into MongoDB."}), 500
    except Exception as e:
        print(f"Error inserting transaction into MongoDB: {str(e)}")
        return jsonify({"error": f"Erreur lors de l'ajout de la transaction : {str(e)}"}), 500

@app.route('/historique_action', methods=['GET'])
def afficher_historique_action():
    try:
        action = request.args.get('action')
        transactions = list(collection_actions.find({"action": action}))
        return jsonify([{
            "date": t["date"], 
            "libelle": t["libelle"], 
            "type": t["type"], 
            "montant": t["montant"]
        } for t in transactions]), 200
    except Exception as e:
        return jsonify({"error": f"Erreur lors de l'affichage de l'historique : {str(e)}"}), 500

@app.route('/rafraichir_actions', methods=['GET'])
def rafraichir_actions():
    try:
        # Fetch the latest transactions from the database
        transactions = list(collection_actions.find().sort("date", -1).limit(100))
        return jsonify([{
            "date": t["date"], 
            "libelle": t["libelle"], 
            "type": t["type"], 
            "montant": t["montant"]
        } for t in transactions]), 200
    except Exception as e:
        return jsonify({"error": f"Erreur lors du rafraîchissement des actions : {str(e)}"}), 500

@app.route('/total_cotisations', methods=['GET'])
def mettre_a_jour_total_cotisations():
    try:
        total_cotisations = sum(membre["cotisation"] for membre in collection_cotisations.find())
        return jsonify({"total_cotisations": total_cotisations}), 200
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la mise à jour du total des cotisations : {str(e)}"}), 500

@app.route('/dashboard_caisse_membre', methods=['GET'])
def mettre_a_jour_dashboard_caisse_membre():
    try:
        actions = collection_actions.distinct("action")
        # Return a default empty graph data along with actions
        return jsonify({"actions": actions, "graph_data": {"entrees": 0, "sorties": 0}}), 200
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la mise à jour du dashboard : {str(e)}"}), 500

@app.route('/dashboard_caisse_action', methods=['GET'])
def mettre_a_jour_dashboard_caisse_action():
    try:
        transactions = list(collection_actions.find())
        total_entrees = sum(t["montant"] for t in transactions if t["type"] == "entrée")
        total_sorties = sum(t["montant"] for t in transactions if t["type"] == "sortie")
        solde = total_entrees - total_sorties

        return jsonify({
            "total_entrees": total_entrees, 
            "total_sorties": total_sorties, 
            "solde": solde
        }), 200
    except Exception as e:  
        return jsonify({"error": f"Erreur lors de la mise à jour du graphique : {str(e)}"}), 500

@app.route('/graphique_caisse_membre', methods=['GET'])
def mettre_a_jour_graphique_caisse_membre():
    try:
        action = request.args.get('action')
        transactions = list(collection_actions.find({"action": action}))
        total_entrees = sum(t.get("montant", 0) for t in transactions if t.get("type") == "entrée")
        total_sorties = sum(t.get("montant", 0) for t in transactions if t.get("type") == "sortie")
        return jsonify({"entrees": total_entrees, "sorties": total_sorties}), 200
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la mise à jour du graphique : {str(e)}"}), 500

@app.route('/graphique_caisse_action', methods=['GET'])
def mettre_a_jour_graphique_caisse_action():
    try:
        transactions = list(collection_actions.find())
        total_entrees = sum(t["montant"] for t in transactions if t["type"] == "entrée")
        total_sorties = sum(t["montant"] for t in transactions if t["type"] == "sortie")
        return jsonify({"entrees": total_entrees, "sorties": total_sorties}), 200
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la mise à jour du graphique : {str(e)}"}), 500

@app.route('/liste_actions', methods=['GET'])
def mettre_a_jour_liste_actions():
    try:
        actions = collection_actions.distinct("action")
        return jsonify({"actions": actions}), 200
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la mise à jour de la liste des actions : {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
