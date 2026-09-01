import os
import sys
import time
from datetime import datetime, timedelta

import requests

TOKEN = os.getenv('BEEMYFLEX_TOKEN')
USER_ID = 5553
DAYS_AHEAD = int(os.getenv('DAYS_AHEAD', 2))
TARGET_HOUR = int(os.getenv('TARGET_HOUR', 17))   # 17 UTC = 18h Casablanca
TIMEOUT = 5

HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def reserver_parking():
    if not TOKEN:
        print("BEEMYFLEX_TOKEN absent.", flush=True)
        return 1

    target_day = datetime.utcnow() + timedelta(days=DAYS_AHEAD)
    target_date = target_day.strftime("%Y-%m-%dT00:00:00.000Z")
    print(f"Cible : {target_day.strftime('%d/%m/%Y')} (J+{DAYS_AHEAD})", flush=True)

    # --- ETAPE 1 : RECUPERER LES PLACES (avant l'attente) ---
    # Fait maintenant plutot qu'a 17h : teste le token en amont et evite
    # de perdre du temps au moment de l'ouverture.
    try:
        res = requests.get('https://api.beemyflex.com/api/ResourceValues',
                           headers=HEADERS, timeout=TIMEOUT)
        if res.status_code in (401, 403):
            print("TOKEN EXPIRE OU INVALIDE. Regenere le secret BEEMYFLEX_TOKEN.",
                  flush=True)
            return 1
        resource_ids = [r['id'] for r in res.json() if r.get('id')]
        print(f"Token OK. Places : {resource_ids}", flush=True)
    except Exception as e:
        resource_ids = [41, 40, 39, 38]
        print(f"ResourceValues KO ({e}) -> liste de secours : {resource_ids}",
              flush=True)

    # --- ETAPE 2 : FAIRE LE GUET ---
    print(f"Mise en attente jusqu'a {TARGET_HOUR:02d}:00:00 UTC...", flush=True)
    while datetime.utcnow().hour < TARGET_HOUR:
        time.sleep(0.5)
    print(f"{TARGET_HOUR:02d}:00 UTC atteint ! Lancement de l'offensive.", flush=True)

    # --- ETAPE 3 : MODE SNIPER (30 SECONDES) ---
    start = time.time()
    tentatives = 0
    while time.time() - start < 30:
        for spot_id in resource_ids:
            json_data = {
                'reservationInfo': 0,
                'resourceValueId': spot_id,
                'userId': USER_ID,
                'startTime': target_date,
                'endTime': target_date,
                'eventRecipients': None,
                'nbParticipants': 1,
            }
            try:
                r = requests.post('https://api.beemyflex.com/api/Reservations/async',
                                  headers=HEADERS, json=json_data, timeout=TIMEOUT)
            except requests.RequestException:
                continue

            tentatives += 1

            if r.status_code in (200, 201, 202):
                print(f"SUCCES ! Place {spot_id} reservee pour "
                      f"{target_day.strftime('%d/%m/%Y')} (HTTP {r.status_code}).",
                      flush=True)
                return 0

            if "already has a reservation" in r.text:
                print("Tu as deja une place pour cette date.", flush=True)
                return 0

            if r.status_code in (401, 403):
                print("401/403 en pleine fenetre : token expire. Arret.", flush=True)
                return 1

            # Premiere reponse d'echec : on montre ce que dit le serveur,
            # sinon on ne sait pas pourquoi ca rate.
            if tentatives == 1:
                print(f"Reponse serveur (place {spot_id}) : "
                      f"HTTP {r.status_code} - {r.text[:300]}", flush=True)

        print("... toujours rien, on recommence le tour des places...", flush=True)
        time.sleep(0.5)

    print(f"Fin du temps imparti ({tentatives} tentatives). Pas de place trouvee.",
          flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(reserver_parking())
