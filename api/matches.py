# api/matches.py (Version Optimisée Anti-Blocage)

import curl_cffi.requests as tls_requests
import json
from flask import Flask, jsonify, request
import pandas as pd
# NOUVEAU: Pour ajouter un délai aléatoire (Anti-Rate Limiting)
import time
import random 

FOTMOB_API = "https://www.fotmob.com/api"
LOGGER = print

class FotMobDailyScraper:
    def __init__(self, target_date_str: str):
        self.target_date_str = target_date_str
        self.session: tls_requests.Session = self._init_session()
        
    def _init_session(self) -> tls_requests.Session:
        session = tls_requests.Session()
        
        # ⚠️ MODIFICATION : Suppression du bloc "try/except" avec l'IP externe
        # pour éviter les dépendances instables. Utilisation directe du User-Agent
        # qui fonctionne en local.
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Ajout d'un Accept header pour être plus complet
            'Accept': 'application/json, text/plain, */*'
        })
        return session

    def fetch_daily_schedule(self) -> dict:
        """Récupère la réponse JSON brute de l'API FotMob."""
        
        url = (
            f"{FOTMOB_API}/data/matches?date={self.target_date_str}"
            f"&timezone=Europe%2FParis&ccode3=FRA"
        )
        
        try:
            # Ajout d'un timeout plus long pour éviter les déconnexions sur Vercel
            response = self.session.get(url, timeout=15)
            response.raise_for_status() 
            
            return response.json()
            
        except Exception as e:
            LOGGER(f"❌ Erreur critique lors de la récupération brute pour {self.target_date_str}: {e}")
            return {}


# --- Application Flask pour Vercel ---

app = Flask(__name__)

@app.route('/api/matches', methods=['GET'])
def get_daily_matches():
    target_date = request.args.get('date')
    
    # 🎯 ANTI-BLOCAGE : Ajouter un délai d'attente aléatoire avant la requête
    delay = random.uniform(1.0, 3.0) # Délai entre 1 et 3 secondes
    time.sleep(delay)
    
    if not target_date or not target_date.isdigit() or len(target_date) != 8:
        return jsonify({
            "error": "Paramètre 'date' manquant ou invalide. Format requis : YYYYMMDD (ex: 20251209)"
        }), 400

    try:
        scraper = FotMobDailyScraper(target_date)
        json_data = scraper.fetch_daily_schedule()
        
        if not json_data:
            return jsonify({
                "message": f"Échec de la récupération du JSON brut pour le {target_date}. (L'API FotMob a peut-être bloqué le serveur Vercel ou la date est trop lointaine)."
            }), 404
            
        return jsonify(json_data), 200

    except Exception:
        # On loggue l'erreur pour le débogage de Vercel (si possible)
        LOGGER(f"Erreur fatale de l'application Flask.")
        return jsonify({"error": "Erreur interne du serveur lors de l'extraction des données."}), 500
