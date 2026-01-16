from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib
from datetime import datetime, timedelta
import os
import secrets
import requests
import hmac

app = Flask(__name__)
CORS(app)

# Configuration
CLE_MASTER = "RECUSAPP_BENIN_2026_SECURE"
PRIX_LICENCE = 2500
DUREE_LICENCE_JOURS = 365

# Clés FedaPay (on utilisera sandbox pour les tests)
FEDAPAY_SECRET_KEY = os.environ.get('FEDAPAY_SECRET_KEY', 'sk_sandbox_test')
FEDAPAY_PUBLIC_KEY = os.environ.get('FEDAPAY_PUBLIC_KEY', 'pk_sandbox_test')
FEDAPAY_MODE = os.environ.get('FEDAPAY_MODE', 'sandbox')  # 'sandbox' ou 'live'

# URLs FedaPay
FEDAPAY_API_URL = "https://sandbox-api.fedapay.com/v1" if FEDAPAY_MODE == 'sandbox' else "https://api.fedapay.com/v1"

# Base de données en mémoire
paiements = {}
licences = {}

# =========================
# UTILITAIRES
# =========================

def generer_code_activation(entreprise, device_id):
    """Génère un code d'activation unique"""
    date_str = datetime.now().strftime("%Y%m%d")
    base = CLE_MASTER + entreprise.upper() + device_id + "PAYANTE" + date_str
    hash_complet = hashlib.sha256(base.encode()).hexdigest()
    code = f"{hash_complet[:4]}-{hash_complet[4:8]}-{hash_complet[8:12]}".upper()
    return code

def generer_transaction_id():
    """Génère un ID unique de transaction"""
    return secrets.token_hex(16).upper()

def valider_code_activation(code, entreprise, device_id):
    """Valide un code d'activation"""
    code_nettoye = code.strip().upper().replace("-", "")
    
    for i in range(30):
        date_test = datetime.now() - timedelta(days=i)
        date_str = date_test.strftime("%Y%m%d")
        
        base = CLE_MASTER + entreprise.upper() + device_id + "PAYANTE" + date_str
        hash_complet = hashlib.sha256(base.encode()).hexdigest()
        code_attendu = f"{hash_complet[:12]}".upper()
        
        if code_nettoye == code_attendu:
            return True
    
    return False

# =========================
# FEDAPAY - FONCTIONS
# =========================

def creer_transaction_fedapay(montant, entreprise, device_id, callback_url):
    """
    Crée une transaction FedaPay
    
    Retourne:
    {
        "success": True,
        "transaction_id": "xxx",
        "checkout_url": "https://checkout.fedapay.com/xxx"
    }
    """
    try:
        headers = {
            "Authorization": f"Bearer {FEDAPAY_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "description": f"Licence RecusApp - {entreprise}",
            "amount": montant,
            "currency": {
                "iso": "XOF"
            },
            "callback_url": callback_url,
            "customer": {
                "firstname": entreprise,
                "lastname": "Client",
                "email": f"client-{device_id[:8]}@recusapp.com"
            }
        }
        
        response = requests.post(
            f"{FEDAPAY_API_URL}/transactions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            transaction = result.get('v1/transaction', result)
            
            # Générer le token pour obtenir l'URL de checkout
            token_response = requests.post(
                f"{FEDAPAY_API_URL}/transactions/{transaction['id']}/token",
                headers=headers,
                timeout=10
            )
            
            if token_response.status_code == 200:
                token_data = token_response.json()
                checkout_url = token_data.get('url', token_data.get('token', {}).get('url'))
                
                return {
                    "success": True,
                    "transaction_id": transaction['id'],
                    "checkout_url": checkout_url
                }
        
        return {
            "success": False,
            "error": f"Erreur FedaPay: {response.text}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Erreur de connexion: {str(e)}"
        }

def verifier_signature_webhook(payload, signature):
    """Vérifie la signature du webhook FedaPay"""
    try:
        expected_signature = hmac.new(
            FEDAPAY_SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    except:
        return False

# =========================
# ROUTES DE BASE
# =========================

@app.route('/')
def home():
    return jsonify({
        "app": "RecusApp API",
        "version": "3.0",
        "status": "running",
        "fedapay_mode": FEDAPAY_MODE,
        "endpoints": {
            "/health": "Health check",
            "/paiement/initier": "Initier un paiement FedaPay",
            "/paiement/verifier/<transaction_id>": "Vérifier un paiement",
            "/code/valider": "Valider un code d'activation",
            "/webhook/fedapay": "Webhook FedaPay (automatique)",
            "/stats": "Statistiques"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# =========================
# PAIEMENT AUTOMATIQUE FEDAPAY
# =========================

@app.route('/paiement/initier', methods=['POST'])
def initier_paiement():
    """
    Initie un paiement automatique via FedaPay
    
    POST Body:
    {
        "entreprise": "Boutique Marie",
        "device_id": "A1B2C3D4E5"
    }
    
    Retourne:
    {
        "success": true,
        "transaction_id": "xxx",
        "checkout_url": "https://checkout.fedapay.com/xxx",
        "montant": 2500
    }
    """
    try:
        data = request.json
        entreprise = data.get('entreprise')
        device_id = data.get('device_id')
        
        if not entreprise or not device_id:
            return jsonify({
                "success": False,
                "error": "Données manquantes"
            }), 400
        
        # Générer un ID local
        local_transaction_id = generer_transaction_id()
        
        # Créer la transaction FedaPay
        callback_url = f"https://re-uapp-api.onrender.com/webhook/fedapay"
        
        fedapay_result = creer_transaction_fedapay(
            PRIX_LICENCE,
            entreprise,
            device_id,
            callback_url
        )
        
        if not fedapay_result.get('success'):
            return jsonify(fedapay_result), 500
        
        # Sauvegarder la transaction
        paiements[local_transaction_id] = {
            "entreprise": entreprise,
            "device_id": device_id,
            "montant": PRIX_LICENCE,
            "statut": "en_attente",
            "fedapay_transaction_id": fedapay_result['transaction_id'],
            "date_creation": datetime.now().isoformat(),
            "code": None
        }
        
        return jsonify({
            "success": True,
            "transaction_id": local_transaction_id,
            "checkout_url": fedapay_result['checkout_url'],
            "montant": PRIX_LICENCE,
            "message": "Ouvrez cette URL pour payer automatiquement"
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/paiement/verifier/<transaction_id>')
def verifier_paiement(transaction_id):
    """Vérifie le statut d'un paiement"""
    
    if transaction_id not in paiements:
        return jsonify({
            "success": False,
            "error": "Transaction introuvable"
        }), 404
    
    paiement = paiements[transaction_id]
    
    return jsonify({
        "success": True,
        "transaction_id": transaction_id,
        "statut": paiement['statut'],
        "code": paiement.get('code'),
        "date_paiement": paiement.get('date_paiement'),
        "entreprise": paiement['entreprise']
    })

# =========================
# WEBHOOK FEDAPAY (AUTOMATIQUE)
# =========================

@app.route('/webhook/fedapay', methods=['POST'])
def webhook_fedapay():
    """
    Webhook appelé automatiquement par FedaPay après paiement
    C'est ici que la magie opère !
    """
    try:
        # Récupérer les données
        payload = request.get_data(as_text=True)
        signature = request.headers.get('X-Fedapay-Signature', '')
        
        # Vérifier la signature (en production)
        # if FEDAPAY_MODE == 'live' and not verifier_signature_webhook(payload, signature):
        #     return jsonify({"error": "Invalid signature"}), 401
        
        data = request.json
        
        # Extraire les informations
        event_type = data.get('entity', {}).get('event', data.get('event'))
        transaction_data = data.get('entity', {}).get('transaction', data)
        
        fedapay_transaction_id = transaction_data.get('id')
        status = transaction_data.get('status')
        
        # Trouver notre transaction locale
        local_transaction = None
        local_transaction_id = None
        
        for tid, paiement in paiements.items():
            if paiement.get('fedapay_transaction_id') == fedapay_transaction_id:
                local_transaction = paiement
                local_transaction_id = tid
                break
        
        if not local_transaction:
            return jsonify({
                "success": False,
                "message": "Transaction locale introuvable"
            }), 404
        
        # Si le paiement est approuvé
        if status in ['approved', 'transferred']:
            # Générer le code d'activation
            code = generer_code_activation(
                local_transaction['entreprise'],
                local_transaction['device_id']
            )
            
            # Mettre à jour la transaction
            local_transaction['statut'] = 'payé'
            local_transaction['code'] = code
            local_transaction['date_paiement'] = datetime.now().isoformat()
            local_transaction['fedapay_status'] = status
            
            # Créer la licence
            date_expiration = datetime.now() + timedelta(days=DUREE_LICENCE_JOURS)
            licences[code] = {
                "entreprise": local_transaction['entreprise'],
                "device_id": local_transaction['device_id'],
                "date_activation": datetime.now().isoformat(),
                "date_expiration": date_expiration.isoformat(),
                "statut": "active",
                "fedapay_transaction_id": fedapay_transaction_id
            }
            
            return jsonify({
                "success": True,
                "message": "Paiement traité avec succès",
                "code": code
            })
        
        return jsonify({
            "success": True,
            "message": f"Webhook reçu - Status: {status}"
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# =========================
# VALIDATION DE CODE
# =========================

@app.route('/code/valider', methods=['POST'])
def valider_code():
    """
    Valide un code d'activation
    
    POST Body:
    {
        "code": "ABCD-1234-EFGH",
        "device_id": "A1B2C3D4E5",
        "entreprise": "Boutique Marie"
    }
    """
    try:
        data = request.json
        code = data.get('code', '').strip().upper()
        device_id = data.get('device_id')
        entreprise = data.get('entreprise')
        
        if not code or not device_id or not entreprise:
            return jsonify({
                "valide": False,
                "error": "Données manquantes"
            }), 400
        
        # Vérifier si le code existe dans les licences
        if code in licences:
            licence = licences[code]
            
            # Vérifier le device_id
            if licence['device_id'] != device_id:
                return jsonify({
                    "valide": False,
                    "error": "Code non valide pour cet appareil"
                }), 400
            
            # Vérifier l'expiration
            exp_date = datetime.fromisoformat(licence['date_expiration'])
            if datetime.now() > exp_date:
                return jsonify({
                    "valide": False,
                    "error": "Licence expirée"
                }), 400
            
            return jsonify({
                "valide": True,
                "entreprise": licence['entreprise'],
                "expiration": licence['date_expiration']
            })
        
        # Sinon, valider avec l'algorithme
        if valider_code_activation(code, entreprise, device_id):
            if code not in licences:
                date_expiration = datetime.now() + timedelta(days=DUREE_LICENCE_JOURS)
                licences[code] = {
                    "entreprise": entreprise,
                    "device_id": device_id,
                    "date_activation": datetime.now().isoformat(),
                    "date_expiration": date_expiration.isoformat(),
                    "statut": "active"
                }
            
            return jsonify({
                "valide": True,
                "entreprise": entreprise,
                "expiration": licences[code]['date_expiration']
            })
        
        return jsonify({
            "valide": False,
            "error": "Code invalide"
        }), 400
    
    except Exception as e:
        return jsonify({
            "valide": False,
            "error": str(e)
        }), 500

# =========================
# STATISTIQUES
# =========================

@app.route('/stats')
def statistiques():
    """Statistiques pour le vendeur"""
    total_paiements = len([p for p in paiements.values() if p['statut'] == 'payé'])
    total_revenus = total_paiements * PRIX_LICENCE
    
    return jsonify({
        "total_paiements": total_paiements,
        "total_revenus": total_revenus,
        "licences_actives": len(licences),
        "paiements_en_attente": len([p for p in paiements.values() if p['statut'] == 'en_attente']),
        "prix_licence": PRIX_LICENCE,
        "mode": FEDAPAY_MODE
    })

# =========================
# PAGE DE TEST
# =========================

@app.route('/test-paiement')
def test_paiement():
    """Page de test pour créer une transaction"""
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Test Paiement FedaPay</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #4CAF50;
                text-align: center;
            }
            input {
                width: 100%;
                padding: 12px;
                margin: 10px 0;
                border: 2px solid #ddd;
                border-radius: 5px;
                font-size: 16px;
                box-sizing: border-box;
            }
            button {
                width: 100%;
                padding: 15px;
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 18px;
                cursor: pointer;
                margin-top: 10px;
            }
            button:hover {
                background: #45a049;
            }
            #result {
                margin-top: 20px;
                padding: 15px;
                border-radius: 5px;
                display: none;
            }
            .success {
                background: #d4edda;
                border: 1px solid #c3e6cb;
                color: #155724;
            }
            .error {
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                color: #721c24;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧪 Test Paiement FedaPay</h1>
            <p style="text-align: center; color: #666;">Mode: <strong>SANDBOX</strong></p>
            
            <input type="text" id="entreprise" placeholder="Nom entreprise" value="Test Boutique">
            <input type="text" id="device_id" placeholder="ID appareil" value="TEST12345">
            
            <button onclick="creerPaiement()">💳 PAYER 2500 FCFA</button>
            
            <div id="result"></div>
        </div>
        
        <script>
            async function creerPaiement() {
                const entreprise = document.getElementById('entreprise').value;
                const device_id = document.getElementById('device_id').value;
                const resultDiv = document.getElementById('result');
                
                try {
                    resultDiv.textContent = '⏳ Création...';
                    resultDiv.style.display = 'block';
                    
                    const response = await fetch('/paiement/initier', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ entreprise, device_id })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        resultDiv.className = 'success';
                        resultDiv.innerHTML = '✅ Transaction créée!<br><br><a href="' + data.checkout_url + '" target="_blank"><button>Ouvrir page de paiement</button></a>';
                    } else {
                        resultDiv.className = 'error';
                        resultDiv.textContent = '❌ ' + (data.error || 'Erreur');
                    }
                } catch (error) {
                    resultDiv.className = 'error';
                    resultDiv.textContent = '❌ Erreur: ' + error.message;
                }
            }
        </script>
    </body>
    </html>
    """
    return html

# =========================
# DÉMARRAGE
# =========================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
