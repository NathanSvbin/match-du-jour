# api/matches.py (VERSION CORRIGÉE AVEC LA LOGIQUE ROBUSTE)

import pandas as pd
import curl_cffi.requests as tls_requests
import json
from flask import Flask, jsonify, request
from typing import Any
import os 

# --- Logique d'Extraction (La classe FotMobDailyScraper) ---

FOTMOB_API = "https://www.fotmob.com/api"
LOGGER = print

class FotMobDailyScraper:
    
    def __init__(self, target_date_str: str):
        self.target_date_str = target_date_str
        self.session: tls_requests.Session = self._init_session()
        
    def _init_session(self) -> tls_requests.Session:
        session = tls_requests.Session()
        # Logique de récupération des headers (inchangée)
        try:
            r = tls_requests.get("http://46.101.91.154:6006/", timeout=5) 
            r.raise_for_status() 
            session.headers.update(r.json())
        except Exception:
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
        return session

    def fetch_daily_schedule(self) -> pd.DataFrame:
        """Récupère et formate les matchs pour la date ciblée, avec une logique robuste."""
        
        url = (
            f"{FOTMOB_API}/data/matches?date={self.target_date_str}"
            f"&timezone=Europe%2FParis&ccode3=FRA"
        )
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            # --- DÉBUT DE LA LOGIQUE D'EXTRACTION ROBUSTE (Celle de votre script local) ---
            
            # Gestion de l'enveloppe JSON si la réponse n'est pas une liste directe
            if isinstance(data, dict):
                if 'leagues' in data:
                    data = data['leagues']
                elif 'matches' in data: # Gère le cas de la clé 'matches'
                    data = data['matches']
                
            if not isinstance(data, list):
                 # Si après avoir cherché les clés 'leagues'/'matches' on n'a toujours pas une liste, on échoue.
                 return pd.DataFrame()
            
            all_matches = []
            
            for item in data:
                if isinstance(item, dict):
                    # 1. Traitement des éléments qui sont des Matchs directs (si l'API change)
                    if item.get("type") == "Match" and item.get("events"):
                        match_source = item.get("events", [])
                    # 2. Traitement des éléments qui sont des Ligues/Sections (le cas le plus fréquent)
                    elif item.get('events'):
                        match_source = item['events']
                    else:
                        continue # Passe à l'élément suivant si pas d'événements
                        
                    for match in match_source:
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
                        
            # --- FIN DE LA LOGIQUE D'EXTRACTION ROBUSTE ---

            if not all_matches:
                return pd.DataFrame()

            # Création du DataFrame et Nettoyage (inchangé)
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
            
        data_json = df.to_dict(orient='records')
        
        # Le code d'écriture de fichier est conservé mais ignoré sur Vercel
        output_filename = f"fotmob_matches_{target_date}.json"
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(data_json, f, indent=4)
        except Exception:
            pass
        
        # Renvoyer le JSON au client
        return jsonify(data_json), 200

    except Exception:
        return jsonify({"error": "Erreur interne du serveur lors de l'extraction des données."}), 500
