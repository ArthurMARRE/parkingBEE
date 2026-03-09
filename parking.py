import requests
import os
from datetime import datetime, timedelta

def reserver_parking():
    token = os.getenv('BEEMYFLEX_TOKEN')
    userId = 5553 # Ton identifiant utilisateur
    
    # Cible : Demain
    target_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    # ÉTAPE 1 : Récupérer toutes les places de parking configurées
    print("Recherche des places disponibles...")
    try:
        # On interroge l'API pour avoir la liste des ressources
        res_list = requests.get('https://api.beemyflex.com/api/ResourceValues', headers=headers)
        resources = res_list.json()
        
        # On extrait tous les IDs des ressources (places)
        # On filtre pour ne garder que ce qui ressemble à du parking si nécessaire
        resource_ids = [r['id'] for r in resources if r.get('id')]
        print(f"{len(resource_ids)} places potentielles trouvées.")
    except Exception as e:
        print(f"Erreur lors de la récupération de la liste : {e}")
        # En cas d'échec de la liste, on tente quand même tes places habituelles
        resource_ids = [41, 40]

    # ÉTAPE 2 : Tenter la réservation sur chaque place jusqu'au succès
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

        print(f"Tentative sur la place ID {spot_id} pour le {target_date}...")
        
        response = requests.post(
            'https://api.beemyflex.com/api/Reservations/async', 
            headers=headers, 
            json=json_data
        )

        if response.status_code in [200, 201, 202]:
            print(f"✅ SUCCÈS ! La place {spot_id} est à toi.")
            return # On arrête tout, mission accomplie !
        else:
            # Si c'est déjà pris, l'API répond souvent 400 ou 409
            print(f"   Echec pour la place {spot_id} (Code {response.status_code})")

    print("❌ Aucune place n'a pu être réservée parmi la liste.")

if __name__ == "__main__":
    reserver_parking()
