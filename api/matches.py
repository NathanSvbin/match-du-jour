import pandas as pd
import curl_cffi.requests as tls_requests
import json
from datetime import datetime
from pathlib import Path
from typing import Any # Pour les annotations de type si nécessaire

# Configuration de base 
FOTMOB_API = "https://www.fotmob.com/api"
LOGGER = print

class FotMobDailyScraper:
    """Version simplifiée pour tester la récupération des matchs quotidiens."""
    
    def __init__(self, target_date_str: str):
        self.target_date_str = target_date_str
        # L'annotation de type pour Session nécessite une méthode d'import spécifique
        self.session: tls_requests.Session = self._init_session()
        
    def _init_session(self) -> tls_requests.Session:
        """Initialise la session TLS et récupère les headers d'authentification."""
        session = tls_requests.Session()
        
        # 🎯 CORRECTION : Gestion sécurisée des erreurs de connexion/timeout sur le serveur de headers
        try:
            r = tls_requests.get("http://46.101.91.154:6006/", timeout=5) # Timeout ajouté
            r.raise_for_status() # Lève une erreur si le statut est 4xx ou 5xx
            result = r.json()
            session.headers.update(result)
            LOGGER("✅ Headers de session récupérés via le serveur tiers.")
        except Exception as e:
            # Cette exception attrape les erreurs ConnectionError, Timeout, HTTPError, et JSONDecodeError
            LOGGER(f"⚠️ AVERTISSEMENT: Impossible de connecter au serveur de headers ou erreur HTTP/JSON: {e}")
            # Ajouter un User-Agent de secours si le serveur de headers échoue
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
        
        LOGGER(f"\n📡 Tentative de requête TLS vers : {url}")
        
        try:
            response = self.session.get(url)
            response.raise_for_status()

            data = response.json()
            
            # --- Vérification et Normalisation des données ---
            # 🎯 CORRECTION : Tenter de récupérer la liste des ligues depuis la clé 'leagues'
            if isinstance(data, dict) and 'leagues' in data:
                data = data['leagues']
                LOGGER("✅ Liste de matchs récupérée à partir de la clé 'leagues'.")
            elif not isinstance(data, list):
                # Si ce n'est ni un dictionnaire avec 'leagues' ni une liste, c'est une erreur de structure
                LOGGER(f"❌ Erreur de structure : La réponse JSON n'est pas une liste ou un dictionnaire avec 'leagues'. Type reçu: {type(data)}.")
                return pd.DataFrame()
            
            all_matches = []
            
            # Iteration sur les ligues (item)
            for item in data:
                if isinstance(item, dict):
                    # Les deux structures courantes sont gérées ici: soit avec 'type': 'Match', soit directement avec 'events'
                    if item.get("type") == "Match" or item.get('events'):
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

            # ❌ ANCIEN BLOC REDONDANT ET ERRONÉ RETIRÉ :
            # if not all_matches:
            #     for section in data: ...

            if not all_matches:
                LOGGER("❌ Aucune donnée de match trouvée après l'analyse de la réponse JSON.")
                return pd.DataFrame()

            # --- Création du DataFrame et Nettoyage ---
            df = pd.DataFrame(all_matches)
            
            df['date'] = pd.to_datetime(df['date_time_utc'], utc=True)
            df.drop(columns=['date_time_utc'], inplace=True)
            
            # Sépare le score 'X - Y' en deux colonnes
            if 'score' in df.columns and not df['score'].isnull().all():
                 df[['home_score', 'away_score']] = df['score'].astype(str).str.split(' - ', expand=True)
                 df.drop(columns=['score'], inplace=True)
            
            return df.sort_values(by='date').set_index(['league', 'date'])
        
        except tls_requests.exceptions.HTTPError as e:
            LOGGER(f"❌ ÉCHEC TLS. Statut: {e.response.status_code}. Le blocage est trop fort. ({e})")
            return pd.DataFrame()
        except Exception as e:
            LOGGER(f"❌ Erreur lors du traitement des données : {e}")
            return pd.DataFrame()


if __name__ == "__main__":
    # La date que vous voulez tester
    DATE_TO_TEST = "20251206"  
    
    # Exécuter le scraper
    scraper = FotMobDailyScraper(DATE_TO_TEST)
    df_daily = scraper.fetch_daily_schedule()

    if not df_daily.empty:
        print(f"\n✅ Succès! {len(df_daily)} matchs récupérés pour le {DATE_TO_TEST}.")
        print("\n--- Calendrier Quotidien ---")
        print(df_daily)
        
        output_file = f"fotmob_matches_{DATE_TO_TEST}.csv"
        df_daily.to_csv(output_file)
        print(f"\nDonnées sauvegardées dans {output_file}")
    else:
        print("\n🔴 Échec de l'extraction de données. Aucune ligne retournée.")
