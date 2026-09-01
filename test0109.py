import os
import sys
import time
from datetime import datetime, timedelta

import requests

API = 'https://api.beemyflex.com/api'
TOKEN = os.getenv('BEEMYFLEX_TOKEN')
USER_ID = 5553
RESOURCE_ID = 13                                  # Parking CFC
DAYS_AHEAD = int(os.getenv('DAYS_AHEAD', 2))
TARGET_HOUR = int(os.getenv('TARGET_HOUR', 17))   # 17 UTC = 18h Casablanca
TIMEOUT = 5

# resourceValueId (id technique) -> nom affiche. L'id n'est PAS le numero
# de place : "Place 175" a l'id 150.
PLACES = {
    150: "Place 175", 77: "Place 174", 41: "Place 261", 40: "Place 260",
    39: "Place 259", 66: "Place 262", 38: "Place 235 (large)",
    37: "Place 234", 36: "Place 233 (large)", 35: "Place 232",
    34: "Place 231", 33: "Place 230",
}

# Ordre de preference : la 175 d'abord, puis les larges, puis le reste.
SPOT_IDS = [int(x) for x in os.getenv(
    'SPOT_IDS', '150,38,36,77,41,40,39,66,37,35,34,33').split(',')]


def nom(spot_id):
    return PLACES.get(spot_id, f"id {spot_id}")


def etat_des_places(session, jour):
    """Lit GetTimeValues et renvoie les ids libres pour le jour vise."""
    try:
        r = session.get(f"{API}/ResourceValues/GetTimeValues",
                        params={'date': jour, 'resourceId': RESOURCE_ID},
                        timeout=TIMEOUT)
        if r.status_code in (401, 403):
            return None
        data = r.json().get('multipleResult') or []
    except Exception as e:
        print(f"GetTimeValues KO ({e}) - on tente quand meme.", flush=True)
        return []

    libres = []
    for place in data:
        pris = any(b.get('startTime', '').startswith(jour)
                   for b in (place.get('bookings') or []))
        if not pris:
            libres.append(place['id'])
    return libres


def reserver():
    if not TOKEN:
        print("BEEMYFLEX_TOKEN absent.", flush=True)
        return 1

    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })

    cible = datetime.utcnow() + timedelta(days=DAYS_AHEAD)
    jour = cible.strftime("%Y-%m-%d")
    # Format confirme par l'API : pas de Z, pas de millisecondes.
    horaire = f"{jour}T00:00:00"
    print(f"Cible : {cible.strftime('%d/%m/%Y')} (J+{DAYS_AHEAD})", flush=True)
    print(f"Priorites : {[nom(s) for s in SPOT_IDS[:3]]}...", flush=True)

    libres = etat_des_places(session, jour)
    if libres is None:
        print("TOKEN EXPIRE. Regenere le secret BEEMYFLEX_TOKEN.", flush=True)
        return 1
    if libres:
        print(f"Libres avant ouverture : {[nom(s) for s in libres]}", flush=True)
    else:
        print("Aucune place libre pour l'instant (normal avant l'ouverture).",
              flush=True)

    print(f"Attente jusqu'a {TARGET_HOUR:02d}:00:00 UTC...", flush=True)
    while datetime.utcnow().hour < TARGET_HOUR:
        time.sleep(0.5)
    print("Ouverture. Lancement.", flush=True)

    debut = time.time()
    essais = 0
    while time.time() - debut < 30:
        for spot in SPOT_IDS:
            payload = {
                'reservationInfo': 0,
                'resourceValueId': spot,
                'userId': USER_ID,
                'startTime': horaire,
                'endTime': horaire,
                'eventRecipients': None,
                'nbParticipants': 1,
            }
            try:
                r = session.post(f"{API}/Reservations/async", json=payload,
                                 timeout=TIMEOUT)
            except requests.RequestException as e:
                print(f"Reseau : {e}", flush=True)
                continue

            essais += 1

            # L'API renvoie TOUJOURS HTTP 200 : le vrai code est dans le
            # champ "status" du corps JSON. Un 200 HTTP avec status 500
            # est un echec.
            try:
                corps = r.json()
                statut = corps.get('status')
                message = corps.get('message')
            except ValueError:
                corps, statut, message = {}, None, r.text[:150]

            print(f"[{essais}] {nom(spot)} -> HTTP {r.status_code} / "
                  f"status {statut} : {message}", flush=True)

            if r.status_code in (401, 403) or statut in (401, 403):
                print("Token expire. Arret.", flush=True)
                return 1

            if message and "already has a reservation" in message:
                print("Tu as deja une place pour cette date.", flush=True)
                return 0

            # Succes uniquement si status 200/201 ET un objet retourne.
            if statut in (200, 201) and corps.get('singleResult'):
                print(f"RESERVE : {nom(spot)} pour "
                      f"{cible.strftime('%d/%m/%Y')} "
                      f"(reservation #{corps['singleResult'].get('id')}).",
                      flush=True)
                return 0

        time.sleep(0.4)

    print(f"Fin du temps imparti ({essais} tentatives). Rien obtenu.", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(reserver())
