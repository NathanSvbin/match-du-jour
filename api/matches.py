# api/matches.py

import pandas as pd
import curl_cffi.requests as tls_requests
import json
from flask import Flask, jsonify, request
from typing import Any
import os # Ajout de os pour manipuler les fichiers si nécessaire

# --- Logique d'Extraction (La classe FotMobDailyScraper) ---
# (Reste inchangé)
# ...

FOTMOB_API = "https://www.fotmob.com/api"
LOGGER = print

class FotMobDailyScraper:
    # ... (Le contenu de la classe FotMobDailyScraper reste inchangé) ...
    def __init__(self, target_date_str: str):
        self.target_date_str = target_date_str
        self.session: tls_requests.Session = self._init_session()
        
    def _init_session(self) -> tls_requests.Session:
        session = tls_requests.Session()
        
        try:
            r = tls_requests.get("http://46.101.91.154:6006/", timeout=5) 
            r.raise_for_status() 
            result = r.json()
            session.headers.update(result)
        except Exception:
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
        return session

    def fetch_daily_schedule(self) -> pd.DataFrame:
        url = (
            f"{FOTMOB_API}/data/matches?date={self.target_date_str}"
            f"&timezone=Europe%2FParis&ccode3=FRA"
        )
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, dict) and 'leagues' in data:
                data = data['leagues']
            elif not isinstance(data, list):
                return pd.DataFrame()
            
            all_matches = []
            
            for item in data:
                if isinstance(item, dict) and item.get('events'):
                    for match in item.get('events', []):
                        all_matches.append({
                            "league": item.get("name"),
                            "country": item.get("country"),
                            "home_team": match.get("home", {}).get("name"),
                            "away_team": match.get("away", {}).get("name"),
                            "date_time_utc": match.get("time"),
                            "status": match.get("status", {}).get("reason", {}).get("short"),
                            "score": match.get("status", {}).get("scoreStr"),
                            "match_id": match.get("id"),
                        })

            if not all_matches:
                return pd.DataFrame()

            df = pd.DataFrame(all_matches)
            df['date'] = pd.to_datetime(df['date_time_utc'], utc=True)
            df.drop(columns=['date_time_utc'], inplace=True)
            
            if 'score' in df.columns and not df['score'].isnull().all():
                 df[['home_score', 'away_score']] = df['score'].astype(str).str.split(' - ', expand=True)
                 df.drop(columns=['score'], inplace=True)
            
            return df.sort_values(by='date')
        
        except Exception:
            return pd.DataFrame()


# --- Application Flask pour Vercel ---

app = Flask(__name__)

@app.route('/api/matches', methods=['GET'])
def get_daily_matches():
    """Endpoint de l'API pour récupérer les matchs d'une date spécifique.
    Accès via: /api/matches?date=YYYYMMDD
    """
    
    target_date = request.args.get('date')
    
    if not target_date or not target_date.isdigit() or len(target_date) != 8:
        return jsonify({
            "error": "Paramètre 'date' manquant ou invalide. Format requis : YYYYMMDD (ex: 20251209)"
        }), 400

    try:
        scraper = FotMobDailyScraper(target_date)
        df = scraper.fetch_daily_schedule()
        
        if df.empty:
            return jsonify({
                "message": f"Aucun match trouvé pour le {target_date}."
            }), 404
            
        # 1. Préparer les données au format JSON
        data_json = df.to_dict(orient='records')
        
        # 2. 🎯 ÉCRITURE DU FICHIER JSON SUR DISQUE (LOCALEMENT SEULEMENT)
        output_filename = f"fotmob_matches_{target_date}.json"
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(data_json, f, indent=4)
            # LOGGER(f"💾 JSON sauvegardé temporairement dans {output_filename}.")
        except Exception:
            # Cette erreur sera ignorée car l'API doit continuer à fonctionner
            pass
        
        # 3. Renvoyer le fichier JSON via la réponse HTTP (C'EST LE VRAI OBJECTIF)
        return jsonify(data_json), 200

    except Exception:
        # Erreur Serverless générique
        return jsonify({"error": "Erreur interne du serveur lors de l'extraction des données."}), 500
