import requests
import os
import time
from datetime import datetime, timedelta

def reserver_parking():
    token = os.getenv('BEEMYFLEX_TOKEN')
    userId = 5553
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    # --- ÉTAPE 1 : FAIRE LE GUET JUSQU'À 17:00:00 GMT ---
    print("Mise en attente du script jusqu'à 17:00:00 GMT...")
    while True:
        now_gmt = datetime.utcnow()
        # Si on est à 17h ou plus, on sort de la boucle d'attente
        if now_gmt.hour >= 17:
            break
        time.sleep(1) # On vérifie chaque seconde

    print("🚀 17:00:00 GMT atteint ! Lancement de l'offensive.")

    # Cible : Demain
    target_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00.000Z")

    # --- ÉTAPE 2 : RÉCUPÉRER LES PLACES ---
    try:
        res_list = requests.get('https://api.beemyflex.com/api/ResourceValues', headers=headers)
        resource_ids = [r['id'] for r in res_list.json() if r.get('id')]
    except:
        resource_ids = [41, 40, 39, 38] # Liste de secours

    # --- ÉTAPE 3 : LE MODE SNIPER (RETENTER PENDANT 30 SECONDES) ---
    start_bombardement = time.time()
    while time.time() - start_bombardement < 30: # On essaie pendant 30 secondes max
        for spot_id in resource_ids:
            json_data = {
                'reservationInfo': 0,
                'resourceValueId': spot_id,
                'userId': userId,
                'startTime': target_date,
                'endTime': target_date,
                'eventRecipients': None,
                'nbParticipants': 1,
            }

            response = requests.post(
                'https://api.beemyflex.com/api/Reservations/async', 
                headers=headers, 
                json=json_data
            )

            if response.status_code in [200, 201, 202]:
                print(f"✅ SUCCÈS ! Place {spot_id} réservée pour demain.")
                return
            
            # Si le serveur dit que c'est déjà réservé par toi
            if "already has a reservation" in response.text:
                print("ℹ️ Tu as déjà une place pour demain.")
                return

        print("... toujours rien, on recommence le tour des places...")
        time.sleep(0.5) # Petite pause pour ne pas se faire bannir par le serveur

    print("❌ Fin du temps imparti. Pas de place trouvée.")

if __name__ == "__main__":
    reserver_parking()
