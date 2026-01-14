"""
API Backend RecusApp - GRATUIT
Hébergé sur Render.com
Intégration FedaPay automatique
"""

from flask import Flask, request, jsonify
import hashlib
import secrets
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Configuration
FEDAPAY_SECRET_KEY = os.environ.get('FEDAPAY_SECRET_KEY')
CLE_MASTER = "RECUSAPP_BENIN_2026_SECURE"
PRIX_LICENCE = 2500

# Base de données en mémoire (ou PostgreSQL gratuit)
# Pour production : utiliser PostgreSQL de Render
paiements = {}
licences = {}

# =========================
# GÉNÉRATION DE CODE
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

# =========================
# ENDPOINTS API
# =========================

@app.route('/')
def home():
    return jsonify({
        "app": "RecusApp API",
        "version": "1.0",
        "status": "running"
    })

@app.route('/health')
def health():
    """Vérification de santé du serveur"""
    return jsonify({"status": "ok"})

@app.route('/paiement/initier', methods=['POST'])
def initier_paiement():
    """
    Initie un paiement FedaPay
    
    Body:
    {
        "entreprise": "Boutique Marie",
        "device_id": "A1B2C3D4E5",
        "numero_telephone": "22990123456"
    }
    """
    try:
        data = request.json
        entreprise = data.get('entreprise')
        device_id = data.get('device_id')
        numero_telephone = data.get('numero_telephone', '')
        
        if not entreprise or not device_id:
            return jsonify({"error": "Données manquantes"}), 400
        
        # Générer un ID de transaction unique
        transaction_id = generer_transaction_id()
        
        # Sauvegarder la demande
        paiements[transaction_id] = {
            "entreprise": entreprise,
            "device_id": device_id,
            "numero_telephone": numero_telephone,
            "montant": PRIX_LICENCE,
            "statut": "en_attente",
            "date_creation": datetime.now().isoformat(),
            "code": None
        }
        
        # Créer le lien de paiement FedaPay
        # Note : Vous devrez configurer FedaPay avec votre clé API
        url_paiement = f"https://paiement-recusapp.onrender.com/payer/{transaction_id}"
        
        return jsonify({
            "success": True,
            "transaction_id": transaction_id,
            "url_paiement": url_paiement,
            "montant": PRIX_LICENCE
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/payer/<transaction_id>')
def page_paiement(transaction_id):
    """Page HTML de paiement avec FedaPay Widget"""
    
    if transaction_id not in paiements:
        return "Transaction introuvable", 404
    
    paiement = paiements[transaction_id]
    
    # Page HTML avec widget FedaPay
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Paiement RecusApp</title>
        <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 400px;
                width: 100%;
                text-align: center;
            }}
            h1 {{
                color: #4CAF50;
                margin-bottom: 10px;
            }}
            .montant {{
                font-size: 48px;
                color: #FF5722;
                font-weight: bold;
                margin: 20px 0;
            }}
            .info {{
                background: #f5f5f5;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: left;
            }}
            .btn-payer {{
                background: #4CAF50;
                color: white;
                border: none;
                padding: 15px 40px;
                font-size: 18px;
                border-radius: 10px;
                cursor: pointer;
                width: 100%;
                margin-top: 20px;
            }}
            .btn-payer:hover {{
                background: #45a049;
            }}
            #status {{
                margin-top: 20px;
                padding: 15px;
                border-radius: 10px;
                display: none;
            }}
            .success {{
                background: #4CAF50;
                color: white;
            }}
            .error {{
                background: #f44336;
                color: white;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎉 RecusApp</h1>
            <p>Licence professionnelle</p>
            
            <div class="montant">{PRIX_LICENCE} F</div>
            
            <div class="info">
                <strong>Entreprise:</strong> {paiement['entreprise']}<br>
                <strong>Durée:</strong> 1 an<br>
                <strong>Transaction:</strong> {transaction_id[:8]}...
            </div>
            
            <button class="btn-payer" onclick="payerMaintenant()">
                💳 PAYER MAINTENANT
            </button>
            
            <div id="status"></div>
        </div>
        
        <script>
            function payerMaintenant() {{
                FedaPay.init({{
                    public_key: 'pk_live_VOTRE_CLE_PUBLIQUE_FEDAPAY',
                    transaction: {{
                        amount: {PRIX_LICENCE},
                        description: 'Licence RecusApp - 1 an',
                    }},
                    customer: {{
                        firstname: '{paiement['entreprise']}',
                        lastname: 'Client',
                        email: 'client@recusapp.com',
                        phone_number: {{
                            number: '{paiement.get('numero_telephone', '')}',
                            country: 'bj'
                        }}
                    }},
                    onComplete: function(transaction) {{
                        // Paiement réussi
                        notifierPaiement(transaction.id, 'success');
                    }},
                    onError: function(error) {{
                        // Erreur
                        showStatus('Erreur: ' + error.message, 'error');
                    }}
                }});
                
                FedaPay.open();
            }}
            
            function notifierPaiement(fedapay_id, status) {{
                // Notifier le serveur que le paiement est réussi
                fetch('/webhook/fedapay', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        transaction_id: '{transaction_id}',
                        fedapay_id: fedapay_id,
                        status: status
                    }})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        showStatus('✅ Paiement réussi! Votre code: ' + data.code, 'success');
                        
                        // Rediriger après 3 secondes
                        setTimeout(() => {{
                            window.location.href = '/success/' + data.code;
                        }}, 3000);
                    }}
                }})
                .catch(error => {{
                    showStatus('Erreur de confirmation', 'error');
                }});
            }}
            
            function showStatus(message, type) {{
                const statusDiv = document.getElementById('status');
                statusDiv.textContent = message;
                statusDiv.className = type;
                statusDiv.style.display = 'block';
            }}
        </script>
    </body>
    </html>
    """
    
    return html

@app.route('/webhook/fedapay', methods=['POST'])
def webhook_fedapay():
    """
    Webhook appelé par FedaPay après paiement
    Génère automatiquement le code d'activation
    """
    try:
        data = request.json
        transaction_id = data.get('transaction_id')
        fedapay_id = data.get('fedapay_id')
        status = data.get('status')
        
        if transaction_id not in paiements:
            return jsonify({"error": "Transaction introuvable"}), 404
        
        paiement = paiements[transaction_id]
        
        if status == 'success':
            # Générer le code d'activation
            code = generer_code_activation(
                paiement['entreprise'],
                paiement['device_id']
            )
            
            # Mettre à jour le paiement
            paiement['statut'] = 'payé'
            paiement['code'] = code
            paiement['fedapay_id'] = fedapay_id
            paiement['date_paiement'] = datetime.now().isoformat()
            
            # Sauvegarder la licence
            date_expiration = datetime.now() + timedelta(days=365)
            licences[code] = {
                "entreprise": paiement['entreprise'],
                "device_id": paiement['device_id'],
                "date_activation": datetime.now().isoformat(),
                "date_expiration": date_expiration.isoformat(),
                "statut": "active"
            }
            
            return jsonify({
                "success": True,
                "code": code,
                "expiration": date_expiration.isoformat()
            })
        
        return jsonify({"success": False, "error": "Paiement échoué"}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/paiement/verifier/<transaction_id>')
def verifier_paiement(transaction_id):
    """Vérifie le statut d'un paiement"""
    
    if transaction_id not in paiements:
        return jsonify({"error": "Transaction introuvable"}), 404
    
    paiement = paiements[transaction_id]
    
    return jsonify({
        "transaction_id": transaction_id,
        "statut": paiement['statut'],
        "code": paiement.get('code'),
        "date_paiement": paiement.get('date_paiement')
    })

@app.route('/code/valider', methods=['POST'])
def valider_code():
    """
    Valide un code d'activation
    
    Body:
    {
        "code": "ABCD-1234-EFGH",
        "device_id": "A1B2C3D4E5"
    }
    """
    try:
        data = request.json
        code = data.get('code', '').strip().upper()
        device_id = data.get('device_id')
        
        if code not in licences:
            return jsonify({"valide": False, "error": "Code invalide"}), 400
        
        licence = licences[code]
        
        # Vérifier le device_id
        if licence['device_id'] != device_id:
            return jsonify({"valide": False, "error": "Code non valide pour cet appareil"}), 400
        
        # Vérifier l'expiration
        exp_date = datetime.fromisoformat(licence['date_expiration'])
        if datetime.now() > exp_date:
            return jsonify({"valide": False, "error": "Licence expirée"}), 400
        
        return jsonify({
            "valide": True,
            "entreprise": licence['entreprise'],
            "expiration": licence['date_expiration']
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/success/<code>')
def success_page(code):
    """Page de succès après paiement"""
    if code not in licences:
        return "Code introuvable", 404
    
    licence = licences[code]
    
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Paiement Réussi</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #4CAF50;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 400px;
                width: 100%;
                text-align: center;
            }}
            .success-icon {{
                font-size: 80px;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #4CAF50;
            }}
            .code {{
                background: #f5f5f5;
                padding: 20px;
                border-radius: 10px;
                font-size: 24px;
                font-weight: bold;
                letter-spacing: 2px;
                margin: 20px 0;
                font-family: 'Courier New', monospace;
            }}
            .info {{
                text-align: left;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>Paiement Réussi!</h1>
            
            <p>Votre licence RecusApp est activée</p>
            
            <div class="code">{code}</div>
            
            <div class="info">
                <strong>Entreprise:</strong> {licence['entreprise']}<br>
                <strong>Valable jusqu'au:</strong> {datetime.fromisoformat(licence['date_expiration']).strftime('%d/%m/%Y')}
            </div>
            
            <p style="color: #666; font-size: 14px;">
                Votre application est maintenant activée automatiquement.
                Vous pouvez la fermer et continuer à utiliser RecusApp!
            </p>
        </div>
    </body>
    </html>
    """
    
    return html

@app.route('/stats')
def statistiques():
    """Statistiques pour le vendeur"""
    total_paiements = len([p for p in paiements.values() if p['statut'] == 'payé'])
    total_revenus = total_paiements * PRIX_LICENCE
    
    return jsonify({
        "total_paiements": total_paiements,
        "total_revenus": total_revenus,
        "licences_actives": len(licences),
        "paiements_en_attente": len([p for p in paiements.values() if p['statut'] == 'en_attente'])
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
