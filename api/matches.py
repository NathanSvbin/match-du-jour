# api/matches.py (VERSION FINALE AVEC GESTION DE DICTIONNAIRE VIDE)

import pandas as pd
import curl_cffi.requests as tls_requests
import json
from flask import Flask, jsonify, request
from typing import Any
import os 

# --- Logique d'Extraction (La classe FotMobDailyScraper) ---

FOTMOB_API = "https://www.fotmob.com/api"
# Utilise print pour les logs Serverless
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
            
            # --- DÉBUT DE LA LOGIQUE D'EXTRACTION ROBUSTE AVEC GESTION DU DICTIONNAIRE ---
            
            if isinstance(data, dict):
                # Si c'est un dict, nous devons trouver la clé contenant les matchs
                if 'leagues' in data:
                    data = data['leagues']
                elif 'matches' in data:
                    data = data['matches']
                else:
                    # 🎯 NOUVEAU: Si c'est un dict mais sans clés de match connues, on loggue et on échoue.
                    LOGGER(f"❌ Données JSON reçues pour {self.target_date_str} est un dict sans clé 'leagues' ni 'matches'.")
                    return pd.DataFrame() 
            
            if not isinstance(data, list):
                 # Si 'data' n'est pas devenu une liste, on renvoie un DataFrame vide.
                 return pd.DataFrame()
            
            all_matches = []
            
            for item in data:
                if isinstance(item, dict) and item.get('events'):
                    match_source = item['events']
                    
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
                # 🎯 NOUVEAU: Le scénario le plus probable est qu'il n'y ait pas de matchs pour cette date.
                LOGGER(f"❌ Aucune donnée de match extraite de la liste (probablement pas de calendrier pour {self.target_date_str}).")
                return pd.DataFrame()

            # Création du DataFrame et Nettoyage (inchangé)
            df = pd.DataFrame(all_matches)
            df['date'] = pd.to_datetime(df['date_time_utc'], utc=True)
            df.drop(columns=['date_time_utc'], inplace=True)
            
            if 'score' in df.columns and not df['score'].isnull().all():
                 df[['home_score', 'away_score']] = df['score'].astype(str).str.split(' - ', expand=True)
                 df.drop(columns=['score'], inplace=True)
            
            return df.sort_values(by='date')
        
        except Exception as e:
            # 🎯 NOUVEAU: Loggue l'erreur générale (connexion, JSONDecodeError) pour le debug sur Vercel
            LOGGER(f"❌ Erreur critique lors de la récupération des matchs pour {self.target_date_str}: {e}")
            return pd.DataFrame()


# --- Application Flask pour Vercel ---
# ... (Le reste du code de l'API Flask est inchangé)
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
            # Renvoyer le message de non-trouvé
            return jsonify({
                "message": f"Aucun match trouvé pour le {target_date}."
            }), 404
            
        data_json = df.to_dict(orient='records')
        
        # Renvoyer le JSON au client
        return jsonify(data_json), 200

    except Exception:
        # Erreur Serverless générique
        return jsonify({"error": "Erreur interne du serveur lors de l'extraction des données."}), 500
