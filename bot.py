import discord
from discord.ext import commands, tasks
import tls_client
import time
import json

# Die Datei für die Channels und URLs
CHANNELS_FILE = "channel_urls.json"

# Laden oder Erstellen der Datei für die Channel-URLs
try:
    with open(CHANNELS_FILE, 'r') as f:
        channels_data = json.load(f)
except FileNotFoundError:
    channels_data = {}

# ==========================================
# VintedSniper Klasse bleibt unverändert
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

        data = {
            "username": "Vinted Sniper PRO",
            "embeds": [{
                "title": f"🔥 {item.get('title')}",
                "url": item_url,
                "color": 0x09b1ba,
                "fields": [
                    {"name": "💶 Preis", "value": f"**{price_val:.2f} €**", "inline": True},
                    {"name": "🚚 Gesamt ca.", "value": f"**{total_price:.2f} €**", "inline": True},
                    {"name": "📏 Größe", "value": item.get('size_title', 'N/A'), "inline": True},
                    {"name": "🏷️ Marke", "value": brand, "inline": True},
                    {"name": "✨ Zustand", "value": status, "inline": True},
                    {"name": "⏰ Gefunden", "value": f"<t:{int(time.time())}:R>", "inline": True},
                    {"name": "⚡ Aktionen", "value": f"[🛒 Kaufen](https://www.vinted.de/transaction/buy/new?item_id={item_id}) | [💬 Nachricht]({item_url}#message)", "inline": False}
                ],
                "image": {"url": main_img},
                "footer": {"text": "Live Sniper • Alle Bilder & Details"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }]
        }

        # Hole den Channel mit der gespeicherten Channel-ID
        channel = bot.get_channel(int(self.channel_id))  # Channel-ID als Integer umwandeln
        if channel:
            await channel.send(embed=data)
        else:
            print(f"❌ Fehler: Channel mit ID {self.channel_id} nicht gefunden!")

    def run(self, bot):
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
                                asyncio.run(self.send_to_discord(item, bot))  # Nachrichten an den richtigen Channel senden
                                print(f"✅ NEU: {item.get('title')}")
                            self.seen_items.append(item["id"])
                    if len(self.seen_items) > 500: self.seen_items = self.seen_items[-200:]
                elif response.status_code == 403:
                    print("⚠️ Blockiert! Warte 2 Min...")
                    time.sleep(120)
                time.sleep(10)
            except Exception as e:
                print(f"❌ Fehler: {e}")
                time.sleep(10)

# ==========================================
# Discord Bot Setup
# ==========================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot ist eingeloggt als {bot.user}')

    # Automatisches Starten des Snipers für gespeicherte URLs in allen Channels
    for channel_id, data in channels_data.items():
        url = data['url']
        print(f"Starte VintedSniper für Channel {channel_id} mit URL {url}")
        sniper = VintedSniper(url, channel_id)
        asyncio.create_task(sniper.run(bot))

@bot.command()
async def startscan(ctx, url: str):
    """Startet den Scan für die angegebene URL im aktuellen Kanal."""
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
    asyncio.create_task(sniper.run(bot))

# Bot starten
bot.run('DEIN_DISCORD_BOT_TOKEN')  # Dein Discord Bot Token hier einfügen
