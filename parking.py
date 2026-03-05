import requests

headers = {
    'sec-ch-ua-platform': '"Windows"',
    'Authorization': 'Bearer eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYW1lIjoiYXJ0aHVyLm1hcnJlIiwiZW1haWwiOiJhcnRodXIubWFycmVAb3JhbmdlLmNvbSIsInBpY3R1cmUiOiJodHRwczovL3MuZ3JhdmF0YXIuY29tL2F2YXRhci84NzI3YTJjMzM2NjBkY2ViYmJkZDdjZmUzNjE3MzFjNj9zPTQ4MCZyPXBnJmQ9aHR0cHMlM0ElMkYlMkZjZG4uYXV0aDAuY29tJTJGYXZhdGFycyUyRmFyLnBuZyIsInN1YiI6ImF1dGgwfDY1NGUwYjk2MDJiODI0ZGUyNjI1MmRmOCIsInNwZWNpZmljVGltZW91dCI6IjE2ZCIsImxhc3RSZWZyZXNoIjoxNzcyNzAyOTMyLCJqdGkiOiJiOTJjYTgyMC00MTEyLTQ2MjUtODc3Yi1mYWI0OWFkNjYwN2UiLCJleHAiOjE3NzQwODUzMzJ9.3VLYZfmTwmMyLGDZC8JF63Cz60hjDdZiXrXfFVLQp6_fna1Z_7O6hOrdB_akt06Rvlytu5fXRT0NJXHnf_W2nw',
    'Referer': 'https://app.beemyflex.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    'sec-ch-ua-mobile': '?0',
}

response = requests.get('https://api.beemyflex.com/api/Reservations/LastReservation', headers=headers)
