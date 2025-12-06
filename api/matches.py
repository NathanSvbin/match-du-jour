import pandas as pd
import curl_cffi.requests as tls_requests
import json
from datetime import datetime
from pathlib import Path

# --- SIMULATION DES IMPORTS DE LA LIBRAIRIE 'soccerdata' ---
# REMPLACEZ CES LIGNES PAR VOS IMPORTS RÉELS SI VOUS ÊTES DANS LE CONTEXTE DU PACKAGE
# Si vous testez ce script seul, vous devez avoir ces fonctions/classes définies ailleurs.
# class BaseRequestsReader: ... (À DEFINIR)
# def make_game_id: ... (À DEFINIR)
# ...
# Pour ce test simple, nous allons simplifier la structure de la classe.
# -------------------------------------------------------------

# Configuration de base (Similaire à votre _config.py)
# Configuration de base (Ajouter les paramètres nécessaires pour la requête 404)
FOTMOB_API = "https://www.fotmob.com/api"
LOGGER = print
# ... (classe FotMobDailyScraper)


class FotMobDailyScraper:
    """Version simplifiée pour tester la récupération des matchs quotidiens."""
    
    def __init__(self, target_date_str: str):
        self.target_date_str = target_date_str
        self.session = self._init_session()
        
    def _init_session(self) -> tls_requests.Session:
        """Initialise la session TLS et récupère les headers d'authentification."""
        session = tls_requests.Session()
        
        # Tentative de récupération des headers de contournement (critique pour éviter 401/403)
        try:
            r = tls_requests.get("http://46.101.91.154:6006/")
            r.raise_for_status()
            result = r.json()
            session.headers.update(result)
            LOGGER("✅ Headers de session récupérés via le serveur tiers.")
        except Exception as e:
            LOGGER(f"⚠️ AVERTISSEMENT: Impossible de connecter au serveur de headers: {e}")
            # Ajouter un User-Agent de secours si le serveur de headers échoue
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
        return session

    def fetch_daily_schedule(self) -> pd.DataFrame:
        """Récupère et formate les matchs pour la date ciblée."""
        
        # 🎯 CORRECTION : DÉFINIR LA VARIABLE URL ICI !
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
            if not isinstance(data, list):
                LOGGER(f"❌ Erreur de structure : La réponse JSON n'est pas une liste mais est de type {type(data)}.")
                
                # 🎯 NOUVELLE ÉTAPE : SAUVEGARDER LE JSON BRUT POUR INSPECTION
                raw_filename = f"fotmob_raw_{self.target_date_str}.json"
                try:
                    with open(raw_filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    LOGGER(f"💾 JSON brut sauvegardé dans {raw_filename} pour inspection de la clé principale.")
                except Exception as save_e:
                    LOGGER(f"⚠️ AVERTISSEMENT: Impossible de sauvegarder le JSON: {save_e}")
                    
                # ----------------------------------------------------
                
                # 🔄 TENTATIVE DE RÉCUPÉRATION DE LA CLÉ COMMUNE (par exemple, 'matches')
                # Remplacez 'matches' par 'leagues', 'events', ou autre si l'inspection le révèle.
                if isinstance(data, dict) and 'matches' in data:
                    data = data['matches']
                    LOGGER("✅ Tentative de récupération de la liste à partir de la clé 'matches'.")
                else:
                    return pd.DataFrame() # Échec si on ne trouve pas la clé
            
            # Si on arrive ici, data est censé être une liste.
            all_matches = []
            for item in data:
                # 🚨 CORRECTION ICI : S'ASSURER QUE L'ITEM EST UN DICT AVANT D'UTILISER .get()
                if isinstance(item, dict):
                    # Filtrer seulement les items qui sont des matchs (type 'Match')
                    if item.get("type") == "Match":
                        for match in item.get("events", []):
                            # ... (le reste du code d'extraction pour le type 'Match')
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
                    # Gérer l'autre structure courante de FotMob (liste de ligues sans le type "Match")
                    elif item.get('events'):
                        for match in item['events']:
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

        # ... (le reste de la fonction : df = pd.DataFrame(all_matches)...)


            if not all_matches:
                 # L'API Fotmob renvoie une structure différente pour le calendrier complet, donc on s'adapte
                for section in data:
                    if section.get('events'):
                        for match in section['events']:
                            all_matches.append({
                                "league": section.get("name"),
                                "country": section.get("country"),
                                "home_team": match.get("home", {}).get("name"),
                                "away_team": match.get("away", {}).get("name"),
                                "date_time_utc": match.get("time"),
                                "status": match.get("status", {}).get("reason", {}).get("short"),
                                "score": match.get("status", {}).get("scoreStr"),
                                "match_id": match.get("id"),
                            })


            if not all_matches:
                LOGGER("❌ Aucune donnée de match trouvée dans la réponse JSON.")
                return pd.DataFrame()


            df = pd.DataFrame(all_matches)
            
            # Nettoyage et formatage
            df['date'] = pd.to_datetime(df['date_time_utc'], utc=True)
            df.drop(columns=['date_time_utc'], inplace=True)
            df[['home_score', 'away_score']] = df['score'].str.split(' - ', expand=True)
            df.drop(columns=['score'], inplace=True)
            
            return df.sort_values(by='date').set_index(['league', 'date'])
        
        except tls_requests.exceptions.HTTPError as e:
            # Capturer spécifiquement le 401/403 si la méthode TLS a échoué
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
        
        # Exemple : Sauvegarder
        output_file = f"fotmob_matches_{DATE_TO_TEST}.csv"
        df_daily.to_csv(output_file)
        print(f"\nDonnées sauvegardées dans {output_file}")
    else:
        print("\n🔴 Échec de l'extraction de données. Aucune ligne retournée.")
