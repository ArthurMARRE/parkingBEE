import os
import sys
import time
from datetime import datetime, timedelta

import requests

TOKEN = os.getenv('BEEMYFLEX_TOKEN')
USER_ID = 5553
DAYS_AHEAD = 2          # J+2 : à passer à 1 si l'ouverture concerne demain
TIMEOUT = 5             # sans ça, une requête qui pend bloque toute la fenêtre

HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def reserver_parking():
    if not TOKEN:
        print("❌ BEEMYFLEX_TOKEN absent.", flush=True)
        return 1

    target_day = datetime.utcnow() + timedelta(days=DAYS_AHEAD)
    target_date = target_day.strftime("%Y-%m-%dT00:00:00.000Z")
    print(f"🎯 Cible : {target_day.strftime('%d/%m/%Y')}", flush=True)

    # --- ÉTAPE 1 : RÉCUPÉRER LES PLACES (avant l'attente) ---
    # Fait maintenant plutôt qu'à 17h : ça teste le token en amont et
    # évite de perdre une seconde au moment de l'ouverture.
    try:
        res = requests.get('https://api.beemyflex.com/api/ResourceValues',
                           headers=HEADERS, timeout=TIMEOUT)
        if res.status_code in (401, 403):
            print("❌ TOKEN EXPIRÉ. Régénère le secret BEEMYFLEX_TOKEN.", flush=True)
            return 1
        resource_ids = [r['id'] for r in res.json() if r.get('id')]
        print(f"✔️  Places : {resource_ids}", flush=True)
    except Exception as e:
        resource_ids = [41, 40, 39, 38]
        print(f"⚠️  ResourceValues KO ({e}) → liste de secours.", flush=True)

    # --- ÉTAPE 2 : FAIRE LE GUET JUSQU'À 17:00:00 GMT ---
    print("Mise en attente jusqu'à 17:00:00 GMT...", flush=True)
    while datetime.utcnow().hour < 17:
        time.sleep(0.5)
    print("🚀 17:00:00 GMT ! Lancement de l'offensive.", flush=True)

    # --- ÉTAPE 3 : LE MODE SNIPER (30 SECONDES) ---
    start = time.time()
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

            if r.status_code in (200, 201, 202):
                print(f"✅ SUCCÈS ! Place {spot_id} réservée.", flush=True)
                return 0

            if "already has a reservation" in r.text:
                print("ℹ️ Tu as déjà une place.", flush=True)
                return 0

            if r.status_code in (401, 403):
                print("❌ Token expiré en pleine fenêtre. Arrêt.", flush=True)
                return 1

        print("... toujours rien, on recommence...", flush=True)
        time.sleep(0.5)

    print("❌ Fin du temps imparti. Pas de place trouvée.", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(reserver_parking())
