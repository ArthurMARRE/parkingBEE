#!/usr/bin/env python3
"""
Reservation automatique d'une place de parking BeeMyFlex.

Garde-fous contre les doublons :
  - un seul run "principal" tire a l'ouverture (DELAI_SECOURS = 0) ;
    les autres sont des runs de secours qui ne se reveillent qu'apres
    l'ouverture et se retirent si une place est deja detenue ;
  - verification systematique des reservations existantes avant de tirer,
    au demarrage ET juste avant la rafale ;
  - controle d'unicite apres coup : si plusieurs places sont detenues,
    le log le signale en clair.

Filtre de jours : on ne reserve que pour les jours listes dans
JOURS_CIBLES (numerotation Python : lundi = 0 ... dimanche = 6).

Variables d'environnement :
  BEEMYFLEX_TOKEN  (obligatoire) JWT
  SPOT_IDS         ordre de preference, ids techniques separes par des virgules
  JOURS_CIBLES     jours de semaine autorises pour la DATE VISEE (defaut 0,1,3)
  DAYS_AHEAD       decalage de la date visee                     (defaut 2)
  TARGET_HOUR      heure UTC d'ouverture                         (defaut 17)
  TARGET_MINUTE    minute UTC d'ouverture                        (defaut 0)
  DELAI_SECOURS    secondes apres l'ouverture avant de tirer     (defaut 0)
  BURST_PRIO       duree de la rafale sur la prioritaire, en s   (defaut 2.5)
  SNIPE_SECONDS    duree totale du tir sur les replis, en s      (defaut 30)
  VEILLE_SECONDS   surveillance de la prioritaire apres repli    (defaut 60)
  SYNC_HORLOGE     1 pour caler sur l'horloge serveur            (defaut 1)
  USER_ID          identifiant BeeMyFlex                         (defaut 5553)

Code de sortie : 0 si une place est obtenue, deja detenue, ou si la date
visee n'est pas un jour autorise. 1 sinon.
"""

import os
import sys
import time
import threading
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

API = 'https://api.beemyflex.com/api'
TOKEN = os.getenv('BEEMYFLEX_TOKEN')
USER_ID = int(os.getenv('USER_ID', '5553'))
RESOURCE_ID = 13                                    # Parking CFC
DAYS_AHEAD = int(os.getenv('DAYS_AHEAD', '2'))
TARGET_HOUR = int(os.getenv('TARGET_HOUR', '17'))   # 17 UTC = 18h Casablanca
TARGET_MINUTE = int(os.getenv('TARGET_MINUTE', '0'))
DELAI_SECOURS = float(os.getenv('DELAI_SECOURS', '0'))
BURST_PRIO = float(os.getenv('BURST_PRIO', '2.5'))
SNIPE_SECONDS = float(os.getenv('SNIPE_SECONDS', '30'))
VEILLE_SECONDS = float(os.getenv('VEILLE_SECONDS', '60'))
SYNC_HORLOGE = os.getenv('SYNC_HORLOGE', '1') == '1'
TIMEOUT = 5

# Numerotation Python : lundi = 0, mardi = 1, mercredi = 2, jeudi = 3...
JOURS_CIBLES = {int(x) for x in os.getenv('JOURS_CIBLES', '0,1,3').split(',')}
NOM_JOUR = ['lundi', 'mardi', 'mercredi', 'jeudi',
            'vendredi', 'samedi', 'dimanche']

# resourceValueId (id technique) -> nom affiche. L'id n'est PAS le numero
# de place : "Place 175" a l'id 150.
PLACES = {
    150: "Place 175", 77: "Place 174", 41: "Place 261", 40: "Place 260",
    39: "Place 259", 66: "Place 262", 38: "Place 235 (large)",
    37: "Place 234", 36: "Place 233 (large)", 35: "Place 232",
    34: "Place 231", 33: "Place 230",
}

SPOT_IDS = [int(x) for x in os.getenv(
    'SPOT_IDS', '150,38,36,77,41,40,39,66,37,35,34,33').split(',')]
PRIO = SPOT_IDS[0]
REPLIS = SPOT_IDS[1:]


def maintenant():
    return datetime.now(timezone.utc)


def log(msg):
    """Horodatage a la milliseconde : indispensable pour savoir si on a
    tire avant ou apres les autres."""
    print(f"{maintenant().strftime('%H:%M:%S.%f')[:-3]}Z  {msg}", flush=True)


def nom(spot_id):
    return PLACES.get(spot_id, f"id {spot_id}")


def noms(ids):
    return [nom(i) for i in ids]


def nouvelle_session():
    s = requests.Session()
    s.headers.update({
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    # Pas de retry automatique : on gere nous-memes, et un retry urllib3
    # ajouterait un backoff invisible au pire moment.
    s.mount('https://', requests.adapters.HTTPAdapter(
        pool_connections=4, pool_maxsize=4, max_retries=0))
    return s


def lire_places(session, jour):
    """Renvoie (libres, occupees, a_moi) en ids techniques.
    None si le token est mort, triplet vide si l'appel echoue."""
    try:
        r = session.get(f"{API}/ResourceValues/GetTimeValues",
                        params={'date': jour, 'resourceId': RESOURCE_ID},
                        timeout=TIMEOUT)
        if r.status_code in (401, 403):
            return None
        data = r.json().get('multipleResult') or []
    except Exception as e:
        log(f"GetTimeValues KO ({e}).")
        return ([], [], [])

    libres, occupees, a_moi = [], [], []
    for place in data:
        du_jour = [b for b in (place.get('bookings') or [])
                   if (b.get('startTime') or '').startswith(jour)]
        if not du_jour:
            libres.append(place['id'])
            continue
        occupees.append(place['id'])
        for b in du_jour:
            # le champ porteur de l'utilisateur varie selon les endpoints
            if any(b.get(c) == USER_ID for c in ('userId', 'UserId', 'user_id')):
                a_moi.append(place['id'])
                break
    return (libres, occupees, a_moi)


def mes_places(session, jour):
    """Places deja detenues pour la date visee.
    Deux sources, la seconde en repli. Renvoie une liste (eventuellement
    vide), ou None si le token est mort."""
    # 1) endpoint dedie aux reservations de l'utilisateur
    try:
        r = session.get(f"{API}/Reservations",
                        params={'q': f'UserId = {USER_ID}'}, timeout=TIMEOUT)
        if r.status_code in (401, 403):
            return None
        if r.status_code == 200:
            data = r.json().get('multipleResult')
            if data is not None:
                trouve = [x.get('resourceValueId') for x in data
                          if (x.get('startTime') or '').startswith(jour)
                          and x.get('resourceValueId') in PLACES]
                return sorted(set(trouve))
    except Exception:
        pass

    # 2) repli : les bookings exposes par GetTimeValues
    etat = lire_places(session, jour)
    if etat is None:
        return None
    return sorted(set(etat[2]))


def offset_serveur(session, jour):
    """Ecart horloge runner -> horloge serveur, en secondes.
    Le header Date est arrondi a la seconde : on interroge toutes les
    100 ms jusqu'a le voir basculer, ce qui situe la frontiere de seconde
    a environ 100 ms pres."""
    precedent = None
    for _ in range(12):
        t_local = time.time()
        try:
            r = session.get(f"{API}/ResourceValues/GetTimeValues",
                            params={'date': jour, 'resourceId': RESOURCE_ID},
                            timeout=TIMEOUT)
            entete = r.headers.get('Date')
            if not entete:
                return 0.0
            t_serveur = parsedate_to_datetime(entete).timestamp()
        except Exception:
            return 0.0
        if precedent is not None and t_serveur != precedent:
            return t_serveur - t_local
        precedent = t_serveur
        time.sleep(0.1)
    return 0.0


def prechauffer(session, jour):
    """Ouvre la connexion TLS a l'avance : DNS, TCP et handshake sont
    faits, le premier POST part sans ce cout."""
    try:
        session.get(f"{API}/ResourceValues/GetTimeValues",
                    params={'date': jour, 'resourceId': RESOURCE_ID},
                    timeout=TIMEOUT)
        log("Connexion prechauffee.")
    except Exception as e:
        log(f"Prechauffage KO ({e}), sans consequence.")


def attendre(cible_ts, offset, session, jour):
    """Attente precise : sommeil grossier de loin, puis actif sur les
    250 dernieres millisecondes."""
    prechauffe = False
    while True:
        reste = cible_ts - (time.time() + offset)
        if reste <= 0:
            return
        if reste > 60:
            time.sleep(min(reste - 60, 30))
        elif reste > 6:
            time.sleep(0.5)
        elif not prechauffe:
            prechauffer(session, jour)
            prechauffe = True
        elif reste > 0.25:
            time.sleep(0.02)
        else:
            while cible_ts - (time.time() + offset) > 0:
                pass          # attente active, 250 ms au pire
            return


def photo_ouverture(jour):
    """Releve l'etat reel des places juste apres l'ouverture, dans un fil
    separe avec sa propre session pour ne jamais retarder le tir."""
    etat = lire_places(nouvelle_session(), jour)
    if not etat:
        return
    libres, occupees, _ = etat
    log(f"PHOTO T+0 : libres = {noms(libres)}")
    log(f"PHOTO T+0 : occupees = {noms(occupees)}")
    log(f"PHOTO T+0 : {nom(PRIO)} "
        f"{'LIBRE' if PRIO in libres else 'DEJA PRISE ou non ouverte'}")


def tirer(session, spot, horaire, jour, compteur):
    """Une tentative. Renvoie 'ok', 'deja', 'stop' ou 'retry'."""
    payload = {
        'reservationInfo': 0,
        'resourceValueId': spot,
        'userId': USER_ID,
        'startTime': horaire,
        'endTime': horaire,
        'eventRecipients': None,
        'nbParticipants': 1,
    }
    depart = time.time()
    try:
        r = session.post(f"{API}/Reservations/async", json=payload,
                         timeout=TIMEOUT)
    except requests.RequestException as e:
        log(f"Reseau : {e}")
        return 'retry'
    ms = (time.time() - depart) * 1000
    compteur[0] += 1

    try:
        corps = r.json()
    except ValueError:
        corps = {}
    statut = corps.get('status', r.status_code)
    message = corps.get('message') or ''

    log(f"[{compteur[0]}] {nom(spot)} -> HTTP {r.status_code} / "
        f"status {statut} : {message or 'ok'}  ({ms:.0f} ms)")

    if r.status_code in (401, 403) or statut in (401, 403):
        log("TOKEN EXPIRE. Regenere le secret BEEMYFLEX_TOKEN.")
        return 'stop'
    if 'already has a reservation' in (r.text or ''):
        log("Le serveur signale une reservation existante pour cette date.")
        return 'deja'
    if statut in (200, 201) and corps.get('singleResult'):
        log(f"RESERVE : {nom(spot)} pour {jour} "
            f"(reservation #{corps['singleResult'].get('id')}).")
        return 'ok'
    return 'retry'


def controle_unicite(session, jour):
    """Dernier garde-fou : si plusieurs places sont detenues pour la meme
    date, on le hurle dans les logs pour que ce soit corrige a la main."""
    detenues = mes_places(session, jour)
    if detenues is None:
        return
    if len(detenues) > 1:
        log("*** DOUBLON : tu detiens " + str(len(detenues)) + " places pour "
            f"{jour} -> {noms(detenues)}. Annule les surnumeraires dans "
            "l'appli. ***")
    elif len(detenues) == 1:
        log(f"Controle final : une seule place detenue, {nom(detenues[0])}.")


def reserver():
    if not TOKEN:
        log("BEEMYFLEX_TOKEN absent.")
        return 1

    session = nouvelle_session()
    cible = maintenant() + timedelta(days=DAYS_AHEAD)
    jour = cible.strftime('%Y-%m-%d')
    horaire = f"{jour}T00:00:00"          # format confirme : ni Z ni ms
    jsem = cible.weekday()

    role = "SECOURS" if DELAI_SECOURS > 0 else "PRINCIPAL"
    log(f"Role : {role}"
        + (f" (tir a T+{DELAI_SECOURS:.0f} s)" if DELAI_SECOURS > 0 else ""))
    log(f"Cible : {NOM_JOUR[jsem]} {cible.strftime('%d/%m/%Y')} (J+{DAYS_AHEAD})")

    # --- Filtre jours autorises -------------------------------------
    if jsem not in JOURS_CIBLES:
        autorises = ', '.join(NOM_JOUR[j] for j in sorted(JOURS_CIBLES))
        log(f"{NOM_JOUR[jsem].capitalize()} n'est pas un jour autorise "
            f"({autorises}). Aucune reservation. Arret.")
        return 0

    log(f"Prioritaire : {nom(PRIO)} | replis : {noms(REPLIS)}")

    # --- Garde-fou doublon, au demarrage ----------------------------
    detenues = mes_places(session, jour)
    if detenues is None:
        log("TOKEN EXPIRE. Regenere le secret BEEMYFLEX_TOKEN.")
        return 1
    if detenues:
        log(f"Tu detiens deja {noms(detenues)} pour cette date. "
            "Aucun tir. Arret.")
        return 0

    etat = lire_places(session, jour)
    libres = etat[0] if etat else []
    log(f"Avant ouverture : {len(libres)} libre(s) "
        f"{noms(libres) if libres else '(normal)'}")

    # --- Instant de tir ---------------------------------------------
    ouverture = maintenant().replace(hour=TARGET_HOUR, minute=TARGET_MINUTE,
                                     second=0, microsecond=0)
    cible_ts = ouverture.timestamp() + DELAI_SECOURS

    offset = 0.0
    if SYNC_HORLOGE and cible_ts - time.time() > 20:
        # la mesure prend jusqu'a 1,2 s : on ne la lance pas si l'ouverture
        # est imminente, ce serait la payer au pire moment
        mesure = offset_serveur(session, jour)
        if abs(mesure) > 3:
            log(f"Ecart d'horloge mesure aberrant ({mesure:+.3f} s), ignore.")
        else:
            offset = mesure
            log(f"Ecart d'horloge runner/serveur : {offset:+.3f} s.")

    reste = cible_ts - (time.time() + offset)
    if reste < -1:
        log(f"DEMARRAGE TARDIF : {-reste:.1f} s apres l'instant de tir. "
            "Le cron a ete retarde par GitHub, on tire quand meme.")
    else:
        log(f"Attente de {reste:.1f} s.")
        attendre(cible_ts, offset, session, jour)

    # --- Second garde-fou, juste avant la rafale --------------------
    # Un run de secours doit imperativement verifier que le principal n'a
    # pas deja fait le travail. Le principal, lui, tire sans ce controle :
    # il est seul a T+0 et 200 ms de round-trip lui couteraient la place.
    if DELAI_SECOURS > 0:
        detenues = mes_places(session, jour)
        if detenues is None:
            log("TOKEN EXPIRE. Arret.")
            return 1
        if detenues:
            log(f"Le run principal a deja obtenu {noms(detenues)}. "
                "Rien a faire.")
            return 0
        log("Aucune place detenue : le run principal a echoue ou n'a pas "
            "tourne. Prise de relais.")

    log("TIR.")
    threading.Thread(target=photo_ouverture, args=(jour,), daemon=True).start()

    compteur = [0]

    # --- Phase A : rafale sur la seule prioritaire -------------------
    fin_prio = time.time() + BURST_PRIO
    while time.time() < fin_prio:
        issue = tirer(session, PRIO, horaire, jour, compteur)
        if issue in ('ok', 'deja'):
            controle_unicite(session, jour)
            return 0
        if issue == 'stop':
            return 1
        time.sleep(0.08)

    log(f"{nom(PRIO)} inaccessible apres {compteur[0]} tentatives en "
        f"{BURST_PRIO} s. Passage aux replis.")

    # --- Phase B : replis -------------------------------------------
    obtenue = None
    fin = time.time() + SNIPE_SECONDS
    while time.time() < fin and obtenue is None:
        for spot in REPLIS:
            issue = tirer(session, spot, horaire, jour, compteur)
            if issue == 'ok':
                obtenue = spot
                break
            if issue == 'deja':
                controle_unicite(session, jour)
                return 0
            if issue == 'stop':
                return 1
        else:
            time.sleep(0.3)

    if obtenue is None:
        log(f"Fin du temps imparti ({compteur[0]} tentatives). Rien obtenu.")
        return 1

    controle_unicite(session, jour)

    # --- Phase C : veille sur la prioritaire ------------------------
    log(f"Repli securise : {nom(obtenue)}. Surveillance de {nom(PRIO)} "
        f"pendant {VEILLE_SECONDS:.0f} s.")
    fin_veille = time.time() + VEILLE_SECONDS
    while time.time() < fin_veille:
        etat = lire_places(session, jour)
        if etat and PRIO in etat[0]:
            log(f"*** {nom(PRIO)} s'est liberee. Annule {nom(obtenue)} dans "
                "l'appli et prends-la a la main. ***")
            break
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(reserver())
