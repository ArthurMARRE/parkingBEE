import requests
import os
from datetime import datetime, timedelta

def reserver_parking():
    # On récupère le token caché sur GitHub
    token = os.getenv('BEEMYFLEX_TOKEN')
    
    # On calcule la date de demain (car tu lances le script à minuit pour le jour même)
    # Si le système ouvre les résas pour dans 2 jours, change timedelta(days=1) par (days=2)
   target_date = datetime.now().strftime("%Y-%m-%dT00:00:00.000Z")

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    json_data = {
        'reservationInfo': 0,
        'resourceValueId': 40,
        'userId': 5553,
        'startTime': target_date,
        'endTime': target_date,
        'eventRecipients': None,
        'nbParticipants': 1,
    }

    print(f"Tentative de réservation pour la date : {target_date}...")
    
    response = requests.post(
        'https://api.beemyflex.com/api/Reservations/async', 
        headers=headers, 
        json=json_data
    )

    if response.status_code in [200, 201, 202]:
        print("✅ Succès ! Place réservée.")
    else:
        print(f"❌ Erreur {response.status_code}: {response.text}")

if __name__ == "__main__":
    reserver_parking()
