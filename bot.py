import discord
from discord.ext import commands
import tls_client
import time
import json
import os
import asyncio

# Datei, die URLs für verschiedene Channels speichert
CHANNELS_FILE = "channel_urls.json"

# Laden oder Erstellen der Datei für die Channel-URLs
try:
    with open(CHANNELS_FILE, 'r') as f:
        channels_data = json.load(f)
except FileNotFoundError:
    channels_data = {}

# ==========================================
# VintedSniper Klasse
# ==========================================
class VintedSniper:
    def __init__(self, target_url, channel_id):
        self.api_url = self.convert_url(target_url)
        self.channel_id = channel_id  # Channel-ID für den aktuellen Channel
        self.session = tls_client.Session(client_identifier="chrome_112")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        self.seen_items = []

    def convert_url(self, url):
        if "api/v2/catalog/items" in url:
            return url
        base_api = "https://www.vinted.de/api/v2/catalog/items?"
        params = url.split('?')[-1]
        if params == url: return base_api + "per_page=20&order=newest_first"
        if "order=" not in params: params += "&order=newest_first"
        return base_api + params

    def get_clean_status(self, item):
        raw_status = item.get('status_id') or item.get('status') or "Unbekannt"
        mapping = {
            "6": "Neu mit Etikett ✨",
            "new_with_tags": "Neu mit Etikett ✨",
            "1": "Neu ohne Etikett ✨",
            "new_without_tags": "Neu ohne Etikett ✨",
            "2": "Sehr gut 👌",
            "very_good": "Sehr gut 👌",
            "3": "Gut 👍",
            "good": "Gut 👍",
            "4": "Zufriedenstellend 🆗",
            "satisfactory": "Zufriedenstellend 🆗"
        }
        return mapping.get(str(raw_status).lower(), str(raw_status))

    async def send_to_discord(self, item, bot):
        p = item.get('total_item_price')
        price_val = float(p.get('amount')) if isinstance(p, dict) else float(p)
        total_price = round(price_val + 0.70 + (price_val * 0.05) + 3.99, 2)
        
        item_id = item.get('id')
        item_url = item.get('url') or f"https://www.vinted.de/items/{item_id}"
        
        brand = item.get('brand_title') or "Keine Marke"
        status = self.get_clean_status(item)
        
        photos = item.get('photos', [])
        if not photos and item.get('photo'): photos = [item.get('photo')]

        image_urls = [img.get('url', '').replace("/medium/", "/full/") for img in photos if img.get('url')]
        main_img = image_urls[0] if image_urls else ""

        # Erstelle das Embed-Objekt korrekt
        embed = discord.Embed(
            title=f"🔥 {item.get('title')}",
            url=item_url,
            color=0x09b1ba,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="💶 Preis", value=f"**{price_val:.2f} €**", inline=True)
        embed.add_field(name="🚚 Gesamt ca.", value=f"**{total_price:.2f} €**", inline=True)
        embed.add_field(name="📏 Größe", value=item.get('size_title', 'N/A'), inline=True)
        embed.add_field(name="🏷️ Marke", value=brand, inline=True)
        embed.add_field(name="✨ Zustand", value=status, inline=True)
        embed.add_field(name="⏰ Gefunden", value=f"<t:{int(time.time())}:R>", inline=True)
        embed.add_field(name="⚡ Aktionen", value=f"[🛒 Kaufen](https://www.vinted.de/transaction/buy/new?item_id={item_id}) | [💬 Nachricht]({item_url}#message)", inline=False)

        # Bild hinzufügen, falls vorhanden
        if main_img:
            embed.set_image(url=main_img)

        embed.set_footer(text="Live Sniper • Alle Bilder & Details")

        # Hole den Channel mit der gespeicherten Channel-ID
        channel = bot.get_channel(int(self.channel_id))  # Channel-ID als Integer umwandeln
        if channel:
            await channel.send(embed=embed)
        else:
            print(f"❌ Fehler: Channel mit ID {self.channel_id} nicht gefunden!")

    async def run(self, bot):
        self.fetch_cookie()
        print(f"🎯 Sniper aktiv! Scan alle 10 Sek.")
        while True:
            try:
                response = self.session.get(self.api_url, headers=self.headers)
                if response.status_code == 200:
                    items = response.json().get("items", [])
                    for item in items:
                        if item["id"] not in self.seen_items:
                            if len(self.seen_items) > 0:
                                await self.send_to_discord(item, bot)  # Direkter await-Aufruf, kein asyncio.run
                                print(f"✅ NEU: {item.get('title')}")
                            self.seen_items.append(item["id"])
                    if len(self.seen_items) > 500: self.seen_items = self.seen_items[-200:]
                elif response.status_code == 403:
                    print("⚠️ Blockiert! Warte 2 Min...")
                    await asyncio.sleep(120)  # Asynchron warten
                await asyncio.sleep(10)  # Asynchron warten
            except Exception as e:
                print(f"❌ Fehler: {e}")
                await asyncio.sleep(10)  # Asynchron warten

    def fetch_cookie(self):
        print("[*] Verbindung wird aufgebaut...")
        try: self.session.get("https://www.vinted.de", headers=self.headers)
        except: pass


# ==========================================
# Discord Bot Setup
# ==========================================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)  # Prefix für traditionelle Befehle anpassen

# Der Startscan-Befehl als normaler Bot-Befehl
@bot.command(name="startscan")
async def startscan(ctx, url: str):
    """Startet den Scan für die angegebene URL im aktuellen Kanal."""
    if not url:
        await ctx.send("❌ Bitte gib eine URL an!")
        return
    
    channel_id = str(ctx.channel.id)
    
    # URL für den Kanal speichern
    channels_data[channel_id] = {
        "url": url
    }
    with open(CHANNELS_FILE, 'w') as f:
        json.dump(channels_data, f, indent=4)
    
    await ctx.send(f"Bot wird jetzt die URL {url} im Channel {ctx.channel.name} überwachen!")
    
    # VintedSniper für den aktuellen Channel starten
    sniper = VintedSniper(url, channel_id)
    
    # Starte Sniper in einem separaten Task, um den Bot nicht zu blockieren
    bot.loop.create_task(sniper.run(bot))

@bot.event
async def on_ready():
    print(f'Bot ist eingeloggt als {bot.user}')

    # Automatisches Starten des Snipers für gespeicherte URLs in allen Channels
    for channel_id, data in channels_data.items():
        url = data['url']
        print(f"Starte VintedSniper für Channel ID {channel_id} mit URL {url}")
        sniper = VintedSniper(url, channel_id)
        
        # Starte Sniper in einem separaten Task, um den Bot nicht zu blockieren
        bot.loop.create_task(sniper.run(bot))

# Starte den Bot
bot.run(os.getenv("DISCORD_TOKEN"))
