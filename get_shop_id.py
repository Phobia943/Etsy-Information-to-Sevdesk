#!/usr/bin/env python3
"""
Schnelles Script um deine Etsy Shop ID abzurufen
"""
import requests

# Trage hier deine Credentials ein:
API_KEY = "DEIN_API_KEY_HIER"  # Keystring aus Etsy Developer Portal
SHOP_NAME = "DEIN_SHOP_NAME"   # z.B. "MeinShop"

url = f"https://openapi.etsy.com/v3/application/shops"
headers = {
    "x-api-key": API_KEY
}
params = {
    "shop_name": SHOP_NAME
}

print(f"Rufe Shop ID für '{SHOP_NAME}' ab...")
response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    data = response.json()
    if data.get("results"):
        shop = data["results"][0]
        print(f"\n✅ Shop gefunden!")
        print(f"Shop ID: {shop['shop_id']}")
        print(f"Shop Name: {shop['shop_name']}")
    else:
        print(f"\n❌ Shop '{SHOP_NAME}' nicht gefunden!")
        print("Prüfe die Schreibweise des Shop-Namens.")
else:
    print(f"\n❌ Fehler: {response.status_code}")
    print(response.text)
