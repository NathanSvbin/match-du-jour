# api/matches.py (Corrigé pour renvoyer le JSON brut)

import curl_cffi.requests as tls_requests
import json
from flask import Flask, jsonify, request
import pandas as pd # Conserver si nécessaire pour d'autres parties du package

FOTMOB_API = "https://www.fotmob.com/api"
LOGGER = print 

class FotMobDailyScraper:
    # ... (Le reste de la classe __init__ et _init_session est inchangé) ...
    def __init__(self, target_date_str: str):
        self.target_date_str = target_date_str
        self.session: tls_requests.Session = self._init_session()
        
    def _init_session(self) -> tls_requests.Session:
        session = tls_requests.Session()
        try:
            r = tls_requests.get("http://46.101.91.154:6006/", timeout=5) 
            r.raise_for_status() 
            session.headers.update(r.json())
        except Exception:
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
        return session

    # 🎯 FONCTION MODIFIÉE pour renvoyer le dict brut
    def fetch_daily_schedule(self) -> dict:
        """Récupère la réponse JSON brute de l'API FotMob."""
        
        url = (
            f"{FOTMOB_API}/data/matches?date={self.target_date_str}"
            f"&timezone=Europe%2FParis&ccode3=FRA"
        )
        
        try:
            response = self.session.get(url)
            response.raise_for_status() 
            
            # Retourne le dictionnaire JSON directement sans traitement
            return response.json()
            
        except Exception as e:
            # En cas d'échec HTTP ou JSON Decode, on loggue et on retourne un dict vide
            LOGGER(f"❌ Erreur critique lors de la récupération brute pour {self.target_date_str}: {e}")
            return {}


# --- Application Flask pour Vercel ---

app = Flask(__name__)

@app.route('/api/matches', methods=['GET'])
def get_daily_matches():
    target_date = request.args.get('date')
    
    if not target_date or not target_date.isdigit() or len(target_date) != 8:
        return jsonify({
            "error": "Paramètre 'date' manquant ou invalide. Format requis : YYYYMMDD (ex: 20251209)"
        }), 400

    try:
        scraper = FotMobDailyScraper(target_date)
        # Appel de la fonction qui renvoie le dict JSON brut
        json_data = scraper.fetch_daily_schedule()
        
        if not json_data:
            # Échec de la récupération (HTTP ou JSON Decode)
            return jsonify({
                "message": f"Échec de la récupération du JSON brut pour le {target_date}. (L'API FotMob a peut-être bloqué le serveur Vercel ou la date est trop lointaine)."
            }), 404
            
        # 🎯 Renvoyer le dictionnaire JSON brut directement
        return jsonify(json_data), 200

    except Exception:
        return jsonify({"error": "Erreur interne du serveur lors de l'extraction des données."}), 500
