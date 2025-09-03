# -*- coding: utf-8 -*-
import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timedelta, UTC
import aiofiles

# Dieser Code ist von Lukas1120987 geschrieben. Die Nutzung ist nur unter den Bedingungen der MIT-Lizenz möglich. 

# Wichtige Dinge:
# - Der Bot muss selber gehostet werden
# - Wir übernehmen keine Verantwortung über diese Code und möglichen Schaden, den dieser anrichten kann

# Informationen:
# - Programmiersprache: Python (Empfohlen ist 3.13)
# - Bibliotheken (siehe imports)
# - Der Bot funktioniert nur für einen Server

KANAL_ID = 0000000000000000000 #ID, des Kanals, wo das Menü hin soll
ERLAUBTE_ROLLE_ID = 0000000000000000000 # Die Rolle, die das Menü benutzten darf (z.B.Team)
DATEIPFAD = "bestrafungen.json" #Die Datenbank, wo die Fälle gespeichert werden
MESSAGE_ID_PATH = "message_id_bestrafungen.json" # Die Datenbank, wo die Id der Nachricht gespeichert wird, dass sie nach Bot-Neustart wieder geht
BESTRAFUNGEN_KANAL_ID = 0000000000000000000 # ID des Kanals, wo die Logs hineingesendet werden sollen

async def lade_message_id():
    if not os.path.exists(MESSAGE_ID_PATH):
        return None
    async with aiofiles.open(MESSAGE_ID_PATH, "r") as f:
        try:
            data = json.loads(await f.read())
            return data.get("message_id")
        except:
            return None

async def speichere_message_id(message_id):
    async with aiofiles.open(MESSAGE_ID_PATH, "w") as f:
        await f.write(json.dumps({"message_id": message_id}))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

cases = {}

async def lade_cases():
    if not os.path.exists(DATEIPFAD):
        async with aiofiles.open(DATEIPFAD, "w", encoding="utf-8") as f:
            await f.write(json.dumps({}))
    async with aiofiles.open(DATEIPFAD, "r", encoding="utf-8") as f:
        return json.loads(await f.read() or "{}")

async def speichere_cases(cases):
    async with aiofiles.open(DATEIPFAD, "w", encoding="utf-8") as f:
        await f.write(json.dumps(cases, ensure_ascii=False, indent=2))

def format_datetime(iso_str):
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%d.%m.%Y %H:%M Uhr")

class CaseModal(discord.ui.Modal, title="📋 Neuer Case"):
    def __init__(self):
        super().__init__()
        self.nutzer = discord.ui.TextInput(label="Nutzername")
        self.art = discord.ui.TextInput(label="Art des Falls (Bei Kick -> Tage = 0)")
        self.grund = discord.ui.TextInput(label="Grund", style=discord.TextStyle.long)
        self.dauer = discord.ui.TextInput(label="Dauer in Tagen")

        self.add_item(self.nutzer)
        self.add_item(self.art)
        self.add_item(self.grund)
        self.add_item(self.dauer)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            tage = int(self.dauer.value)
        except ValueError:
            await interaction.response.send_message("❌ Dauer muss eine Zahl sein.", ephemeral=True)
            return

        username = self.nutzer.value.strip()
        case = {
            "art": self.art.value.strip(),
            "grund": self.grund.value.strip(),
            "dauer": tage,
            "zeitpunkt": datetime.now(UTC).isoformat(),
            "author": str(interaction.user)
        }

        cases.setdefault(username, []).append(case)
        await speichere_cases(cases)
        await interaction.response.send_message(f"✅ Case für **{username}** gespeichert.", ephemeral=True)

        embed = discord.Embed(
            title=f"📝 Neuer Case für {username}",
            description="Ein neuer Fall wurde erstellt.",
            color=discord.Color.red(),
            timestamp=datetime.now(UTC)
        )
        embed.add_field(name="📝 Art", value=case["art"], inline=False)
        embed.add_field(name="📋 Grund", value=case["grund"], inline=False)
        embed.add_field(name="⏳ Dauer", value=f"{case['dauer']} Tage", inline=True)
        embed.add_field(name="👤 Autor", value=case["author"], inline=True)
        embed.add_field(name="🕒 Zeitpunkt", value=format_datetime(case["zeitpunkt"]), inline=False)
        embed.set_footer(text="Case-System von Lukas")

        kanal = bot.get_channel(BESTRAFUNGEN_KANAL_ID)
        if kanal:
            await kanal.send(embed=embed)

class EditCaseDropdown(discord.ui.Select):
    def __init__(self, username, eintraege, user):
        self.username = username
        self.eintraege = eintraege
        self.user = user
        options = [
            discord.SelectOption(label=f"{i+1}. {e['grund']}", value=str(i))
            for i, e in enumerate(eintraege)
        ]
        super().__init__(placeholder="✏️ Case zum Bearbeiten auswählen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Nur du darfst das bedienen!", ephemeral=True)
            return

        index = int(self.values[0])
        eintrag = cases[self.username][index]

        await interaction.response.send_message(
            f"✏️ Du bearbeitest Case #{index+1}: **{eintrag['grund']}**\n"
            f"Bitte sende den neuen Grund (oder 'skip' zum Überspringen):", ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and isinstance(m.channel, discord.DMChannel)

        try:
            msg_grund = await bot.wait_for("message", check=check, timeout=120)
            neuer_grund = msg_grund.content.strip()
            if neuer_grund.lower() != "skip" and neuer_grund != "":
                cases[self.username][index]["grund"] = neuer_grund

            await interaction.followup.send("Bitte gib die neue Dauer in Tagen ein (oder 'skip'):", ephemeral=True)
            msg_dauer = await bot.wait_for("message", check=check, timeout=120)
            neuer_dauer = msg_dauer.content.strip()
            if neuer_dauer.lower() != "skip":
                dauer_int = int(neuer_dauer)
                cases[self.username][index]["dauer"] = dauer_int

            await speichere_cases(cases)
            await interaction.followup.send("✅ Case wurde erfolgreich aktualisiert.", ephemeral=True)

        except ValueError:
            await interaction.followup.send("❌ Dauer muss eine Zahl sein.", ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ Timeout oder Fehler beim Bearbeiten.", ephemeral=True)

class DeleteCaseDropdown(discord.ui.Select):
    def __init__(self, username, eintraege):
        self.username = username
        options = [
            discord.SelectOption(label=f"{i+1}. {e['grund']}", value=str(i))
            for i, e in enumerate(eintraege)
        ]
        super().__init__(placeholder="🗑️ Case zum Löschen auswählen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        eintrag = cases[self.username].pop(index)
        if not cases[self.username]:
            del cases[self.username]
        await speichere_cases(cases)
        await interaction.response.send_message(f"🗑️ Case '{eintrag['grund']}' gelöscht.", ephemeral=True)

class CaseVerwaltungView(discord.ui.View):
    def __init__(self, username, eintraege, user):
        super().__init__(timeout=120)
        self.username = username
        self.eintraege = eintraege
        self.user = user
        self.add_item(DeleteCaseDropdown(username, eintraege))
        self.edit_dropdown = None

    @discord.ui.button(label="✏️ Bearbeiten", style=discord.ButtonStyle.blurple)
    async def bearbeiten(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Nur du darfst das bedienen!", ephemeral=True)
            return

        if not self.eintraege:
            await interaction.response.send_message("ℹ️ Keine Cases zum Bearbeiten vorhanden.", ephemeral=True)
            return

        self.edit_dropdown = EditCaseDropdown(self.username, self.eintraege, self.user)
        self.clear_items()
        self.add_item(self.edit_dropdown)
        await interaction.response.edit_message(content="Wähle einen Case zum Bearbeiten aus:", view=self)

class CaseHauptmenu(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=None)
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Nur du kannst dieses Menü benutzen.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="📋 Neuer Case", style=discord.ButtonStyle.green)
    async def neuer_case(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CaseModal())

    @discord.ui.button(label="📁 Nutzer-Cases", style=discord.ButtonStyle.blurple)
    async def nutzer_cases(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✉️ Gib den Nutzernamen ein (DM):", ephemeral=True)

        def check(m):
            return m.author == interaction.user and isinstance(m.channel, discord.DMChannel)

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            username = msg.content.strip()
            eintraege = cases.get(username, [])
            if not eintraege:
                await interaction.followup.send("❌ Keine Einträge gefunden.", ephemeral=True)
                return

            embed = discord.Embed(title=f"📄 Fälle von {username}", color=discord.Color.orange())
            for i, e in enumerate(eintraege, 1):
                autor = e.get("author", "Unbekannt")
                embed.add_field(
                    name=f"#{i}",
                    value=f"📋 Grund: {e['grund']}\n⏳ Dauer: {e['dauer']} Tage\n🕒 Zeit: {format_datetime(e['zeitpunkt'])}\n👤 Autor: {autor}",
                    inline=False
                )
            await interaction.followup.send(embed=embed, view=CaseVerwaltungView(username, eintraege, interaction.user), ephemeral=True)
        except:
            await interaction.followup.send("⏰ Zeitüberschreitung.", ephemeral=True)

    @discord.ui.button(label="🔍 Ähnliche Nutzernamen finden", style=discord.ButtonStyle.gray)
    async def aehnliche_nutzer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✉️ Gib einen Teil des Namens ein (DM):", ephemeral=True)

        def check(m):
            return m.author == interaction.user and isinstance(m.channel, discord.DMChannel)

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            eingabe = msg.content.strip().lower()
            aehnliche = [name for name in cases.keys() if eingabe in name.lower()]

            if not aehnliche:
                await interaction.followup.send("❌ Keine ähnlichen Nutzernamen gefunden.", ephemeral=True)
                return

            embed = discord.Embed(title="🔍 Ähnliche Nutzernamen", color=discord.Color.blue())
            embed.description = "\n".join(f"- {name}" for name in aehnliche)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except:
            await interaction.followup.send("⏰ Zeitüberschreitung oder Fehler.", ephemeral=True)

class KanalButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📄 Case-Menü öffnen", style=discord.ButtonStyle.green)
    async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not any(role.id == ERLAUBTE_ROLLE_ID for role in member.roles):
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        try:
            await interaction.user.send("📄 Case-Menü geöffnet:", view=CaseHauptmenu(interaction.user))
            await interaction.response.send_message("✉️ Menü per DM gesendet.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Deine DMs sind deaktiviert.", ephemeral=True)

@tasks.loop(hours=24)
async def auto_cleanup():
    jetzt = datetime.now(UTC)
    geaendert = False
    for nutzer in list(cases.keys()):
        neue = [c for c in cases[nutzer] if datetime.fromisoformat(c["zeitpunkt"]) > jetzt - timedelta(weeks=2)]
        if len(neue) < len(cases[nutzer]):
            geaendert = True
        if neue:
            cases[nutzer] = neue
        else:
            del cases[nutzer]
    if geaendert:
        await speichere_cases(cases)

@bot.event
async def on_ready():
    global cases
    cases = await lade_cases()
    auto_cleanup.start()
    print(f"✅ Bot ist bereit als {bot.user}.")

    kanal = bot.get_channel(KANAL_ID)
    if not kanal:
        print("❌ Kanal nicht gefunden.")
        return

    message_id = await lade_message_id()
    if message_id:
        try:
            nachricht = await kanal.fetch_message(message_id)
            await nachricht.edit(content="📝 Klicke unten, um das Case-Menü zu öffnen:", view=KanalButtonView())
            print("📬 Nachricht erfolgreich aktualisiert.")
            return
        except discord.NotFound:
            print("⚠️ Nachricht nicht gefunden – sende neu.")
        except Exception as e:
            print(f"⚠️ Fehler beim Abrufen: {e}")

    msg = await kanal.send(content="📝 Klicke unten, um das Case-Menü zu öffnen:", view=KanalButtonView())
    await speichere_message_id(msg.id)
    print(f"📥 Neue Nachricht gesendet und ID gespeichert: {msg.id}")

# Starte den Bot
from mytoken import TOKEN1 #Datei, wo der Token des Bots ist heißt mytoken.py
bot.run(TOKEN1) # Straten des Bots
