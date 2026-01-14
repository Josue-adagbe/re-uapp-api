from flask import Flask, request, jsonify
import hashlib
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Configuration
CLE_MASTER = "RECUSAPP_BENIN_2026_SECURE"
PRIX_LICENCE = 2500

# Base de données en mémoire
paiements = {}
licences = {}

def generer_code_activation(entreprise, device_id):
    """Génère un code d'activation unique"""
    date_str = datetime.now().strftime("%Y%m%d")
    base = CLE_MASTER + entreprise.upper() + device_id + "PAYANTE" + date_str
    hash_complet = hashlib.sha256(base.encode()).hexdigest()
    code = f"{hash_complet[:4]}-{hash_complet[4:8]}-{hash_complet[8:12]}".upper()
    return code

@app.route('/')
def home():
    return jsonify({
        "app": "RecusApp API",
        "version": "1.0",
        "status": "running"
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/test')
def test():
    return jsonify({
        "message": "API fonctionne!",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
