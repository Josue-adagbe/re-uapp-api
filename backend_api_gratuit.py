from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib
from datetime import datetime, timedelta
import os
import secrets

app = Flask(__name__)
CORS(app)  # Activer CORS pour toutes les routes

# Configuration
CLE_MASTER = "RECUSAPP_BENIN_2026_SECURE"
PRIX_LICENCE = 2500
FEDAPAY_SECRET_KEY = os.environ.get('FEDAPAY_SECRET_KEY', '')

# Base de données en mémoire (sera remplacé par une vraie DB plus tard)
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
    
    # Vérifier les codes des 30 derniers jours
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
# ROUTES DE BASE
# =========================

@app.route('/')
def home():
    return jsonify({
        "app": "RecusApp API",
        "version": "2.0",
        "status": "running",
        "endpoints": {
            "/health": "Health check",
            "/paiement/initier": "Initier un paiement",
            "/paiement/verifier/<transaction_id>": "Vérifier un paiement",
            "/code/valider": "Valider un code d'activation",
            "/webhook/fedapay": "Webhook FedaPay",
            "/stats": "Statistiques"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/test')
def test():
    return jsonify({
        "message": "API fonctionne!",
        "timestamp": datetime.now().isoformat(),
        "fedapay_configured": bool(FEDAPAY_SECRET_KEY)
    })

# =========================
# ROUTES DE PAIEMENT
# =========================

@app.route('/paiement/initier', methods=['POST'])
def initier_paiement():
    """
    Initie un paiement
    
    POST Body:
    {
        "entreprise": "Boutique Marie",
        "device_id": "A1B2C3D4E5"
    }
    
    Retourne:
    {
        "success": true,
        "transaction_id": "xxx",
        "url_paiement": "https://...",
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
        
        # Générer un ID de transaction unique
        transaction_id = generer_transaction_id()
        
        # Sauvegarder la demande de paiement
        paiements[transaction_id] = {
            "entreprise": entreprise,
            "device_id": device_id,
            "montant": PRIX_LICENCE,
            "statut": "en_attente",
            "date_creation": datetime.now().isoformat(),
            "code": None
        }
        
        # URL de la page de paiement
        url_paiement = f"https://re-uapp-api.onrender.com/payer/{transaction_id}"
        
        return jsonify({
            "success": True,
            "transaction_id": transaction_id,
            "url_paiement": url_paiement,
            "montant": PRIX_LICENCE,
            "message": "Ouvrez cette URL pour payer"
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/payer/<transaction_id>')
def page_paiement(transaction_id):
    """Page HTML de paiement avec instructions"""
    
    if transaction_id not in paiements:
        return """
        <html>
        <head><title>Transaction introuvable</title></head>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1>❌ Transaction introuvable</h1>
            <p>Cette transaction n'existe pas ou a expiré.</p>
        </body>
        </html>
        """, 404
    
    paiement = paiements[transaction_id]
    
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Paiement RecusApp</title>
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
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                max-width: 450px;
                width: 100%;
            }}
            h1 {{
                color: #4CAF50;
                margin-bottom: 10px;
                font-size: 24px;
            }}
            .montant {{
                font-size: 36px;
                color: #FF5722;
                font-weight: bold;
                margin: 20px 0;
            }}
            .info {{
                background: #f5f5f5;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                text-align: left;
                font-size: 14px;
            }}
            .numero {{
                background: #FFF3E0;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
                border: 2px solid #FF9800;
            }}
            .numero h3 {{
                margin: 0 0 10px 0;
                color: #FF9800;
                font-size: 16px;
            }}
            .numero p {{
                margin: 5px 0;
                font-size: 14px;
            }}
            .numero strong {{
                font-size: 18px;
                color: #000;
            }}
            button {{
                background: #4CAF50;
                color: white;
                border: none;
                padding: 15px 30px;
                font-size: 16px;
                border-radius: 8px;
                cursor: pointer;
                width: 100%;
                margin-top: 15px;
                font-weight: bold;
            }}
            button:hover {{
                background: #45a049;
            }}
            .steps {{
                background: #E8F5E9;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                text-align: left;
            }}
            .steps h3 {{
                margin: 0 0 10px 0;
                color: #4CAF50;
            }}
            .steps ol {{
                margin: 0;
                padding-left: 20px;
            }}
            .steps li {{
                margin: 8px 0;
                font-size: 14px;
            }}
            input {{
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
                margin: 10px 0;
                box-sizing: border-box;
            }}
            .activer-btn {{
                background: #2196F3;
            }}
            .activer-btn:hover {{
                background: #1976D2;
            }}
            #status {{
                margin-top: 15px;
                padding: 15px;
                border-radius: 8px;
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
            <h1>💳 Paiement RecusApp</h1>
            
            <div class="montant">{PRIX_LICENCE} FCFA</div>
            
            <div class="info">
                <strong>Entreprise:</strong> {paiement['entreprise']}<br>
                <strong>Durée:</strong> 1 an<br>
                <strong>Transaction:</strong> {transaction_id[:12]}...
            </div>
            
            <div class="steps">
                <h3>📱 Instructions de paiement</h3>
                <ol>
                    <li>Envoyez <strong>{PRIX_LICENCE} FCFA</strong> à l'un des numéros ci-dessous</li>
                    <li>Notez votre <strong>référence de transaction</strong></li>
                    <li>Contactez-nous sur WhatsApp avec la référence</li>
                    <li>Recevez votre code d'activation</li>
                </ol>
            </div>
            
            <div class="numero">
                <h3>📱 MTN MOBILE MONEY</h3>
                <p><strong>2290167004080</strong></p>
                <p>Nom: RecusApp Benin</p>
            </div>
            
            <div class="numero">
                <h3>📱 CELTIIS CASH</h3>
                <p><strong>2290143948122</strong></p>
                <p>Nom: RecusApp Benin</p>
            </div>
            
            <button onclick="contacterWhatsApp()">
                💬 CONTACTER SUR WHATSAPP
            </button>
            
            <hr style="margin: 25px 0; border: none; border-top: 1px solid #ddd;">
            
            <h3 style="margin: 15px 0; font-size: 16px;">Vous avez déjà payé ?</h3>
            <p style="font-size: 14px; color: #666;">Entrez le code d'activation reçu :</p>
            
            <input type="text" id="code" placeholder="XXXX-XXXX-XXXX" maxlength="14">
            
            <button class="activer-btn" onclick="activerLicence()">
                ✅ ACTIVER LA LICENCE
            </button>
            
            <div id="status"></div>
        </div>
        
        <script>
            function contacterWhatsApp() {{
                const msg = `Bonjour,\\n\\nJ'ai effectué le paiement pour RecusApp.\\n\\nEntreprise: {paiement['entreprise']}\\nID Appareil: {paiement['device_id']}\\nMontant: {PRIX_LICENCE} FCFA\\nRéférence transaction: [VOTRE REFERENCE]\\n\\nMerci de m'envoyer le code d'activation.`;
                
                const url = `https://wa.me/2290167004080?text=${{encodeURIComponent(msg)}}`;
                window.open(url, '_blank');
            }}
            
            function activerLicence() {{
                const code = document.getElementById('code').value.trim();
                const statusDiv = document.getElementById('status');
                
                if (!code) {{
                    statusDiv.textContent = 'Veuillez entrer le code d\\'activation';
                    statusDiv.className = 'error';
                    statusDiv.style.display = 'block';
                    return;
                }}
                
                // Simuler la validation du code
                fetch('/code/simuler-activation', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        transaction_id: '{transaction_id}',
                        code: code
                    }})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        statusDiv.textContent = '✅ Code validé ! Retournez dans l\\'application et entrez ce code.';
                        statusDiv.className = 'success';
                    }} else {{
                        statusDiv.textContent = '❌ ' + (data.error || 'Code invalide');
                        statusDiv.className = 'error';
                    }}
                    statusDiv.style.display = 'block';
                }})
                .catch(error => {{
                    statusDiv.textContent = '❌ Erreur de connexion';
                    statusDiv.className = 'error';
                    statusDiv.style.display = 'block';
                }});
            }}
        </script>
    </body>
    </html>
    """
    
    return html

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

@app.route('/paiement/confirmer', methods=['POST'])
def confirmer_paiement():
    """
    Confirme un paiement manuellement (pour le vendeur)
    
    POST Body:
    {
        "transaction_id": "xxx",
        "reference_paiement": "REF123"
    }
    """
    try:
        data = request.json
        transaction_id = data.get('transaction_id')
        reference = data.get('reference_paiement', 'MANUEL')
        
        if transaction_id not in paiements:
            return jsonify({
                "success": False,
                "error": "Transaction introuvable"
            }), 404
        
        paiement = paiements[transaction_id]
        
        # Générer le code d'activation
        code = generer_code_activation(
            paiement['entreprise'],
            paiement['device_id']
        )
        
        # Mettre à jour le paiement
        paiement['statut'] = 'payé'
        paiement['code'] = code
        paiement['reference_paiement'] = reference
        paiement['date_paiement'] = datetime.now().isoformat()
        
        # Sauvegarder la licence
        date_expiration = datetime.now() + timedelta(days=365)
        licences[code] = {
            "entreprise": paiement['entreprise'],
            "device_id": paiement['device_id'],
            "date_activation": datetime.now().isoformat(),
            "date_expiration": date_expiration.isoformat(),
            "statut": "active",
            "transaction_id": transaction_id
        }
        
        return jsonify({
            "success": True,
            "code": code,
            "expiration": date_expiration.isoformat(),
            "message": "Paiement confirmé et code généré"
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
            # Créer la licence si elle n'existe pas
            if code not in licences:
                date_expiration = datetime.now() + timedelta(days=365)
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

@app.route('/code/simuler-activation', methods=['POST'])
def simuler_activation():
    """Simule l'activation d'un code (pour la page de paiement)"""
    try:
        data = request.json
        code = data.get('code', '').strip().upper()
        transaction_id = data.get('transaction_id')
        
        if not code:
            return jsonify({
                "success": False,
                "error": "Code manquant"
            }), 400
        
        # Vérifier si c'est un code valide
        if code in licences or len(code.replace('-', '')) == 12:
            return jsonify({
                "success": True,
                "message": "Code valide"
            })
        
        return jsonify({
            "success": False,
            "error": "Code invalide"
        }), 400
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# =========================
# WEBHOOK FEDAPAY
# =========================

@app.route('/webhook/fedapay', methods=['POST'])
def webhook_fedapay():
    """
    Webhook appelé par FedaPay après paiement réussi
    """
    try:
        data = request.json
        
        # À implémenter plus tard avec la vérification de signature FedaPay
        # Pour l'instant, on accepte tous les webhooks
        
        transaction_id = data.get('transaction_id')
        fedapay_id = data.get('fedapay_id')
        status = data.get('status')
        
        if transaction_id in paiements and status == 'approved':
            paiement = paiements[transaction_id]
            
            # Générer le code
            code = generer_code_activation(
                paiement['entreprise'],
                paiement['device_id']
            )
            
            paiement['statut'] = 'payé'
            paiement['code'] = code
            paiement['fedapay_id'] = fedapay_id
            paiement['date_paiement'] = datetime.now().isoformat()
            
            # Créer la licence
            date_expiration = datetime.now() + timedelta(days=365)
            licences[code] = {
                "entreprise": paiement['entreprise'],
                "device_id": paiement['device_id'],
                "date_activation": datetime.now().isoformat(),
                "date_expiration": date_expiration.isoformat(),
                "statut": "active",
                "fedapay_id": fedapay_id
            }
            
            return jsonify({
                "success": True,
                "message": "Paiement traité"
            })
        
        return jsonify({
            "success": False,
            "message": "Transaction non trouvée ou statut invalide"
        }), 400
    
    except Exception as e:
        return jsonify({
            "success": False,
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
        "prix_licence": PRIX_LICENCE
    })

# =========================
# DÉMARRAGE
# =========================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
           
