# api/matches.py

import pandas as pd
import curl_cffi.requests as tls_requests
import json
from flask import Flask, jsonify, request
from typing import Any

# --- Logique d'Extraction (La classe FotMobDailyScraper) ---

FOTMOB_API = "https://www.fotmob.com/api"
# Nous utilisons un simple print pour les logs dans l'environnement Serverless
LOGGER = print

class FotMobDailyScraper:
    """Contient la logique d'extraction de données de Fotmob."""
    
    def __init__(self, target_date_str: str):
        self.target_date_str = target_date_str
        self.session: tls_requests.Session = self._init_session()
        
    def _init_session(self) -> tls_requests.Session:
        """Initialise la session TLS et récupère les headers d'authentification de manière sécurisée."""
        session = tls_requests.Session()
        
        try:
            # Tentative de récupération sécurisée (avec timeout)
            r = tls_requests.get("http://46.101.91.154:6006/", timeout=5) 
            r.raise_for_status() # Lève une erreur si le statut est 4xx ou 5xx
            result = r.json()
            session.headers.update(result)
            # LOGGER("✅ Headers de session récupérés via le serveur tiers.") # Commenté pour Vercel
        except Exception:
            # Ajout d'un User-Agent générique en cas d'échec
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
        return session

    def fetch_daily_schedule(self) -> pd.DataFrame:
        """Récupère et formate les matchs pour la date ciblée."""
        
        url = (
            f"{FOTMOB_API}/data/matches?date={self.target_date_str}"
            f"&timezone=Europe%2FParis&ccode3=FRA"
        )
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Gestion de la structure JSON (dict avec 'leagues' ou list)
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

            # Création du DataFrame et Nettoyage
            df = pd.DataFrame(all_matches)
            df['date'] = pd.to_datetime(df['date_time_utc'], utc=True)
            df.drop(columns=['date_time_utc'], inplace=True)
            
            if 'score' in df.columns and not df['score'].isnull().all():
                 df[['home_score', 'away_score']] = df['score'].astype(str).str.split(' - ', expand=True)
                 df.drop(columns=['score'], inplace=True)
            
            # Retourne le DataFrame (non indexé pour faciliter la conversion JSON)
            return df.sort_values(by='date')
        
        except Exception:
            # Capture tous les échecs (HTTP, JSON, connexion) et retourne un DataFrame vide.
            return pd.DataFrame()


# --- Application Flask pour Vercel ---

# 1. Vercel cherche la variable 'app'.
app = Flask(__name__)

# 2. 🎯 CORRECTION: La route DOIT être la racine (/) pour le fichier d'API
@app.route('/', methods=['GET'])
def get_daily_matches():
    """Endpoint de l'API pour récupérer les matchs d'une date spécifique.
    Accès via: /api/matches?date=YYYYMMDD
    """
    
    # 1. Récupérer le paramètre 'date' de l'URL
    target_date = request.args.get('date')
    
    if not target_date or not target_date.isdigit() or len(target_date) != 8:
        return jsonify({
            "error": "Paramètre 'date' manquant ou invalide. Format requis : YYYYMMDD (ex: 20251209)"
        }), 400

    try:
        # 2. Exécuter le scraper
        scraper = FotMobDailyScraper(target_date)
        df = scraper.fetch_daily_schedule()
        
        if df.empty:
            return jsonify({
                "message": f"Aucun match trouvé pour le {target_date}."
            }), 404
        
        # 3. Convertir le DataFrame en JSON et le renvoyer
        return jsonify(df.to_dict(orient='records')), 200

    except Exception:
        # Erreur Serverless générique
        return jsonify({"error": "Erreur interne du serveur lors de l'extraction des données."}), 500
