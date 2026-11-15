import os
import json
import asyncio
import re
import time
import io
import random
from collections import OrderedDict, deque
from datetime import timedelta

from dotenv import load_dotenv
import discord

from discord import app_commands
from discord.ext import commands

# Load Wispbyte's .env file before reading any environment variables.
# With the server working directory set to /home/container, this loads
# /home/container/.env without hard-coding a hosting-specific path.
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "1563997203377426623"))
DEFAULT_MOD_LOG_CHANNEL_ID = 1571301904946831441
STAFF_ROLE_IDS = {
    int(value.strip())
    for value in os.getenv("STAFF_ROLE_IDS", "").split(",")
    if value.strip().isdigit()
}
STAFF_ROLE_KEYWORDS = (
    "staff", "moderator", "mod", "admin", "administrator",
    "helper", "management", "owner",
)
EMOJIS = {
    "link": "<:Link:1568838760538447982>",
    "loading": "<a:Loading:1568727971806580747>",
    "denied": "<a:Denied:1568726299428524104>",
    "confirmed": "<:Confirmed:1568725741460398260>",
    "laughing": "<a:Laughing:1568724733074350140>",
}
MAX_MESSAGE_CACHE = 5000
AUDIT_LOOKBACK_SECONDS = 30
DUPLICATE_WINDOW_SECONDS = 60
DUPLICATE_GIF_URL = "https://media.tenor.com/QTG7rHOz300AAAAM/goku-namek.gif"
MIN_DUPLICATE_LENGTH = 12

# BRAX blacklist and ticket configuration
BLACKLIST_ROLES = {
    "Suggestion blacklist": 1571274114881167601,
    "Application blacklist": 1564081888123953152,
    "Image blacklist": 1571274714414973009,
    "Role blacklist": 1570618973731688468,
    "Staff blacklist": 1570148574480830628,
    "Divine punishment": 1571292901659644024,
}
GENERAL_CHANNEL_ID = 1561145710361976882
SUGGESTION_CHANNEL_ID = 1517259302459543714
MEDIA_CHANNEL_ID = 1561145636559003749
TICKETS_CHANNEL_ID = 1561188845154865173
TICKET_CATEGORY_ID = 1561150725588000808
TICKET_STAFF_ROLE_ID = 1563998176187260949
TICKET_LOG_CHANNEL_ID = 1571315910684180652
TICKET_EMOJIS = {
    "open": "<:Ticket:1571278544041156668>",
    "claim": "<a:Claim:1571281287853907978>",
    "reason": "<a:Reason:1571280404714098729>",
    "close": "<:Lock:1571279856690266213>",
}
STAFF_ROLE_NAMES = {
    "developers", "senior admin", "admin", "trial admin",
    "zinzicraftian admin", "senior moderator", "moderator",
    "trial moderator", "ingame admin", "ingame moderator",
}
DIVINE_PUNISHMENT_REMOVAL_ALLOWED_IDS = {
    781537035428429866,  # noobidbody
    942862192867409941,  # eyeless
    1521469840970350632, # Braxton
    1511412885040009309, # kaydnn
    1369381936283389983, # theimpostorsyndrome/testo
    1276932593790484636, # bob061344/British guy
    718619652187750411, # additional Divine punishment authorization
}
BRAX_USAGE_ROLE_ID = 1571309152440025190

LESSER_BRAX_USAGE_ROLE_ID = 1571343801149296660
UWU_AUTHORIZED_IDS = {1511412885040009309, 1521469840970350632, 1011740267453366434}  # ch33zee

BRAX_COINS_EMOJI = "<:Braxcoins:1571355479278485624>"
COINFLIP_EMOJI = "<a:Coinflip:1571355371086422166>"
ECONOMY_FILE = "brax_economy.json"
MAX_GAMBLE_MULTIPLIER = 30
try:
    with open(ECONOMY_FILE, "r", encoding="utf-8") as file:
        economy_data = json.load(file)
except (OSError, json.JSONDecodeError):
    economy_data = {"balances": {}, "message_counts": {}, "stocks": {}}

economy_data.setdefault("inventories", {})
economy_data.setdefault("mine_cooldowns", {})
economy_data.setdefault("trades", {})

def save_economy():
    with open(ECONOMY_FILE, "w", encoding="utf-8") as file:
        json.dump(economy_data, file, ensure_ascii=False, indent=2)

def economy_key(guild_id, user_id):
    return f"{guild_id}:{user_id}"

def coin_balance(guild_id, user_id):
    return int(economy_data.setdefault("balances", {}).get(economy_key(guild_id, user_id), 0))

def set_coin_balance(guild_id, user_id, amount):
    economy_data.setdefault("balances", {})[economy_key(guild_id, user_id)] = int(amount)
    save_economy()

def add_coins(guild_id, user_id, amount):
    set_coin_balance(guild_id, user_id, coin_balance(guild_id, user_id) + int(amount))

def spend_coins(guild_id, user_id, amount):
    balance = coin_balance(guild_id, user_id)
    if amount < 0 or balance < amount:
        return False
    set_coin_balance(guild_id, user_id, balance - amount)
    return True


MINING_LOOT = [
    ("Dirt",1,260),("Scrap Metal",4,150),("Circuit Scrap",7,95),("Copper Ore",5,110),
    ("Glass Shard",3,100),("Glow Moss",4,85),("Amber Resin",8,70),("Obsidian",10,55),
    ("Toxic Sludge",6,65),("Sugar Quartz",5,70),("Sulfur",4,75),("Gunpowder",6,50),
    ("GlowCap",5,60),("Blossom Petal",3,65),("Gear Bits",5,90),("Wool Tuft",3,60),
    ("Spider Silk",8,45),("Desert Rose",7,42),("Living Coral",9,35),("Frost Fur",8,35),
    ("Dino Hide",9,32),("Squid Ink",6,40),("Glow Plankton",6,45),("Snake Venom",11,24),
    ("Raptor Claw",12,24),("Silver Ore",12,28),("Cryo Crystal",14,22),("Magma Core",18,18),
    ("Emerald Shard",20,16),("Golden Nugget",25,12),("Sea Pearl",22,12),("Moon",30,9),
    ("Portal Fluid",35,8),("Flux Crystal",45,7),("Wriggly Worm",4,42),("Crystal Ant",8,18),
    ("Frog Legs",6,22),("Crab Claw",9,18),("Black Truffle",18,8),("Saffron",20,7),
    ("Dragon Pepper",24,6),("Ancient Spice",30,4),("Golden Honey",28,5),("Phoenix Egg",90,1),
    ("Raw Fish",5,25),("Magma Crab",32,4),("Storm Eel",38,3),("Void Tentacle",55,2),
    ("Rock Grub",7,20),("Thorn Beetle",16,7),("Moon Cheese",26,5),("Gumdrop",4,25),
    ("Lollipop",5,20),("Candy Cane",7,14),("Almond Water",25,5),("Thorn Resin",35,4),
    ("Wisp Essence",50,2),("Meteor Iron",55,2),("Quantum Dust",60,2),("Ancient Alloy",65,1),
    ("Void Essence",75,1),("Relic Gear",80,1),("Phoenix Feather",95,1),("Chrono Crystal",100,1),
    ("Dark Matter",120,1),("Singularity Shard",150,1),
]
MINING_ITEM_LOOKUP = {name.casefold(): name for name, _, _ in MINING_LOOT}
MINING_ITEM_VALUES = {name: value for name, value, _ in MINING_LOOT}
MINING_COOLDOWN_SECONDS = 30
TRADE_CATEGORY_ID = 1571397522289729686

def inventory_key(guild_id, user_id):
    return economy_key(guild_id, user_id)

def get_inventory(guild_id, user_id):
    return economy_data.setdefault("inventories", {}).setdefault(inventory_key(guild_id, user_id), {})

def add_item(guild_id, user_id, item, amount):
    inventory = get_inventory(guild_id, user_id)
    inventory[item] = int(inventory.get(item, 0)) + int(amount)
    if inventory[item] <= 0:
        inventory.pop(item, None)
    save_economy()

def normalize_mining_item(value):
    return MINING_ITEM_LOOKUP.get(" ".join(str(value).casefold().split()))

def active_trade_for_channel(channel_id):
    for trade in economy_data.setdefault("trades", {}).values():
        if int(trade.get("channel_id", 0)) == int(channel_id):
            return trade
    return None

def trade_offer_for(trade, user_id):
    return trade.setdefault("offers", {}).setdefault(str(user_id), {"coins": 0, "items": {}})

def trade_member_ids(trade):
    return [int(value) for value in trade.get("user_ids", [])]

def refund_trade(guild_id, trade):
    for user_id in trade_member_ids(trade):
        offer = trade_offer_for(trade, user_id)
        coins = int(offer.get("coins", 0))
        if coins > 0:
            add_coins(guild_id, user_id, coins)
        for item, amount in offer.get("items", {}).items():
            if int(amount) > 0:
                add_item(guild_id, user_id, item, int(amount))

def award_message_coin(message):
    key = economy_key(message.guild.id, message.author.id)
    counts = economy_data.setdefault("message_counts", {})
    old_count = int(counts.get(key, 0))
    new_count = old_count + 1
    counts[key] = new_count
    save_economy()
    if new_count // 10 > old_count // 10:
        add_coins(message.guild.id, message.author.id, 1)
        return 1
    return 0

LESSER_USAGE_STATE_FILE = "lesser_usage_state.json"
try:
    with open(LESSER_USAGE_STATE_FILE, "r", encoding="utf-8") as file:
        lesser_usage_state = json.load(file)
except (OSError, json.JSONDecodeError):
    lesser_usage_state = {"strikes": {}, "blocked_users": []}

def save_lesser_usage_state():
    with open(LESSER_USAGE_STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(lesser_usage_state, file, ensure_ascii=False, indent=2)

def has_lesser_usage(member):
    return any(role.id == LESSER_BRAX_USAGE_ROLE_ID for role in getattr(member, "roles", []))

def is_uwu_authorized(member):
    return getattr(member, "id", None) in UWU_AUTHORIZED_IDS

USAGE_ROLE_GRANTER_IDS = {
    1521469840970350632,  # Braxton
    1511412885040009309,  # kaydnn
}
role_blacklist_warnings = {}
BLACKLIST_ASSIGNMENTS_FILE = "blacklist_assignments.json"
MOD_LOG_CONFIG_FILE = "mod_log_config.json"
MODERATION_HISTORY_FILE = "moderation_history.json"
try:
    with open(MOD_LOG_CONFIG_FILE, "r", encoding="utf-8") as file:
        mod_log_channels = json.load(file)
except (OSError, json.JSONDecodeError):
    mod_log_channels = {}

try:
    with open(MODERATION_HISTORY_FILE, "r", encoding="utf-8") as file:
        moderation_history = json.load(file)
except (OSError, json.JSONDecodeError):
    moderation_history = {}

UWU_LOCKS_FILE = "uwu_locks.json"
try:
    with open(UWU_LOCKS_FILE, "r", encoding="utf-8") as file:
        uwu_locks = json.load(file)
except (OSError, json.JSONDecodeError):
    uwu_locks = {}

def save_moderation_history():
    with open(MODERATION_HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(moderation_history, file, ensure_ascii=False, indent=2)

def record_moderation_action(target, action, moderator, reason, duration=None):
    try:
        entries = moderation_history.setdefault(str(target.id), [])
        entries.append({
            "action": str(action),
            "target_name": str(target),
            "moderator": str(moderator),
            "moderator_id": moderator.id,
            "reason": str(reason or "No reason provided"),
            "duration": duration,
            "timestamp": discord.utils.utcnow().isoformat(),
        })
        moderation_history[str(target.id)] = entries[-100:]
        save_moderation_history()
        print(f"BRAX HISTORY: saved {action} for target {target.id}, moderator {moderator.id}")
        return True
    except (OSError, TypeError, AttributeError) as error:
        print(f"BRAX HISTORY ERROR: could not save {action}: {error}")
        return False

def save_uwu_locks():
    with open(UWU_LOCKS_FILE, "w", encoding="utf-8") as file:
        json.dump(uwu_locks, file, ensure_ascii=False, indent=2)

def uwu_lock_key(guild_id, user_id):
    return f"{guild_id}:{user_id}"

def moderator_label(moderator_id, fallback="Unknown"):
    if moderator_id == 1521469840970350632:
        return "<:Brax:1571324199765549219> Braxton"
    if moderator_id == 1511412885040009309:
        return "<:Kaydn:1571324228127690954> kaydnn"
    return str(fallback)

try:
    with open(BLACKLIST_ASSIGNMENTS_FILE, "r", encoding="utf-8") as file:
        blacklist_assignments = json.load(file)
except (OSError, json.JSONDecodeError):
    blacklist_assignments = {}


def save_blacklist_assignments():
    with open(BLACKLIST_ASSIGNMENTS_FILE, "w", encoding="utf-8") as file:
        json.dump(blacklist_assignments, file)


def save_mod_log_channels():
    with open(MOD_LOG_CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(mod_log_channels, file)


def blacklist_assignment_key(guild_id, user_id, role_id):
    return f"{guild_id}:{user_id}:{role_id}"

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="b!", intents=intents, help_command=None)

# In-memory only: message contents are not persisted across restarts.
message_cache = OrderedDict()
# Tracks recent messages by server, channel, and normalized text.
recent_messages = {}


def shorten(value, limit=1024):
    value = str(value or "")
    return value if len(value) <= limit else value[:limit - 3] + "..."


def is_high_staff(member):
    """BRAX command access is granted only by the dedicated BRAX Usage role."""
    return any(role.id == BRAX_USAGE_ROLE_ID for role in member.roles)


def is_staff_role(role):
    if role.id in STAFF_ROLE_IDS:
        return True
    name = role.name.casefold()
    return any(word in name for word in STAFF_ROLE_KEYWORDS)


def staff_roles_for(member):
    return [
        role for role in member.roles
        if role != member.guild.default_role and is_staff_role(role)
    ]


def role_with_icon(member):
    if member is None:
        return None
    roles = sorted(staff_roles_for(member), key=lambda r: r.position, reverse=True)
    for role in roles:
        if role.display_icon:
            return role
    roles = sorted(member.roles, key=lambda r: r.position, reverse=True)
    for role in roles:
        if role != member.guild.default_role and role.display_icon:
            return role
    return roles[0] if roles else None


def make_embed(title, description, color):
    embed = discord.Embed(
        title=title,
        description=shorten(description, 4096),
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text="BRAX • Server Logging")
    return embed


async def send_mod_log(guild, embed):
    channel_id = mod_log_channels.get(str(guild.id), DEFAULT_MOD_LOG_CHANNEL_ID)
    if not channel_id:
        print(f"BRAX: No moderation log channel configured for {guild.name}. Use b!mlog in the desired channel.")
        return False
    channel = guild.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await guild.fetch_channel(int(channel_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as error:
            print(f"BRAX: Could not access moderation log channel: {error}")
            return False
    if not isinstance(channel, discord.TextChannel):
        print("BRAX: Configured moderation log channel is not a text channel.")
        return False
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        return True
    except discord.HTTPException as error:
        print(f"BRAX: Failed to send moderation log: {error}")
        return False


async def log_brax_action(guild, target, moderator, action, reason, duration=None):
    """Save an action to the target's b!mlogs history and send it to mod logs."""
    record_moderation_action(target, action, moderator, reason, duration)
    embed = discord.Embed(
        title=f"{EMOJIS['confirmed']} {action}",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Member", value=f"{target}\nID: {target.id}", inline=True)
    embed.add_field(
        name="Moderator",
        value=f"{moderator_label(moderator.id, moderator)}\n{moderator} (ID: {moderator.id})",
        inline=True,
    )
    if duration:
        embed.add_field(name="Duration", value=str(duration), inline=True)
    embed.add_field(name="Reason", value=shorten(reason or "No reason provided"), inline=False)
    embed.set_footer(text="BRAX • Moderation")
    await send_mod_log(guild, embed)


async def send_log(embed):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as error:
            print(f"BRAX: Could not access logging channel: {error}")
            return

    if not isinstance(channel, discord.TextChannel):
        print("BRAX: LOG_CHANNEL_ID must point to a text channel.")
        return

    try:
        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException as error:
        print(f"BRAX: Failed to send log: {error}")


def add_member_field(embed, label, member):
    embed.add_field(
        name=label,
        value=f"{member.mention}\n{member}\nID: {member.id}",
        inline=True,
    )


def add_actor_fields(embed, guild, actor):
    if actor is None:
        embed.add_field(
            name="Moderator",
            value="Unknown (audit log unavailable)",
            inline=True,
        )
        return

    mention = getattr(actor, "mention", str(actor))
    actor_id = getattr(actor, "id", "unknown")
    embed.add_field(
        name="Moderator",
        value=f"{mention}\nID: {actor_id}",
        inline=True,
    )

    member = guild.get_member(actor_id) if isinstance(actor_id, int) else None
    role = role_with_icon(member)
    if role is not None:
        embed.add_field(
            name="Staff Role",
            value=f"{role.mention}\n{role.name}",
            inline=True,
        )
        icon = role.display_icon
        if isinstance(icon, discord.Asset):
            embed.set_thumbnail(url=icon.url)
        elif icon:
            embed.add_field(name="Role Icon", value=shorten(str(icon), 256), inline=True)


async def find_audit_entry(guild, action, target_id):
    cutoff = discord.utils.utcnow() - timedelta(seconds=AUDIT_LOOKBACK_SECONDS)
    try:
        async for entry in guild.audit_logs(
            limit=25,
            action=action,
            after=cutoff,
        ):
            target = entry.target
            if (
                target is not None
                and getattr(target, "id", None) == target_id
                and (discord.utils.utcnow() - entry.created_at).total_seconds()
                <= AUDIT_LOOKBACK_SECONDS
            ):
                return entry
    except discord.Forbidden:
        print("BRAX: Missing View Audit Log permission.")
    except discord.HTTPException as error:
        print(f"BRAX: Audit log lookup failed: {error}")
    return None


async def find_departure_action(member):
    for attempt in range(3):
        entry = await find_audit_entry(
            member.guild, discord.AuditLogAction.ban, member.id
        )
        if entry:
            return "ban", entry

        entry = await find_audit_entry(
            member.guild, discord.AuditLogAction.kick, member.id
        )
        if entry:
            return "kick", entry

        if attempt < 2:
            await asyncio.sleep(1)
    return "leave", None


@bot.event
async def on_ready():
    print("===================================")
    print("BRAX IS ONLINE")
    print(f"Logged in as: {bot.user} ({bot.user.id})")
    print(f"Logging channel ID: {LOG_CHANNEL_ID}")
    print(f"Connected guilds: {len(bot.guilds)}")
    print(f"Message Content Intent enabled: {bot.intents.message_content}")
    for guild in bot.guilds:
        me = guild.me
        if me is None:
            continue
        perms = me.guild_permissions
        print(
            f"BRAX permissions in {guild.name}: "
            f"Manage Messages={perms.manage_messages}, "
            f"Manage Channels={perms.manage_channels}, "
            f"Manage Roles={perms.manage_roles}, "
            f"View Audit Log={perms.view_audit_log}"
        )
        for channel_id in (GENERAL_CHANNEL_ID, MEDIA_CHANNEL_ID, SUGGESTION_CHANNEL_ID):
            channel = guild.get_channel(channel_id)
            if channel is not None:
                channel_perms = channel.permissions_for(me)
                print(
                    f"BRAX channel permissions in #{channel.name}: "
                    f"View Channel={channel_perms.view_channel}, "
                    f"Send Messages={channel_perms.send_messages}, "
                    f"Manage Messages={channel_perms.manage_messages}"
                )
    print("===================================")
    if not getattr(bot, "_brax_synced", False):
        bot.add_view(TicketPanelView())
        bot.add_view(TicketControlsView())
        try:
            synced = await bot.tree.sync()
            print(f"BRAX: Synced {len(synced)} slash commands.")
        except discord.HTTPException as error:
            print(f"BRAX: Slash-command sync failed: {error}")
        bot._brax_synced = True

    # Re-apply Divine punishment restrictions after every fresh startup so
    # already-punished members receive the updated channel overwrites too.
    if not getattr(bot, "_divine_reapplied", False):
        for guild in bot.guilds:
            for member in guild.members:
                if has_blacklist(member, "Divine punishment"):
                    await apply_divine_punishment(member)
        bot._divine_reapplied = True


@bot.event
async def on_guild_channel_create(channel):
    role = channel.guild.get_role(BLACKLIST_ROLES["Divine punishment"])
    if role is None:
        return

    role_overwrite = channel.overwrites_for(role)
    role_overwrite.send_messages = False
    role_overwrite.send_messages_in_threads = False
    role_overwrite.add_reactions = False
    role_overwrite.create_public_threads = False
    role_overwrite.create_private_threads = False
    role_overwrite.use_application_commands = False
    try:
        await channel.set_permissions(role, overwrite=role_overwrite, reason="BRAX Divine punishment channel restriction")
        for member in channel.guild.members:
            if has_blacklist(member, "Divine punishment"):
                member_overwrite = channel.overwrites_for(member)
                member_overwrite.send_messages = False
                member_overwrite.send_messages_in_threads = False
                member_overwrite.add_reactions = False
                member_overwrite.create_public_threads = False
                member_overwrite.create_private_threads = False
                member_overwrite.use_application_commands = False
                await channel.set_permissions(
                    member, overwrite=member_overwrite,
                    reason="BRAX Divine punishment: explicit member restriction",
                )
    except discord.HTTPException as error:
        print(f"BRAX: Could not apply Divine punishment to new channel {channel}: {error}")


@bot.event
async def on_member_join(member):
    embed = make_embed(
        f"{EMOJIS['confirmed']} Member Joined",
        f"{member.mention} joined the server.",
        discord.Color.green(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    add_member_field(embed, "Member", member)
    embed.add_field(
        name="Account Created",
        value=discord.utils.format_dt(member.created_at, style="F"),
        inline=False,
    )
    await send_log(embed)


@bot.event
async def on_member_remove(member):
    action, entry = await find_departure_action(member)

    if action == "ban":
        title = f"{EMOJIS['denied']} Member Banned"
        description = f"{member} was banned from the server."
        color = discord.Color.red()
    elif action == "kick":
        title = f"{EMOJIS['denied']} Member Kicked"
        description = f"{member} was kicked from the server."
        color = discord.Color.orange()
    else:
        title = f"{EMOJIS['link']} Member Left"
        description = f"{member} left the server."
        color = discord.Color.dark_grey()

    embed = make_embed(title, description, color)
    embed.add_field(name="Username", value=shorten(str(member), 256), inline=True)
    embed.add_field(name="User ID", value=str(member.id), inline=True)

    if entry is not None:
        add_actor_fields(embed, member.guild, entry.user)
        if entry.reason:
            embed.add_field(name="Reason", value=shorten(entry.reason), inline=False)

    await send_log(embed)


@bot.event
async def on_member_update(before, after):
    before_ids = {role.id for role in before.roles}
    after_ids = {role.id for role in after.roles}

    added = [
        role for role in after.roles
        if role.id not in before_ids and role != after.guild.default_role
    ]
    removed = [
        role for role in before.roles
        if role.id not in after_ids and role != after.guild.default_role
    ]
    if any(role.id == LESSER_BRAX_USAGE_ROLE_ID for role in added):
        if str(after.id) in {str(uid) for uid in lesser_usage_state.get("blocked_users", [])}:
            lesser_role = after.guild.get_role(LESSER_BRAX_USAGE_ROLE_ID)
            if lesser_role is not None:
                try:
                    await after.remove_roles(lesser_role, reason="BRAX: member permanently lost Lesser B Usage access")
                    print(f"BRAX: Removed reassigned Lesser B Usage from blocked member {after}.")
                except discord.HTTPException as error:
                    print(f"BRAX: Could not remove reassigned Lesser B Usage: {error}")

    await handle_blacklisted_role_changes(before, after, added)

    had_suggestion = any(
        role.id == BLACKLIST_ROLES["Suggestion blacklist"] for role in before.roles
    )
    has_suggestion_now = has_blacklist(after, "Suggestion blacklist")
    if had_suggestion != has_suggestion_now:
        await apply_suggestion_restriction(after)

    if not added and not removed:
        return

    entry = await find_audit_entry(
        after.guild,
        discord.AuditLogAction.member_role_update,
        after.id,
    )
    actor = entry.user if entry else None

    # Blacklist roles are protected. Ignore other blacklist roles removed
    # automatically while BRAX is applying Divine punishment (which strips
    # every other role after adding the Divine punishment role).
    divine_is_active = has_blacklist(after, "Divine punishment")
    for role in removed:
        if role.id not in BLACKLIST_ROLES.values():
            continue
        if divine_is_active and role.id != BLACKLIST_ROLES["Divine punishment"]:
            continue

        key = blacklist_assignment_key(after.guild.id, after.id, role.id)
        assigned_by = blacklist_assignments.get(key)
        actor_id = getattr(actor, "id", None)

        if role.id == BLACKLIST_ROLES["Divine punishment"]:
            allowed_to_remove = actor_id in DIVINE_PUNISHMENT_REMOVAL_ALLOWED_IDS
        else:
            allowed_to_remove = assigned_by is not None and actor_id == assigned_by

        if not allowed_to_remove:
            try:
                await after.add_roles(
                    role,
                    reason="BRAX: unauthorized attempt to remove a protected blacklist role",
                )
                print(
                    f"BRAX: Blocked unauthorized removal attempt for {role.name} "
                    f"from {after} by {actor or 'unknown actor'}."
                )
            except discord.HTTPException as error:
                print(f"BRAX: Could not restore protected blacklist role {role.name}: {error}")

            attempt_embed = make_embed(
                f"{EMOJIS['denied']} Blacklist Removal Attempt Blocked",
                f"An unauthorized attempt was made to remove **{role.name}** from {after.mention}.",
                discord.Color.red(),
            )
            add_member_field(attempt_embed, "Affected Member", after)
            attempt_embed.add_field(
                name="Attempted By",
                value=f"{getattr(actor, 'mention', 'Unknown (audit log unavailable)')}\nID: {actor_id or 'Unknown'}",
                inline=True,
            )
            attempt_embed.add_field(name="Blacklist Role", value=role.name, inline=True)
            await send_log(attempt_embed)

            if role.id == BLACKLIST_ROLES["Divine punishment"]:
                warning = (
                    "Even tho we pray for your survival your power won't help you "
                    "in this predicament all you have is praying left dear god help "
                    f"{after.mention} 🙏"
                )
            else:
                warning = (
                    f"OH no you don't buddy trying to remove your **{role.name}** "
                    f"from yourself mr {after.mention}"
                )
            await send_user_warning(after.guild, after, warning)
        else:
            blacklist_assignments.pop(key, None)
            save_blacklist_assignments()
            if actor is not None:
                await log_brax_action(
                    after.guild, after, actor,
                    f"{role.name} Removed",
                    "Authorized blacklist removal",
                )

    # Re-apply suggestion restrictions if an unauthorized removal was reversed.
    if (
        BLACKLIST_ROLES["Suggestion blacklist"] in [role.id for role in removed]
        and has_blacklist(after, "Suggestion blacklist")
    ):
        await apply_suggestion_restriction(after)

    for role in added:
        special = is_staff_role(role)
        title = (
            f"{EMOJIS['confirmed']} Staff Role Assigned"
            if special else f"{EMOJIS['confirmed']} Role Added"
        )
        embed = make_embed(
            title,
            f"A role was assigned to {after.mention}.",
            discord.Color.green(),
        )
        add_member_field(embed, "Member", after)
        embed.add_field(
            name="Assigned Role",
            value=f"{role.mention}\n{role.name}",
            inline=True,
        )
        add_actor_fields(embed, after.guild, actor)
        if special:
            embed.add_field(name="Staff Assignment", value="Yes", inline=True)
        if entry and entry.reason:
            embed.add_field(name="Reason", value=shorten(entry.reason), inline=False)
        await send_log(embed)

    for role in removed:
        special = is_staff_role(role)
        title = (
            f"{EMOJIS['denied']} Staff Role Removed"
            if special else f"{EMOJIS['denied']} Role Removed"
        )
        embed = make_embed(
            title,
            f"A role was removed from {after.mention}.",
            discord.Color.orange(),
        )
        add_member_field(embed, "Member", after)
        embed.add_field(name="Removed Role", value=role.name, inline=True)
        add_actor_fields(embed, after.guild, actor)
        if special:
            embed.add_field(name="Staff Role Change", value="Yes", inline=True)
        if entry and entry.reason:
            embed.add_field(name="Reason", value=shorten(entry.reason), inline=False)
        await send_log(embed)


@bot.event
async def on_message(message):
    if message.guild is None or (bot.user is not None and message.author.id == bot.user.id):
        return

    # Enforce Divine punishment at message level as a fallback to channel
    # permissions. Delete messages written by punished members.
    author = message.author if isinstance(message.author, discord.Member) else message.guild.get_member(message.author.id)
    if author is not None and has_blacklist(author, "Divine punishment"):
        try:
            await message.delete()
            print(f"BRAX: Deleted a message from Divine-punished member {author} in {message.channel}.")
        except discord.Forbidden:
            print("BRAX: Missing Manage Messages permission; could not delete a Divine-punished member's message.")
        except discord.HTTPException as error:
            print(f"BRAX: Failed to delete Divine-punished member message: {error}")
        return

    # Remove messages from anyone that ping a Divine-punished member,
    # including direct mentions, role mentions, and @everyone/@here.
    punished_members = [
        member for member in message.guild.members
        if has_blacklist(member, "Divine punishment")
    ]
    mentioned_ids = {member.id for member in message.mentions}
    mentioned_role_ids = {role.id for role in message.role_mentions}
    pinged = [
        member for member in punished_members
        if member.id in mentioned_ids
        or message.mention_everyone
        or any(role.id in mentioned_role_ids for role in member.roles)
    ]
    if pinged:
        try:
            await message.delete()
            print(
                "BRAX: Deleted a message that attempted to ping Divine-punished member(s): "
                + ", ".join(str(member) for member in pinged)
            )
        except discord.Forbidden:
            print("BRAX: Missing Manage Messages permission; could not delete a message pinging a Divine-punished member.")
        except discord.HTTPException as error:
            print(f"BRAX: Failed to delete message pinging Divine-punished member: {error}")
        return

    if message.author.bot:
        return

    earned_coins = award_message_coin(message)
    if earned_coins:
        try:
            await message.channel.send(
                f"{message.author.mention} earned {BRAX_COINS_EMOJI} **1 BRAX Coin**! Balance: **{coin_balance(message.guild.id, message.author.id)}**",
                delete_after=8,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except discord.HTTPException:
            pass

    # Blacklist enforcement: block image/GIF posts in General and all posts in Media.
    member = message.author if isinstance(message.author, discord.Member) else message.guild.get_member(message.author.id)

    if has_lesser_usage(member) and message.content.startswith("b!"):
        context = await bot.get_context(message)
        command_name = context.command.name if context.command else None
        if command_name not in {"mweute", "help", "gamble", "mine", "inventory", "sell", "trade", "offercoins", "offeritem", "tradeconfirm", "tradecancel"}:
            strikes = lesser_usage_state.setdefault("strikes", {})
            count = int(strikes.get(str(member.id), 0)) + 1
            strikes[str(member.id)] = count
            if count == 1:
                save_lesser_usage_state()
                await message.channel.send(
                    f"⚠️ {message.author.mention} You risk your inferior usage being removed. Do you wanna continue your peasant act?",
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            else:
                lesser_role = message.guild.get_role(LESSER_BRAX_USAGE_ROLE_ID)
                if lesser_role is not None and lesser_role in member.roles:
                    try:
                        await member.remove_roles(lesser_role, reason="BRAX: second unauthorized command attempt with Lesser B Usage")
                        blocked = lesser_usage_state.setdefault("blocked_users", [])
                        if member.id not in blocked:
                            blocked.append(member.id)
                        save_lesser_usage_state()
                        await message.channel.send(
                            f"🚫 {message.author.mention} has lost Lesser B Usage permanently. Any attempt to give it back will be reversed.",
                            allowed_mentions=discord.AllowedMentions(users=True),
                        )
                        await log_brax_action(message.guild, member, bot.user, "Lesser B Usage Revoked", "Second unauthorized BRAX command attempt; role reassignment is blocked")
                    except discord.HTTPException as error:
                        print(f"BRAX: Could not revoke Lesser B Usage from {member}: {error}")
                        await message.channel.send(f"{EMOJIS['denied']} I couldn't remove the Lesser B role. Check my Manage Roles permission and role hierarchy.")
                else:
                    blocked = lesser_usage_state.setdefault("blocked_users", [])
                    if member.id not in blocked:
                        blocked.append(member.id)
                    save_lesser_usage_state()
            return

    if message.channel.id == MEDIA_CHANNEL_ID and member and has_blacklist(member, "Image blacklist"):
        try:
            await message.delete()
            print(f"BRAX: Deleted Image-blacklisted member message in #{message.channel}.")
        except discord.Forbidden:
            print(f"BRAX: MISSING Manage Messages in #{message.channel}; could not delete Image-blacklisted message.")
        except discord.HTTPException as error:
            print(f"BRAX: Could not delete Image-blacklisted message: {error}")
        await send_user_warning(message.guild, member, "You're Image blacklisted, you can't do that buddy")
        return

    if message.channel.id == GENERAL_CHANNEL_ID and member and has_blacklist(member, "Image blacklist") and message_has_image(message):
        try:
            await message.delete()
            print(f"BRAX: Deleted image/GIF from Image-blacklisted member in #{message.channel}.")
        except discord.Forbidden:
            print(f"BRAX: MISSING Manage Messages in #{message.channel}; could not delete image/GIF.")
        except discord.HTTPException as error:
            print(f"BRAX: Could not delete image/GIF: {error}")
        await send_user_warning(message.guild, member, "You're Image blacklisted, you can't do that buddy")
        return

    if message.channel.id == SUGGESTION_CHANNEL_ID and member and has_blacklist(member, "Suggestion blacklist"):
        try:
            await message.delete()
            print(f"BRAX: Deleted suggestion from Suggestion-blacklisted member in #{message.channel}.")
        except discord.Forbidden:
            print(f"BRAX: MISSING Manage Messages in #{message.channel}; could not delete blacklisted suggestion.")
        except discord.HTTPException as error:
            print(f"BRAX: Could not delete blacklisted suggestion: {error}")
        return

    # UWU lock: replace a locked member's message with a transformed relay.
    if member is not None and uwu_lock_key(message.guild.id, member.id) in uwu_locks:
        try:
            await relay_uwu_message(message)
            print(f"BRAX UWU: relayed message from {member} in #{message.channel}.")
        except discord.Forbidden as error:
            print(f"BRAX UWU: permission failure in #{message.channel}: {error}")
        except discord.HTTPException as error:
            print(f"BRAX UWU: relay failed in #{message.channel}: {error}")
        return

    # Detect another member repeating the same text in the same channel.
    # Case and extra whitespace are ignored when comparing messages.
    normalized = " ".join(message.content.casefold().split())

    # Gambling commands are intentional repeated actions, not duplicate spam.
    if len(normalized) >= MIN_DUPLICATE_LENGTH and not normalized.startswith("b!gamble"):
        now = time.monotonic()

        # Remove expired entries so this stays small over time.
        expired = [
            key for key, value in recent_messages.items()
            if now - value["time"] > DUPLICATE_WINDOW_SECONDS
        ]
        for key in expired:
            recent_messages.pop(key, None)

        duplicate_key = (message.guild.id, message.channel.id, normalized)
        previous = recent_messages.get(duplicate_key)

        if (
            previous is not None
            and previous["author_id"] != message.author.id
            and now - previous["time"] <= DUPLICATE_WINDOW_SECONDS
        ):
            try:
                await message.delete()
                await message.channel.send(
                    DUPLICATE_GIF_URL,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                print(
                    f"BRAX: Removed duplicate message from {message.author} "
                    f"in #{message.channel}."
                )
            except discord.Forbidden:
                print(
                    "BRAX: Cannot remove duplicate message. "
                    "Give the bot Manage Messages permission."
                )
            except discord.HTTPException as error:
                print(f"BRAX: Duplicate-message action failed: {error}")
            return

        # Keep the first person's message as the original.
        if previous is None:
            recent_messages[duplicate_key] = {
                "author_id": message.author.id,
                "time": now,
            }

    message_cache[message.id] = {
        "author": message.author,
        "channel": message.channel,
        "content": message.content,
        "attachments": [item.url for item in message.attachments],
    }
    message_cache.move_to_end(message.id)

    while len(message_cache) > MAX_MESSAGE_CACHE:
        message_cache.popitem(last=False)

    # This custom on_message handler must pass messages to prefix commands.
    await bot.process_commands(message)


@bot.event
async def on_message_delete(message):
    if message.guild is None:
        return

    cached = message_cache.pop(message.id, None)
    author = cached["author"] if cached else message.author
    channel = cached["channel"] if cached else message.channel
    content = cached["content"] if cached else message.content
    attachments = (
        cached["attachments"] if cached
        else [item.url for item in getattr(message, "attachments", [])]
    )

    if author is None or getattr(author, "bot", False):
        return

    embed = make_embed(
        f"{EMOJIS['denied']} Message Deleted",
        f"A message from {author.mention} was deleted.",
        discord.Color.red(),
    )
    embed.add_field(
        name="Author",
        value=f"{author}\nID: {author.id}",
        inline=True,
    )
    embed.add_field(
        name="Channel",
        value=getattr(channel, "mention", str(channel)),
        inline=True,
    )
    embed.add_field(
        name="Message Content",
        value=shorten(content or "*Content unavailable (message was not cached).*"),
        inline=False,
    )
    if attachments:
        embed.add_field(
            name="Attachments",
            value=shorten("\n".join(attachments)),
            inline=False,
        )
    await send_log(embed)


@bot.event
async def on_bulk_message_delete(messages):
    for message in messages:
        await on_message_delete(message)


@bot.event
async def on_message_edit(before, after):
    if after.guild is None or after.author.bot:
        return

    old_attachments = [item.url for item in before.attachments]
    new_attachments = [item.url for item in after.attachments]
    if before.content == after.content and old_attachments == new_attachments:
        return

    embed = make_embed(
        f"{EMOJIS['link']} Message Edited",
        f"{after.author.mention} edited a message.",
        discord.Color.gold(),
    )
    embed.add_field(
        name="Author",
        value=f"{after.author}\nID: {after.author.id}",
        inline=True,
    )
    embed.add_field(name="Channel", value=after.channel.mention, inline=True)
    embed.add_field(
        name="Before",
        value=shorten(before.content or "*Empty or unavailable*"),
        inline=False,
    )
    embed.add_field(
        name="After",
        value=shorten(after.content or "*Empty or unavailable*"),
        inline=False,
    )
    if old_attachments != new_attachments:
        embed.add_field(
            name="Attachments Before",
            value=shorten("\n".join(old_attachments) or "None"),
            inline=False,
        )
        embed.add_field(
            name="Attachments After",
            value=shorten("\n".join(new_attachments) or "None"),
            inline=False,
        )
    await send_log(embed)



# ---------------- BLACKLISTS + TICKETS ----------------

def has_blacklist(member, label):
    role_id = BLACKLIST_ROLES[label]
    return any(role.id == role_id for role in member.roles)


def message_has_image(message):
    image_types = ("image/",)
    for attachment in message.attachments:
        content_type = (attachment.content_type or "").lower()
        filename = attachment.filename.lower()
        if content_type.startswith(image_types) or filename.endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".avif")
        ):
            return True
    text = (message.content or "").lower()
    return any(
        marker in text for marker in (
            ".gif", ".png", ".jpg", ".jpeg", ".webp",
            "tenor.com/view/", "giphy.com/gifs/", "media.tenor.com/",
        )
    )


uwu_webhooks = {}

def uwuify_text(value):
    value = str(value or "")
    if not value:
        return "uwu~"
    swaps = [
        (r"\bhello\b", "hewwo"), (r"\bhey\b", "hewwo"),
        (r"\bthe\b", "da"), (r"\bthis\b", "dis"), (r"\bthat\b", "dat"),
        (r"\bthere\b", "dere"), (r"\bthink\b", "fink"), (r"\bwith\b", "wif"),
        (r"\byou\b", "yu"), (r"\byour\b", "yur"), (r"\bare\b", "awwe"),
        (r"\bvery\b", "vewy"), (r"\blove\b", "wuv"), (r"\breally\b", "weawwy"),
        (r"\bplease\b", "pwease"), (r"\bfriend\b", "fwiend"),
        (r"\bsmall\b", "smol"), (r"\bcute\b", "kyoot"), (r"\bno\b", "nyo"),
        (r"\bokay\b", "okie"), (r"\bthanks\b", "fankies"), (r"\bwhat\b", "w-what"),
        (r"\bwhy\b", "w-why"), (r"\bwait\b", "w-wait"), (r"\bhelp\b", "hewlp"),
        (r"\bgoing\b", "g-going"), (r"\bwant\b", "w-want"), (r"\bcan\b", "c-can"),
        (r"\bhi\b", "hai"),
    ]
    for pattern, replacement in swaps:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    value = re.sub(r"[rl]", "w", value, flags=re.IGNORECASE)
    words = value.split(" ")
    for i, word in enumerate(words):
        match = re.match(r"^([^A-Za-z]*)([A-Za-z]{3,})([^A-Za-z]*)$", word)
        if match and random.random() < 0.20:
            prefix, core, suffix = match.groups()
            if core.casefold() not in {"uwu", "owo", "nya"}:
                words[i] = f"{prefix}{core[0]}-{core}{suffix}"
    value = " ".join(words)
    endings = ["nya~", ">w<", "uwu~", "owo!", "p-pwease~", "hehe~", "mwehehe"]
    if random.random() < 0.35:
        value += " " + random.choice(["*tail wag*", "*happy wiggle*", "*tiny gasp*"])
    return f"{value} {random.choice(endings)}"

async def relay_uwu_message(message):
    """Repost a transformed message, preferring a labelled webhook and falling back to BRAX."""
    channel = message.channel
    thread = channel if isinstance(channel, discord.Thread) else None
    webhook_channel = channel.parent if thread else channel
    content = uwuify_text(message.content)
    if message.attachments:
        content += "\n" + "\n".join(item.url for item in message.attachments)
    if message.embeds:
        content += "\n" + "\n".join(
            f"[Embed] {embed.title or ''} {embed.url or ''}".strip()
            for embed in message.embeds
        )
    content = shorten(content, 1900)

    delivered = False
    if isinstance(webhook_channel, discord.TextChannel):
        try:
            webhook = uwu_webhooks.get(webhook_channel.id)
            if webhook is None:
                hooks = await webhook_channel.webhooks()
                webhook = next((item for item in hooks if item.name == "BRAX UWU Relay"), None)
                if webhook is None:
                    webhook = await webhook_channel.create_webhook(name="BRAX UWU Relay")
                uwu_webhooks[webhook_channel.id] = webhook
            webhook_kwargs = {
                "content": content,
                "username": shorten(f"{message.author.display_name} (uwu)", 80),
                "avatar_url": message.author.display_avatar.url,
                "allowed_mentions": discord.AllowedMentions.none(),
            }
            # discord.py expects a real Thread object here; passing thread=None
            # raises AttributeError before the webhook request is made.
            if thread is not None:
                webhook_kwargs["thread"] = thread
            await webhook.send(**webhook_kwargs)
            delivered = True
        except (discord.HTTPException, AttributeError, TypeError) as error:
            print(f"BRAX UWU: webhook unavailable in #{channel}; using bot-message fallback: {error}")

    if not delivered:
        await channel.send(
            f"**{message.author.display_name} (uwu):** {content}",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    try:
        await message.delete()
    except discord.Forbidden:
        print(f"BRAX UWU: BRAX cannot delete the original message in #{channel}; check channel-specific Manage Messages.")
    except discord.HTTPException as error:
        print(f"BRAX UWU: original message deletion failed: {error}")


async def send_user_warning(guild, member, text):
    channel = guild.get_channel(GENERAL_CHANNEL_ID)
    if channel is None:
        try:
            channel = await guild.fetch_channel(GENERAL_CHANNEL_ID)
        except discord.HTTPException:
            return
    try:
        await channel.send(
            f"{member.mention} {text}",
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
    except discord.HTTPException as error:
        print(f"BRAX: Could not send blacklist warning: {error}")


async def apply_divine_punishment(member):
    """Silence a Divine-punished member in existing channels and strip their other roles."""
    role = member.guild.get_role(BLACKLIST_ROLES["Divine punishment"])
    if role is None:
        print("BRAX: Divine punishment role was not found.")
        return
    try:
        # Add Divine punishment first so the role-update listener knows that
        # subsequent role removals are part of BRAX's own punishment process.
        if role not in member.roles:
            await member.add_roles(role, reason="BRAX Divine punishment")

        other_roles = [
            existing for existing in member.roles
            if existing != member.guild.default_role and existing.id != role.id
        ]
        if other_roles:
            await member.remove_roles(*other_roles, reason="BRAX Divine punishment: remove other roles")
    except discord.HTTPException as error:
        print(f"BRAX: Could not fully apply Divine punishment roles: {error}")

    # Role overwrites can be overridden by another role's allow. Apply an
    # explicit member deny as well, so ordinary role hierarchy/role allows
    # cannot grant this member permission to speak or use app commands.
    for channel in member.guild.channels:
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel, discord.CategoryChannel, discord.VoiceChannel, discord.StageChannel)):
            continue
        role_overwrite = channel.overwrites_for(role)
        role_overwrite.send_messages = False
        role_overwrite.send_messages_in_threads = False
        role_overwrite.add_reactions = False
        role_overwrite.create_public_threads = False
        role_overwrite.create_private_threads = False
        role_overwrite.use_application_commands = False
        member_overwrite = channel.overwrites_for(member)
        member_overwrite.send_messages = False
        member_overwrite.send_messages_in_threads = False
        member_overwrite.add_reactions = False
        member_overwrite.create_public_threads = False
        member_overwrite.create_private_threads = False
        member_overwrite.use_application_commands = False
        try:
            await channel.set_permissions(
                role, overwrite=role_overwrite,
                reason="BRAX Divine punishment: server-wide role restriction",
            )
            await channel.set_permissions(
                member, overwrite=member_overwrite,
                reason="BRAX Divine punishment: explicit member restriction",
            )
        except discord.HTTPException as error:
            print(f"BRAX: Could not restrict Divine punishment in {channel}: {error}")


async def apply_suggestion_restriction(member):
    channel = member.guild.get_channel(SUGGESTION_CHANNEL_ID)
    if channel is None:
        try:
            channel = await member.guild.fetch_channel(SUGGESTION_CHANNEL_ID)
        except discord.HTTPException:
            return
    if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
        return
    if has_blacklist(member, "Suggestion blacklist"):
        overwrite = channel.overwrites_for(member)
        overwrite.view_channel = False
        overwrite.send_messages = False
        overwrite.add_reactions = False
        overwrite.create_public_threads = False
        overwrite.send_messages_in_threads = False
        try:
            await channel.set_permissions(member, overwrite=overwrite, reason="Suggestion blacklist")
        except discord.HTTPException as error:
            print(f"BRAX: Could not apply suggestion restriction: {error}")
    else:
        try:
            await channel.set_permissions(member, overwrite=None, reason="Suggestion blacklist removed")
        except discord.HTTPException as error:
            print(f"BRAX: Could not clear suggestion restriction: {error}")


def is_protected_staff_role(role):
    return role.name.casefold() in STAFF_ROLE_NAMES or is_staff_role(role)


async def handle_blacklisted_role_changes(before, after, added_roles):
    if not added_roles:
        return

    role_blacklisted = has_blacklist(after, "Role blacklist")
    staff_blacklisted = has_blacklist(after, "Staff blacklist")
    denied = []
    divine_blacklisted = has_blacklist(after, "Divine punishment")
    if divine_blacklisted:
        denied.extend(
            role for role in added_roles
            if role.id != BLACKLIST_ROLES["Divine punishment"]
            and role != after.guild.default_role
        )
    elif role_blacklisted:
        denied.extend(
            role for role in added_roles
            if role.id not in BLACKLIST_ROLES.values()
            and role != after.guild.default_role
        )
    elif staff_blacklisted:
        denied.extend(
            role for role in added_roles
            if role.id not in BLACKLIST_ROLES.values()
            and role != after.guild.default_role
            and is_protected_staff_role(role)
        )

    if not denied:
        return

    try:
        await after.remove_roles(*denied, reason="BRAX blacklist enforcement")
    except discord.Forbidden:
        print("BRAX: Cannot remove blacklisted role(s). Move BRAX above those roles and grant Manage Roles.")
        return
    except discord.HTTPException as error:
        print(f"BRAX: Failed to remove blacklisted role(s): {error}")
        return

    if role_blacklisted:
        now = time.monotonic()
        recent = role_blacklist_warnings.setdefault(after.id, deque())
        if len(recent) >= 2 and now - recent[-1] >= 86400:
            recent.clear()
        if len(recent) < 2:
            recent.append(now)
            await send_user_warning(
                after.guild,
                after,
                "you're role blacklisted, you can't get anymore roles",
            )


@bot.event

async def on_raw_reaction_add(payload):
    if payload.guild_id is None:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id) if guild else None
    if member is None or member.bot or not has_blacklist(member, "Suggestion blacklist"):
        return
    try:
        channel = bot.get_channel(payload.channel_id) or await bot.fetch_channel(payload.channel_id)
        parent_id = getattr(channel, "parent_id", None)
        if payload.channel_id != SUGGESTION_CHANNEL_ID and parent_id != SUGGESTION_CHANNEL_ID:
            return
        message = await channel.fetch_message(payload.message_id)
        await message.remove_reaction(payload.emoji, member)
    except discord.HTTPException:
        pass


class BlacklistSelect(discord.ui.Select):
    def __init__(self, target):
        self.target = target
        options = [
            discord.SelectOption(label=name, value=str(role_id), description=f"Give {name}")
            for name, role_id in BLACKLIST_ROLES.items()
        ]
        super().__init__(
            placeholder="Choose which blacklist to give",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="brax:blacklist:select",
        )

    async def callback(self, interaction):
        role_id = int(self.values[0])
        is_divine = role_id == BLACKLIST_ROLES["Divine punishment"]
        is_divine_authorized = interaction.user.id in DIVINE_PUNISHMENT_REMOVAL_ALLOWED_IDS

        if is_divine:
            if not is_divine_authorized:
                await interaction.response.send_message(
                    "Only the seven specifically authorized users can assign or remove Divine punishment.",
                    ephemeral=True,
                )
                return
        elif not is_high_staff(interaction.user):
            await interaction.response.send_message("You need the BRAX Usage role to use regular blacklist controls.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("You need Manage Roles to use this.", ephemeral=True)
            return
        guild = interaction.guild
        role = guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message("That blacklist role could not be found.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self.target.add_roles(role, reason=f"Blacklist assigned by {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                "I can't assign that role. Move BRAX above the blacklist roles and grant Manage Roles.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as error:
            await interaction.followup.send(f"Couldn't assign the role: {error}", ephemeral=True)
            return
        key = blacklist_assignment_key(guild.id, self.target.id, role_id)
        blacklist_assignments[key] = interaction.user.id
        save_blacklist_assignments()
        if role_id == BLACKLIST_ROLES["Suggestion blacklist"]:
            await apply_suggestion_restriction(self.target)
        if role_id == BLACKLIST_ROLES["Divine punishment"]:
            await apply_divine_punishment(self.target)
            general = guild.get_channel(GENERAL_CHANNEL_ID)
            if general:
                await general.send(
                    f"Pray for {self.target.mention} as has gotten divine punishment 🙏",
                    allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                )
        await log_brax_action(
            guild, self.target, interaction.user,
            f"{role.name} Assigned",
            "Assigned through the BRAX blacklist menu",
        )
        await interaction.followup.send(
            f"{interaction.user.mention} gave {self.target.mention} **{role.name}**.",
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )


class BlacklistView(discord.ui.View):
    def __init__(self, target):
        super().__init__(timeout=180)
        self.add_item(BlacklistSelect(target))


@bot.command(name="blacklist")
async def blacklist_command(ctx, user: discord.Member):
    if not is_high_staff(ctx.author) and ctx.author.id not in DIVINE_PUNISHMENT_REMOVAL_ALLOWED_IDS:
        await ctx.reply("You need the BRAX Usage role to use this command. The six Divine-authorized users may also open this menu for Divine punishment only.", mention_author=False)
        return
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.reply("You also need the **Manage Roles** permission.", mention_author=False)
        return
    await ctx.reply(
        f"Choose a blacklist to give to {user.mention}:",
        view=BlacklistView(user),
        mention_author=False,
    )


# Ticket panel: button opens an ephemeral dropdown.
class TicketOpenButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Open Ticket",
            style=discord.ButtonStyle.secondary,
            emoji=discord.PartialEmoji.from_str(TICKET_EMOJIS["open"]),
            custom_id="brax:tickets:open",
        )

    async def callback(self, interaction):
        await interaction.response.send_message(
            "What do you need?",
            view=TicketTypeView(),
            ephemeral=True,
        )


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketOpenButton())


class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Reporting", value="report", description="Report a member or issue"),
            discord.SelectOption(label="Appeals", value="appeal", description="Appeal a punishment"),
            discord.SelectOption(label="Applying for a role", value="roleapply", description="Apply for a server role"),
            discord.SelectOption(label="Bug issue", value="bug", description="Report a bug"),
        ]
        super().__init__(
            placeholder="What do you need?",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="brax:tickets:type",
        )

    async def callback(self, interaction):
        member = interaction.user
        await interaction.response.defer(ephemeral=True, thinking=True)
        if self.values[0] == "roleapply" and has_blacklist(member, "Application blacklist"):
            await interaction.followup.send(
                "You're application blacklisted, so you can't open an application ticket.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "The configured ticket category wasn't found. Please tell an administrator.",
                ephemeral=True,
            )
            return

        prefix = {
            "report": "Reports",
            "appeal": "Appeal",
            "roleapply": "roleapply",
            "bug": "bug",
        }[self.values[0]]
        existing_numbers = []
        for channel in category.text_channels:
            name = channel.name
            if name.startswith("closed-"):
                name = name[len("closed-"):]
            if name.startswith(prefix + "-"):
                suffix = name[len(prefix) + 1:]
                if suffix.isdigit():
                    existing_numbers.append(int(suffix))
        number = max(existing_numbers, default=0) + 1
        channel_name = f"{prefix}-{number}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                attach_files=True, embed_links=True,
            ),
        }
        staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                manage_messages=True,
            )
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                manage_channels=True, manage_messages=True,
            )

        try:
            ticket = await guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"BRAX_TICKET|opener={member.id}|type={self.values[0]}|claimed=none",
                reason=f"Ticket opened by {member}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "I need Manage Channels and permission to view the ticket category.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as error:
            await interaction.followup.send(f"Couldn't create the ticket: {error}", ephemeral=True)
            return

        embed = discord.Embed(
            title="Ticket opened",
            description="Thank you for opening a ticket we will be here shortly",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Opened by", value=member.mention, inline=True)
        embed.add_field(name="Type", value=self.values[0].replace("roleapply", "Applying for a role").title(), inline=True)
        ticket_message = await ticket.send(
            content=f"|| <@&{TICKET_STAFF_ROLE_ID}> ||",
            embed=embed,
            view=TicketControlsView(),
            allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
        )
        await interaction.followup.send(
            f"Your ticket has been created: {ticket.mention}",
            ephemeral=True,
        )


class TicketTypeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(TicketTypeSelect())


class CloseReasonModal(discord.ui.Modal, title="Close ticket with a reason"):
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Enter why this ticket is being closed",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    async def on_submit(self, interaction):
        await close_ticket_channel(interaction, str(self.reason))


def ticket_metadata(channel):
    metadata = {"opener": "Unknown", "type": "Unknown", "claimed": "Not claimed"}
    topic = channel.topic or ""
    if topic.startswith("BRAX_TICKET|"):
        for part in topic.split("|")[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                if key == "opener":
                    metadata["opener"] = value
                elif key == "type":
                    metadata["type"] = value
                elif key == "claimed":
                    metadata["claimed"] = value if value != "none" else "Not claimed"
    return metadata


async def build_ticket_transcript(channel):
    lines = [
        f"Ticket: #{channel.name}",
        f"Channel ID: {channel.id}",
        f"Created: {channel.created_at.isoformat()}",
        f"Topic: {channel.topic or 'No topic'}",
        "",
        "========== TICKET MESSAGES (oldest first) ==========",
        "",
    ]
    async for message in channel.history(limit=None, oldest_first=True):
        lines.append(f"[{message.created_at.isoformat()}] {message.author} (ID: {message.author.id})")
        lines.append(message.content or "[No text content]")
        for attachment in message.attachments:
            lines.append(f"Attachment: {attachment.filename} — {attachment.url}")
        for embed in message.embeds:
            if embed.title:
                lines.append(f"Embed title: {embed.title}")
            if embed.description:
                lines.append(f"Embed description: {embed.description}")
        lines.append("")
    return "\n".join(lines).encode("utf-8")


async def close_ticket_channel(interaction, reason=None):
    if not is_high_staff(interaction.user):
        await interaction.response.send_message("You need the BRAX Usage role to close tickets with BRAX.", ephemeral=True)
        return
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel) or channel.category_id != TICKET_CATEGORY_ID:
        await interaction.response.send_message("This button can only be used inside a ticket.", ephemeral=True)
        return
    if not reason or not reason.strip():
        await interaction.response.send_message("A closing reason is required.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    guild = channel.guild
    metadata = ticket_metadata(channel)
    log_channel = guild.get_channel(TICKET_LOG_CHANNEL_ID)
    if log_channel is None:
        try:
            log_channel = await guild.fetch_channel(TICKET_LOG_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as error:
            await interaction.followup.send(
                f"Couldn't access the ticket log channel ({error}). The ticket has been left open.",
                ephemeral=True,
            )
            return
    if not isinstance(log_channel, discord.TextChannel):
        await interaction.followup.send(
            "The configured ticket log destination isn't a text channel. The ticket has been left open.",
            ephemeral=True,
        )
        return

    try:
        transcript = await build_ticket_transcript(channel)
        filename = f"{channel.name}-transcript.txt"
        opener_value = metadata["opener"]
        if opener_value.isdigit():
            opener_value = f"<@{opener_value}> (ID: {opener_value})"
        claimed_value = metadata["claimed"]
        if claimed_value.isdigit():
            claimed_value = f"<@{claimed_value}> (ID: {claimed_value})"

        embed = discord.Embed(
            title="Ticket Closed • Transcript",
            description=f"Ticket: #{channel.name}\nChannel ID: {channel.id}",
            color=discord.Color.dark_red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Ticket Type", value=metadata["type"].replace("roleapply", "Applying for a role").title(), inline=True)
        embed.add_field(name="Opened By", value=opener_value, inline=True)
        embed.add_field(name="Claimed By", value=claimed_value, inline=True)
        embed.add_field(name="Closed By", value=f"{interaction.user.mention}\n{interaction.user} (ID: {interaction.user.id})", inline=True)
        embed.add_field(name="Closing Reason", value=shorten(reason.strip(), 1024), inline=False)
        embed.set_footer(text="BRAX • Ticket Archive")

        await log_channel.send(
            embed=embed,
            file=discord.File(io.BytesIO(transcript), filename=filename),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "I can't read the ticket or post its transcript. Check View Channel, Read Message History, Send Messages, and Attach Files permissions. The ticket has been left open.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as error:
        await interaction.followup.send(
            f"Couldn't archive the ticket transcript ({error}). The ticket has been left open.",
            ephemeral=True,
        )
        return

    try:
        await channel.delete(reason=f"Ticket closed by {interaction.user}: {reason.strip()}")
    except discord.Forbidden:
        await interaction.followup.send(
            "The transcript was saved, but I couldn't delete the ticket. Check my Manage Channels permission.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as error:
        await interaction.followup.send(
            f"The transcript was saved, but deleting the ticket failed: {error}",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        f"Ticket #{channel.name} was archived in {log_channel.mention} and deleted. Reason: {shorten(reason.strip(), 500)}",
        ephemeral=True,
    )


class TicketControlsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.primary,
        emoji=discord.PartialEmoji.from_str(TICKET_EMOJIS["claim"]),
        custom_id="brax:tickets:claim",
    )
    async def claim(self, interaction, button):
        if not is_high_staff(interaction.user):
            await interaction.response.send_message("You need the BRAX Usage role to claim tickets with BRAX.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel) or interaction.channel.category_id != TICKET_CATEGORY_ID:
            await interaction.response.send_message("This isn't a ticket channel.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = interaction.message
        embed = message.embeds[0] if message.embeds else discord.Embed(title="Ticket opened")
        embed.description = "Thank you for opening a ticket we will be here shortly\n\n" + f"**This ticket has been claimed by {interaction.user.mention}.**"
        await message.edit(embed=embed, view=self)
        channel = interaction.channel
        metadata = ticket_metadata(channel)
        metadata["claimed"] = str(interaction.user.id)
        await channel.edit(
            topic=f"BRAX_TICKET|opener={metadata['opener']}|type={metadata['type']}|claimed={metadata['claimed']}",
            reason=f"Ticket claimed by {interaction.user}",
        )
        await interaction.followup.send("Ticket claimed.", ephemeral=True)

    @discord.ui.button(
        label="Close with a reason",
        style=discord.ButtonStyle.secondary,
        emoji=discord.PartialEmoji.from_str(TICKET_EMOJIS["reason"]),
        custom_id="brax:tickets:close_reason",
    )
    async def close_reason(self, interaction, button):
        if not is_high_staff(interaction.user):
            await interaction.response.send_message("You need the BRAX Usage role to close tickets with BRAX.", ephemeral=True)
            return
        await interaction.response.send_modal(CloseReasonModal())

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        emoji=discord.PartialEmoji.from_str(TICKET_EMOJIS["close"]),
        custom_id="brax:tickets:close",
    )
    async def close(self, interaction, button):
        if not is_high_staff(interaction.user):
            await interaction.response.send_message("You need the BRAX Usage role to close tickets with BRAX.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel) or interaction.channel.category_id != TICKET_CATEGORY_ID:
            await interaction.response.send_message("This isn't a ticket channel.", ephemeral=True)
            return
        await interaction.response.send_modal(CloseReasonModal())



# ---------------- MODERATION COMMANDS ----------------

def parse_timeout_duration(value):
    """Parse durations such as 30s, 10m, 2h, 3d, 1w, or 1d2h."""
    matches = list(re.finditer(r"(\d+)\s*(w|d|h|m|s)", value.casefold()))
    if not matches:
        raise ValueError("Use a duration like 30s, 10m, 2h, 3d, 1w, or 1d2h.")
    compact = re.sub(r"\s+", "", value.casefold())
    if "".join(match.group(0).replace(" ", "") for match in matches) != compact:
        raise ValueError("That duration format isn't valid. Example: 10m, 2h, or 1d2h.")
    seconds = 0
    units = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
    for match in matches:
        seconds += int(match.group(1)) * units[match.group(2)]
    if seconds <= 0:
        raise ValueError("The timeout duration must be greater than zero.")
    if seconds > 28 * 86400:
        raise ValueError("Discord timeouts cannot be longer than 28 days.")
    return timedelta(seconds=seconds)


async def moderation_gate(ctx, permission_name):
    if not is_high_staff(ctx.author):
        await ctx.reply(
            f"{EMOJIS['denied']} You need the BRAX Usage role to use BRAX moderation commands.",
            mention_author=False,
        )
        return False
    if not getattr(ctx.author.guild_permissions, permission_name, False):
        await ctx.reply(
            f"{EMOJIS['denied']} You need the **{permission_name.replace('_', ' ').title()}** permission.",
            mention_author=False,
        )
        return False
    return True


async def send_moderation_result(ctx, action, target, reason, duration=None, color=None):
    await log_brax_action(ctx.guild, target, ctx.author, action, reason, duration)


def moderation_history_embed(member, page):
    entries = moderation_history.get(str(member.id), [])
    total_pages = max(1, (len(entries) + 2) // 3)
    start = page * 3
    selected = list(reversed(entries))[start:start + 3]
    embed = discord.Embed(
        title=f"Moderation Logs • {member}",
        description=f"Showing {len(selected)} of {len(entries)} recorded actions.",
        color=discord.Color.from_rgb(58, 48, 35),
    )
    for index, entry in enumerate(selected, start=start + 1):
        moderator_id = entry.get("moderator_id", "Unknown")
        moderator_name = moderator_label(moderator_id, entry.get("moderator", "Unknown"))
        details = [
            f"Action: {entry.get('action', 'Unknown')}",
            f"Moderator: {moderator_name}",
            f"Moderator ID: {moderator_id}",
            f"Reason: {shorten(entry.get('reason', 'No reason provided'), 500)}",
        ]
        if entry.get("duration"):
            details.append(f"Duration: {entry['duration']}")
        details.append(f"When: {entry.get('timestamp', 'Unknown')}")
        embed.add_field(name=f"Log {index}", value="\n".join(details), inline=False)
    if not entries:
        embed.description = "No moderation actions have been recorded for this member yet."
    embed.set_footer(text=f"BRAX • Page {page + 1}/{total_pages} • 3 logs per page")
    return embed

class ModerationHistoryView(discord.ui.View):
    def __init__(self, member, author_id):
        super().__init__(timeout=180)
        self.member, self.author_id, self.page = member, author_id, 0
        self.total_pages = max(1, (len(moderation_history.get(str(member.id), [])) + 2) // 3)
        self.back_button = discord.ui.Button(style=discord.ButtonStyle.secondary, emoji=discord.PartialEmoji.from_str("<:Backwards:1571304371646632077>"), disabled=True)
        self.forward_button = discord.ui.Button(style=discord.ButtonStyle.secondary, emoji=discord.PartialEmoji.from_str("<:Forward:1571304228255957133>"), disabled=self.total_pages <= 1)
        self.back_button.callback = self.go_back
        self.forward_button.callback = self.go_forward
        self.add_item(self.back_button)
        self.add_item(self.forward_button)
    async def interaction_check(self, interaction):
        if not is_high_staff(interaction.user):
            await interaction.response.send_message("You need the brax usage role to view moderation logs.", ephemeral=True)
            return False
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the person who opened these logs can change pages.", ephemeral=True)
            return False
        return True
    async def update_page(self, interaction):
        self.back_button.disabled = self.page == 0
        self.forward_button.disabled = self.page >= self.total_pages - 1
        await interaction.response.edit_message(embed=moderation_history_embed(self.member, self.page), view=self)
    async def go_back(self, interaction):
        self.page = max(0, self.page - 1)
        await self.update_page(interaction)
    async def go_forward(self, interaction):
        self.page = min(self.total_pages - 1, self.page + 1)
        await self.update_page(interaction)

def moderator_action_entries(moderator_id):
    entries = []
    for target_id, target_entries in moderation_history.items():
        for entry in target_entries:
            if entry.get("moderator_id") == moderator_id:
                item = dict(entry)
                item["target_id"] = target_id
                entries.append(item)
    entries.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return entries

def moderator_action_history_embed(moderator_id, entries, page):
    total_pages = max(1, (len(entries) + 2) // 3)
    selected = entries[page * 3:page * 3 + 3]
    embed = discord.Embed(
        title=f"Your BRAX Action Logs • {moderator_label(moderator_id)}",
        description=f"Showing {len(selected)} of {len(entries)} actions you performed.",
        color=discord.Color.from_rgb(58, 48, 35),
    )
    for index, entry in enumerate(selected, start=page * 3 + 1):
        details = [
            f"Action: {entry.get('action', 'Unknown')}",
            f"Target: {entry.get('target_name', 'Unknown')} (ID: {entry.get('target_id', 'Unknown')})",
            f"Reason: {shorten(entry.get('reason', 'No reason provided'), 500)}",
            f"When: {entry.get('timestamp', 'Unknown')}",
        ]
        if entry.get("duration"):
            details.append(f"Duration: {entry['duration']}")
        embed.add_field(name=f"Action {index}", value="\n".join(details), inline=False)
    if not entries:
        embed.description = "You haven't performed any logged BRAX actions yet."
    embed.set_footer(text=f"BRAX • Your Actions • Page {page + 1}/{total_pages}")
    return embed

class ModeratorActionHistoryView(discord.ui.View):
    def __init__(self, moderator_id, author_id, entries):
        super().__init__(timeout=180)
        self.moderator_id = moderator_id
        self.author_id = author_id
        self.entries = entries
        self.page = 0
        self.total_pages = max(1, (len(entries) + 2) // 3)
        self.back_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            emoji=discord.PartialEmoji.from_str("<:Backwards:1571304371646632077>"),
            disabled=True,
        )
        self.forward_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            emoji=discord.PartialEmoji.from_str("<:Forward:1571304228255957133>"),
            disabled=self.total_pages <= 1,
        )
        self.back_button.callback = self.go_back
        self.forward_button.callback = self.go_forward
        self.add_item(self.back_button)
        self.add_item(self.forward_button)

    async def interaction_check(self, interaction):
        if not is_high_staff(interaction.user):
            await interaction.response.send_message("You need the BRAX Usage role to view these logs.", ephemeral=True)
            return False
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the person who opened these logs can change pages.", ephemeral=True)
            return False
        return True

    async def update_page(self, interaction):
        self.back_button.disabled = self.page == 0
        self.forward_button.disabled = self.page >= self.total_pages - 1
        await interaction.response.edit_message(
            embed=moderator_action_history_embed(self.moderator_id, self.entries, self.page),
            view=self,
        )

    async def go_back(self, interaction):
        self.page = max(0, self.page - 1)
        await self.update_page(interaction)

    async def go_forward(self, interaction):
        self.page = min(self.total_pages - 1, self.page + 1)
        await self.update_page(interaction)


@bot.command(name="mlogs")
async def moderation_logs_command(ctx, member: discord.Member = None):
    if not is_high_staff(ctx.author):
        await ctx.reply("You need the brax usage role to view moderation logs.", mention_author=False)
        return
    if member is None:
        entries = moderator_action_entries(ctx.author.id)
        view = ModeratorActionHistoryView(ctx.author.id, ctx.author.id, entries)
        await ctx.reply(
            embed=moderator_action_history_embed(ctx.author.id, entries, 0),
            view=view,
            mention_author=False,
        )
        return
    view = ModerationHistoryView(member, ctx.author.id)
    await ctx.reply(embed=moderation_history_embed(member, 0), view=view, mention_author=False)

@bot.command(name="mweute")
async def fake_mute_command(ctx, member: discord.Member):
    if not (is_high_staff(ctx.author) or has_lesser_usage(ctx.author)):
        await ctx.reply(f"{EMOJIS['denied']} You need a BRAX Usage role to use Fun commands.", mention_author=False)
        return
    if member.id == ctx.author.id or member.bot:
        await ctx.reply(f"{EMOJIS['denied']} Choose another server member.", mention_author=False)
        return
    await ctx.reply(
        f"🔇 {member.mention} has been **FAKE MUTED**. This is only a joke—no Discord timeout was applied.",
        mention_author=False,
    )
    await log_brax_action(
        ctx.guild, member, ctx.author, "Fake Mute",
        "Fun command: pretend mute only; no real timeout was applied",
    )


@bot.command(name="uwu")
async def uwu_command(ctx, member: discord.Member):
    if not is_uwu_authorized(ctx.author):
        await ctx.reply(f"{EMOJIS['denied']} Only the bot owner, Braxton, and ch33zee can use UWU lock.", mention_author=False)
        return
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.reply(f"{EMOJIS['denied']} You need Manage Messages to use UWU lock.", mention_author=False)
        return
    if not ctx.guild.me.guild_permissions.manage_messages:
        await ctx.reply(f"{EMOJIS['denied']} BRAX needs Manage Messages to replace locked members' original messages.", mention_author=False)
        return
    if member.bot:
        await ctx.reply(f"{EMOJIS['denied']} Choose a human server member.", mention_author=False)
        return
    key = uwu_lock_key(ctx.guild.id, member.id)
    if key in uwu_locks:
        uwu_locks.pop(key, None)
        save_uwu_locks()
        action = "UWU Lock Removed"
        message = f"{EMOJIS['confirmed']} UWU lock removed from {member.mention}."
    else:
        uwu_locks[key] = {"moderator_id": ctx.author.id, "enabled_at": discord.utils.utcnow().isoformat()}
        save_uwu_locks()
        action = "UWU Lock Enabled"
        message = f"✨ {member.mention} is now UWU locked. Their messages will be transformed."
    await ctx.reply(message, mention_author=False)
    await log_brax_action(
        ctx.guild, member, ctx.author, action,
        "Toggled through b!uwu; message relay uses a labelled BRAX UWU webhook",
    )



class UwuListView(discord.ui.View):
    def __init__(self, ctx, locked_members):
        super().__init__(timeout=180)
        self.author_id = ctx.author.id
        self.guild = ctx.guild
        self.selected_member_id = None
        options = [
            discord.SelectOption(label=str(member)[:100], value=str(member.id), description=f"ID: {member.id}")
            for member in locked_members[:25]
        ]
        if options:
            self.member_select = discord.ui.Select(
                placeholder="Choose someone to un-UWU",
                min_values=1,
                max_values=1,
                options=options,
                emoji="🔒",
            )
            self.member_select.callback = self.select_member
            self.add_item(self.member_select)
            self.remove_button = discord.ui.Button(
                label="Un-UWU selected",
                style=discord.ButtonStyle.danger,
                emoji="🔓",
            )
            self.remove_button.callback = self.remove_selected
            self.add_item(self.remove_button)

    async def interaction_check(self, interaction):
        if not is_uwu_authorized(interaction.user):
            await interaction.response.send_message("Only the bot owner, Braxton, and ch33zee can manage UWU locks.", ephemeral=True)
            return False
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the person who opened this list can use its controls.", ephemeral=True)
            return False
        return True

    async def select_member(self, interaction):
        self.selected_member_id = int(self.member_select.values[0])
        member = self.guild.get_member(self.selected_member_id)
        await interaction.response.send_message(
            f"Selected {member.mention if member else self.selected_member_id}. Press Un-UWU selected to remove the lock.",
            ephemeral=True,
        )

    async def remove_selected(self, interaction):
        if self.selected_member_id is None:
            await interaction.response.send_message("Choose a member first.", ephemeral=True)
            return
        key = uwu_lock_key(self.guild.id, self.selected_member_id)
        if key not in uwu_locks:
            await interaction.response.send_message("That member is no longer UWU locked.", ephemeral=True)
            return
        uwu_locks.pop(key, None)
        save_uwu_locks()
        member = self.guild.get_member(self.selected_member_id)
        await interaction.response.send_message(
            f"🔓 UWU lock removed from {member.mention if member else self.selected_member_id}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        if member is not None:
            await log_brax_action(self.guild, member, interaction.user, "UWU Lock Removed", "Removed through b!uwulist")
        self.stop()


@bot.command(name="uwulist")
async def uwu_list_command(ctx):
    if not is_uwu_authorized(ctx.author):
        await ctx.reply(f"{EMOJIS['denied']} Only the bot owner and Braxton can view or manage UWU locks.", mention_author=False)
        return
    prefix = f"{ctx.guild.id}:"
    locked_ids = []
    for key in uwu_locks:
        if key.startswith(prefix):
            try:
                locked_ids.append(int(key.split(":", 1)[1]))
            except ValueError:
                continue
    locked_members = [member for user_id in locked_ids if (member := ctx.guild.get_member(user_id)) is not None]
    lines = [f"🔒 {member.mention} — {member.id}" for member in locked_members]
    embed = discord.Embed(
        title="🔒 Current UWU Locks",
        description="\n".join(lines) if lines else "Nobody is currently UWU locked.",
        color=discord.Color.from_rgb(58, 48, 35),
    )
    embed.set_footer(text=f"{len(locked_members)} locked member(s) • Dropdown manages up to 25 at a time")
    view = UwuListView(ctx, locked_members) if locked_members else None
    await ctx.reply(embed=embed, view=view, mention_author=False)


@bot.command(name="mlog")
async def moderation_log_command(ctx, channel: discord.TextChannel = None):
    if not await moderation_gate(ctx, "manage_guild"):
        return
    channel = channel or ctx.channel
    permissions = channel.permissions_for(ctx.guild.me)
    if not permissions.view_channel or not permissions.send_messages or not permissions.embed_links:
        await ctx.reply(
            f"{EMOJIS['denied']} I need View Channel, Send Messages, and Embed Links in {channel.mention}.",
            mention_author=False,
        )
        return
    mod_log_channels[str(ctx.guild.id)] = channel.id
    save_mod_log_channels()
    await ctx.reply(
        f"{EMOJIS['confirmed']} Moderation logs will now be sent to {channel.mention}.",
        mention_author=False,
    )


@bot.command(name="timeout", aliases=["mute", "tempmute"])
async def timeout_command(ctx, member: discord.Member, duration: str, *, reason: str):
    if not await moderation_gate(ctx, "moderate_members"):
        return
    if member.id == ctx.author.id or member.bot:
        await ctx.reply(f"{EMOJIS['denied']} You can't timeout yourself or a bot.", mention_author=False)
        return
    if ctx.author.id != ctx.guild.owner_id and member.top_role >= ctx.author.top_role:
        await ctx.reply(f"{EMOJIS['denied']} You can't timeout someone with an equal or higher role.", mention_author=False)
        return
    try:
        parsed_duration = parse_timeout_duration(duration)
    except ValueError as error:
        await ctx.reply(f"{EMOJIS['denied']} {error}", mention_author=False)
        return
    try:
        await member.timeout(discord.utils.utcnow() + parsed_duration, reason=f"{ctx.author}: {reason}")
    except discord.Forbidden:
        await ctx.reply(f"{EMOJIS['denied']} I can't timeout that member. Check my Moderate Members permission and role position.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Timeout failed: {error}", mention_author=False)
        return
    await ctx.reply(f"{EMOJIS['confirmed']} {member.mention} was timed out for **{duration}**. Reason: {reason}", mention_author=False)
    await send_moderation_result(ctx, "Member Timed Out", member, reason, duration)


@bot.command(name="untimeout", aliases=["unmute", "removetimeout"])
async def untimeout_command(ctx, member: discord.Member, *, reason: str = "Timeout removed"):
    if not await moderation_gate(ctx, "moderate_members"):
        return
    if ctx.author.id != ctx.guild.owner_id and member.top_role >= ctx.author.top_role:
        await ctx.reply(f"{EMOJIS['denied']} You can't remove a timeout from someone with an equal or higher role.", mention_author=False)
        return
    try:
        await member.timeout(None, reason=f"{ctx.author}: {reason}")
    except discord.Forbidden:
        await ctx.reply(f"{EMOJIS['denied']} I can't remove that timeout. Check my Moderate Members permission and role position.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Couldn't remove timeout: {error}", mention_author=False)
        return
    await ctx.reply(f"{EMOJIS['confirmed']} Removed the timeout from {member.mention}. Reason: {reason}", mention_author=False)
    await send_moderation_result(ctx, "Timeout Removed", member, reason)


@bot.command(name="kick")
async def kick_command(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not await moderation_gate(ctx, "kick_members"):
        return
    if member.id == ctx.author.id or member.bot:
        await ctx.reply(f"{EMOJIS['denied']} You can't kick yourself or a bot.", mention_author=False)
        return
    if ctx.author.id != ctx.guild.owner_id and member.top_role >= ctx.author.top_role:
        await ctx.reply(f"{EMOJIS['denied']} You can't kick someone with an equal or higher role.", mention_author=False)
        return
    try:
        await member.kick(reason=f"{ctx.author}: {reason}")
    except discord.Forbidden:
        await ctx.reply(f"{EMOJIS['denied']} I can't kick that member. Check my Kick Members permission and role position.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Kick failed: {error}", mention_author=False)
        return
    await ctx.reply(f"{EMOJIS['confirmed']} Kicked **{member}**. Reason: {reason}", mention_author=False)
    await send_moderation_result(ctx, "Member Kicked", member, reason)


@bot.command(name="ban")
async def ban_command(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not await moderation_gate(ctx, "ban_members"):
        return
    if member.id == ctx.author.id or member.bot:
        await ctx.reply(f"{EMOJIS['denied']} You can't ban yourself or a bot.", mention_author=False)
        return
    if ctx.author.id != ctx.guild.owner_id and member.top_role >= ctx.author.top_role:
        await ctx.reply(f"{EMOJIS['denied']} You can't ban someone with an equal or higher role.", mention_author=False)
        return
    try:
        await ctx.guild.ban(member, reason=f"{ctx.author}: {reason}", delete_message_seconds=0)
    except discord.Forbidden:
        await ctx.reply(f"{EMOJIS['denied']} I can't ban that member. Check my Ban Members permission and role position.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Ban failed: {error}", mention_author=False)
        return
    await ctx.reply(f"{EMOJIS['confirmed']} Banned **{member}**. Reason: {reason}", mention_author=False)
    await send_moderation_result(ctx, "Member Banned", member, reason)


@bot.command(name="unban")
async def unban_command(ctx, user_id: int, *, reason: str = "Ban removed"):
    if not await moderation_gate(ctx, "ban_members"):
        return
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=f"{ctx.author}: {reason}")
    except discord.NotFound:
        await ctx.reply(f"{EMOJIS['denied']} That user isn't banned (or the ID is invalid).", mention_author=False)
        return
    except discord.Forbidden:
        await ctx.reply(f"{EMOJIS['denied']} I need Ban Members permission to unban users.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Unban failed: {error}", mention_author=False)
        return
    await ctx.reply(f"{EMOJIS['confirmed']} Unbanned **{user}**. Reason: {reason}", mention_author=False)
    await send_moderation_result(ctx, "Member Unbanned", user, reason)


@bot.command(name="roleadd", aliases=["addrole"])
async def role_add_command(ctx, member: discord.Member, role: discord.Role, *, reason: str = "Role added by moderator"):
    if not await moderation_gate(ctx, "manage_roles"):
        return
    if role.is_default() or role.managed or role >= ctx.guild.me.top_role:
        await ctx.reply(f"{EMOJIS['denied']} I can't assign that role. Check whether it's managed or above my highest role.", mention_author=False)
        return
    if ctx.author.id != ctx.guild.owner_id and role >= ctx.author.top_role:
        await ctx.reply(f"{EMOJIS['denied']} You can't assign a role equal to or above your highest role.", mention_author=False)
        return
    try:
        await member.add_roles(role, reason=f"Role added by {ctx.author}: {reason}")
    except discord.Forbidden:
        await ctx.reply(f"{EMOJIS['denied']} I can't assign that role. Check Manage Roles and role hierarchy.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Role add failed: {error}", mention_author=False)
        return
    await ctx.reply(f"{EMOJIS['confirmed']} Added {role.mention} to {member.mention}. Reason: {reason}", mention_author=False)
    await send_moderation_result(ctx, "Role Added", member, reason)
    

@bot.command(name="roleremove", aliases=["removerole"])
async def role_remove_command(ctx, member: discord.Member, role: discord.Role, *, reason: str = "Role removed by moderator"):
    if not await moderation_gate(ctx, "manage_roles"):
        return
    if role.is_default() or role.managed or role >= ctx.guild.me.top_role:
        await ctx.reply(f"{EMOJIS['denied']} I can't remove that role. Check whether it's managed or above my highest role.", mention_author=False)
        return
    if ctx.author.id != ctx.guild.owner_id and role >= ctx.author.top_role:
        await ctx.reply(f"{EMOJIS['denied']} You can't remove a role equal to or above your highest role.", mention_author=False)
        return
    if role not in member.roles:
        await ctx.reply(f"{EMOJIS['denied']} {member.mention} doesn't have {role.mention}.", mention_author=False)
        return
    try:
        await member.remove_roles(role, reason=f"Role removed by {ctx.author}: {reason}")
    except discord.Forbidden:
        await ctx.reply(f"{EMOJIS['denied']} I can't remove that role. Check Manage Roles and role hierarchy.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Role removal failed: {error}", mention_author=False)
        return
    await ctx.reply(f"{EMOJIS['confirmed']} Removed {role.mention} from {member.mention}. Reason: {reason}", mention_author=False)
    await send_moderation_result(ctx, "Role Removed", member, reason)


@bot.command(name="usageadd")
async def usage_add_command(ctx, member: discord.Member):
    if ctx.author.id not in USAGE_ROLE_GRANTER_IDS:
        await ctx.reply("Only Braxton and kaydnn can grant the brax usage role.", mention_author=False)
        return
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.reply("You need the **Manage Roles** permission to grant brax usage.", mention_author=False)
        return
    role = ctx.guild.get_role(BRAX_USAGE_ROLE_ID)
    if role is None:
        await ctx.reply("The brax usage role could not be found. Check the configured role ID.", mention_author=False)
        return
    if role >= ctx.guild.me.top_role:
        await ctx.reply("I can't assign brax usage because the role is above or equal to my highest role. Move BRAX above it.", mention_author=False)
        return
    if role in member.roles:
        await ctx.reply(f"{member.mention} already has the brax usage role.", mention_author=False)
        return
    try:
        await member.add_roles(role, reason=f"BRAX Usage access granted by {ctx.author}")
    except discord.Forbidden:
        await ctx.reply("I can't grant the brax usage role. Check my Manage Roles permission and role hierarchy.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"Couldn't grant the brax usage role: {error}", mention_author=False)
        return
    await ctx.reply(
        f"{EMOJIS['confirmed']} {ctx.author.mention} gave {member.mention} <@&{BRAX_USAGE_ROLE_ID}>.",
        mention_author=False,
        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
    )
    await log_brax_action(
        ctx.guild, member, ctx.author, "BRAX Usage Granted",
        "BRAX Usage access granted with b!usageadd",
    )


@bot.command(name="lusageadd")
async def lesser_usage_add_command(ctx, member: discord.Member):
    if not is_high_staff(ctx.author):
        await ctx.reply("You need the BRAX Usage role to give Lesser B Usage.", mention_author=False)
        return
    role = ctx.guild.get_role(LESSER_BRAX_USAGE_ROLE_ID)
    if role is None:
        await ctx.reply("The Lesser B Usage role could not be found. Check the configured role ID.", mention_author=False)
        return
    if role >= ctx.guild.me.top_role:
        await ctx.reply("I can't assign Lesser B Usage because the role is above or equal to my highest role. Move BRAX above it.", mention_author=False)
        return
    if role in member.roles:
        await ctx.reply(f"{member.mention} already has the Lesser B Usage role.", mention_author=False)
        return
    try:
        await member.add_roles(role, reason=f"Lesser B Usage granted by {ctx.author} with b!lusageadd")
    except discord.Forbidden:
        await ctx.reply("I can't grant Lesser B Usage. Check my Manage Roles permission and role hierarchy.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"Couldn't grant Lesser B Usage: {error}", mention_author=False)
        return
    await ctx.reply(
        f"{EMOJIS['confirmed']} {ctx.author.mention} gave {member.mention} <@&{LESSER_BRAX_USAGE_ROLE_ID}>.",
        mention_author=False,
        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
    )
    await log_brax_action(
        ctx.guild, member, ctx.author, "Lesser B Usage Granted",
        "Lesser B Usage access granted with b!lusageadd",
    )


@bot.command(name="ticketpanel")
async def ticket_panel_command(ctx):
    if not is_high_staff(ctx.author):
        await ctx.reply("You need the BRAX Usage role to use BRAX commands.", mention_author=False)
        return
    if not ctx.author.guild_permissions.manage_guild:
        await ctx.reply("You also need the **Manage Server** permission.", mention_author=False)
        return
    channel = ctx.guild.get_channel(TICKETS_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel):
        await ctx.reply("The configured ticket panel channel wasn't found.", mention_author=False)
        return
    embed = discord.Embed(
        title="Open a ticket",
        description="Click the button below to open a ticket so we can see what you need",
        color=discord.Color.from_rgb(58, 48, 35),
    )
    embed.set_footer(text="Braxton Lwk had this idea")
    try:
        await channel.send(embed=embed, view=TicketPanelView())
        await ctx.reply(f"Ticket panel posted in {channel.mention}.", mention_author=False)
    except discord.Forbidden:
        await ctx.reply("I need View Channel, Send Messages, and Embed Links there.", mention_author=False)


# BRAX Coins economy and fun games. Coins are virtual server points only.
SHOP_ITEMS = {
    "lesser": (50, "Lesser BRAX Usage"),
    "usage": (7500, "BRAX Usage (staff review)"),
    "unblacklist": (40, "regular blacklist removal"),
    "divine": (450, "Divine punishment removal (staff review)"),
    "customrole": (500, "custom role"),
}

@bot.command(name="balance", aliases=["bal", "coins"])
async def balance_command(ctx, member: discord.Member = None):
    member = member or ctx.author
    key = economy_key(ctx.guild.id, member.id)
    count = int(economy_data.setdefault("message_counts", {}).get(key, 0))
    embed = discord.Embed(
        title=f"{BRAX_COINS_EMOJI} {member.display_name}'s Wallet",
        description=f"Balance: **{coin_balance(ctx.guild.id, member.id)}** BRAX Coins\nMessage progress: **{count % 10}/10** toward your next coin",
        color=discord.Color.from_rgb(58, 48, 35),
    )
    await ctx.reply(embed=embed, mention_author=False)

@bot.command(name="shop", aliases=["store"])
async def shop_command(ctx):
    embed = discord.Embed(
        title=f"{BRAX_COINS_EMOJI} BRAX Store",
        description=(
            "Earn **1 BRAX Coin every 10 messages**. Coins are virtual server points.\n\n"
            "**50** — Lesser BRAX Usage: b!buy lesser\n"
            "**7,500** — BRAX Usage (staff review): b!buy usage\n"
            "**40** — Remove one regular blacklist: b!buy unblacklist\n"
            "**450** — Divine punishment removal (staff review): b!buy divine\n"
            "**500** — Custom role: b!buy customrole\n\n"
            "Check your wallet with b!balance."
        ),
        color=discord.Color.from_rgb(58, 48, 35),
    )
    await ctx.reply(embed=embed, mention_author=False)

@bot.command(name="buy")
async def buy_command(ctx, item: str, *, details: str = ""):
    item = item.casefold().replace("-", "").replace("_", "")
    aliases = {"lesserusage": "lesser", "braxusage": "usage", "blacklist": "unblacklist", "divinepunishment": "divine", "custom": "customrole", "role": "customrole"}
    item = aliases.get(item, item)
    if item not in SHOP_ITEMS:
        await ctx.reply("Unknown item. Use b!shop.", mention_author=False)
        return
    price, label = SHOP_ITEMS[item]
    if coin_balance(ctx.guild.id, ctx.author.id) < price:
        await ctx.reply(f"You need {price} {BRAX_COINS_EMOJI}; your balance is {coin_balance(ctx.guild.id, ctx.author.id)}.", mention_author=False)
        return

    if item == "lesser":
        role = ctx.guild.get_role(LESSER_BRAX_USAGE_ROLE_ID)
        if role is None or role >= ctx.guild.me.top_role or role in ctx.author.roles:
            await ctx.reply("The role is unavailable, above my role, or you already have it. No coins spent.", mention_author=False)
            return
        if ctx.author.id in lesser_usage_state.get("blocked_users", []):
            await ctx.reply("Your account is blocked from receiving Lesser BRAX Usage.", mention_author=False)
            return
        spend_coins(ctx.guild.id, ctx.author.id, price)
        try:
            await ctx.author.add_roles(role, reason="Purchased with BRAX Coins")
        except discord.HTTPException:
            add_coins(ctx.guild.id, ctx.author.id, price)
            await ctx.reply("Role assignment failed; your coins were returned.", mention_author=False)
            return
        await ctx.reply(f"Purchased {role.mention} for {price} {BRAX_COINS_EMOJI}.", mention_author=False)
        return

    if item == "customrole":
        name = details.strip()
        if not name:
            await ctx.reply("What should the role be called? Reply within 60 seconds.", mention_author=False)
            try:
                answer = await bot.wait_for("message", timeout=60, check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id)
                name = answer.content.strip()
            except asyncio.TimeoutError:
                await ctx.reply("Timed out. No coins were spent.", mention_author=False)
                return
        name = shorten(name, 80).strip()
        if not name or not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.reply("Invalid name or I need Manage Roles. No coins spent.", mention_author=False)
            return
        spend_coins(ctx.guild.id, ctx.author.id, price)
        try:
            role = await ctx.guild.create_role(name=name, reason=f"BRAX Coins custom role for {ctx.author}")
            await ctx.author.add_roles(role, reason="Custom role purchase")
        except discord.HTTPException:
            add_coins(ctx.guild.id, ctx.author.id, price)
            await ctx.reply("I couldn't create or assign that role. Your coins were returned.", mention_author=False)
            return
        await ctx.reply(f"Created and assigned {role.mention} for {price} {BRAX_COINS_EMOJI}.", mention_author=False)
        return

    if item == "unblacklist":
        eligible = [(name, ctx.guild.get_role(role_id)) for name, role_id in BLACKLIST_ROLES.items() if name != "Divine punishment"]
        eligible = [(name, role) for name, role in eligible if role is not None and role in ctx.author.roles]
        if not eligible:
            await ctx.reply("You don't have a regular blacklist role to remove.", mention_author=False)
            return
        if details:
            eligible = [(name, role) for name, role in eligible if name.casefold() == details.casefold()]
        if len(eligible) != 1:
            await ctx.reply("Specify which blacklist to remove: " + ", ".join(name for name, role in eligible), mention_author=False)
            return
        name, role = eligible[0]
        if role >= ctx.guild.me.top_role:
            await ctx.reply("That role is above my highest role. Ask staff.", mention_author=False)
            return
        spend_coins(ctx.guild.id, ctx.author.id, price)
        try:
            await ctx.author.remove_roles(role, reason="Purchased removal with BRAX Coins")
        except discord.HTTPException:
            add_coins(ctx.guild.id, ctx.author.id, price)
            await ctx.reply("Removal failed; your coins were returned.", mention_author=False)
            return
        await ctx.reply(f"Removed {name} for {price} {BRAX_COINS_EMOJI}.", mention_author=False)
        return

    if item == "divine":
        role = ctx.guild.get_role(BLACKLIST_ROLES["Divine punishment"])
        if role is None or role not in ctx.author.roles:
            await ctx.reply("You don't have Divine punishment.", mention_author=False)
            return
    else:
        role = ctx.guild.get_role(BRAX_USAGE_ROLE_ID)
        if role is None or role in ctx.author.roles:
            await ctx.reply("You already have BRAX Usage or the role is missing.", mention_author=False)
            return
    spend_coins(ctx.guild.id, ctx.author.id, price)
    staff = "<@1521469840970350632> <@1511412885040009309>"
    await ctx.channel.send(
        f"{staff} — {ctx.author.mention} bought a request for **{label}** ({price} {BRAX_COINS_EMOJI}). Please review it.",
        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
    )
    await ctx.reply("Your request was sent to staff. Coins are held pending review.", mention_author=False)

@bot.command(name="coinadd")
async def coinadd_command(ctx, member: discord.Member, amount: int):
    # Only Braxton's Discord account may use this economy-admin command.
    if ctx.author.id != 1511412885040009309:
        await ctx.reply("You aren't authorized to use this command.", mention_author=False)
        return
    if amount <= 0:
        await ctx.reply("Amount must be a positive whole number.", mention_author=False)
        return
    add_coins(ctx.guild.id, member.id, amount)
    new_balance = coin_balance(ctx.guild.id, member.id)
    await ctx.reply(
        f"{EMOJIS['confirmed']} Added **{amount:,}** {BRAX_COINS_EMOJI} to {member.mention}. "
        f"Their new balance is **{new_balance:,}** {BRAX_COINS_EMOJI}.",
        mention_author=False,
        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
    )

@bot.command(name="coinflip", aliases=["flip"])
async def coinflip_command(ctx, side: str, amount: int):
    side = side.casefold()
    if side not in {"heads", "tails", "h", "t"} or not 1 <= amount <= MAX_GAMBLE_BET:
        await ctx.reply(f"Use b!coinflip heads 10 or b!coinflip tails 10 (1–{MAX_GAMBLE_BET} coins). {COINFLIP_EMOJI}", mention_author=False)
        return
    if not spend_coins(ctx.guild.id, ctx.author.id, amount):
        await ctx.reply("Not enough BRAX Coins.", mention_author=False)
        return
    result = random.choice(["heads", "tails"])
    won = side[0] == result[0]
    if won:
        add_coins(ctx.guild.id, ctx.author.id, amount * 2)
    await ctx.reply(f"{COINFLIP_EMOJI} **{result.title()}!** " + (f"You won {amount} coins." if won else f"You lost {amount} coins.") + f" Balance: {coin_balance(ctx.guild.id, ctx.author.id)} {BRAX_COINS_EMOJI}", mention_author=False)

@bot.command(name="gamble")
async def gamble_command(ctx, amount: int, multiplier: int = 2):
    if amount < 1 or multiplier < 2 or multiplier > MAX_GAMBLE_MULTIPLIER:
        await ctx.reply(f"Use b!gamble <amount> <multiplier>. Multipliers range from 2x to {MAX_GAMBLE_MULTIPLIER}x. Example: b!gamble 100 15", mention_author=False)
        return
    balance = coin_balance(ctx.guild.id, ctx.author.id)
    if multiplier <= 10 and balance < amount:
        await ctx.reply(f"Not enough BRAX Coins. Your balance is {balance} {BRAX_COINS_EMOJI}. Bets above 10x can put you in debt.", mention_author=False)
        return
    # Higher multipliers are riskier. A win chance of 1/multiplier keeps the payout odds aligned.
    won = random.randrange(multiplier) == 0
    set_coin_balance(ctx.guild.id, ctx.author.id, balance - amount)
    if won:
        add_coins(ctx.guild.id, ctx.author.id, amount * multiplier)
    new_balance = coin_balance(ctx.guild.id, ctx.author.id)
    debt_note = " You are now in debt." if new_balance < 0 else ""
    await ctx.reply(
        (f"🎉 You hit **{multiplier}x**!" if won else f"💀 You lost the **{amount}** coin bet at **{multiplier}x**.")
        + f" Balance: **{new_balance}** {BRAX_COINS_EMOJI}.{debt_note}",
        mention_author=False,
    )

@bot.command(name="coinlb", aliases=["coinleaderboard", "leaderboard", "richlist"])
async def coin_leaderboard_command(ctx):
    prefix = f"{ctx.guild.id}:"
    entries = []
    for key, balance in economy_data.setdefault("balances", {}).items():
        if key.startswith(prefix):
            try:
                user_id = int(key.split(":", 1)[1])
            except (ValueError, IndexError):
                continue
            entries.append((user_id, int(balance)))
    entries.sort(key=lambda item: item[1], reverse=True)
    entries = entries[:10]
    if not entries:
        await ctx.reply("Nobody has earned any BRAX Coins yet.", mention_author=False)
        return
    rows = []
    for rank, (user_id, balance) in enumerate(entries, start=1):
        member = ctx.guild.get_member(user_id)
        name = member.display_name if member else f"User {user_id}"
        rows.append(f"**{rank}.** {name} — **{balance:,}** {BRAX_COINS_EMOJI}")
    embed = discord.Embed(
        title=f"{BRAX_COINS_EMOJI} BRAX Coin Leaderboard",
        description="\n".join(rows),
        color=discord.Color.from_rgb(58, 48, 35),
    )
    await ctx.reply(embed=embed, mention_author=False)

STOCK_START_PRICES = {"BRAX": 25, "WISP": 15, "UWU": 10, "TICKET": 40}
def stock_prices():
    prices = economy_data.setdefault("market_prices", dict(STOCK_START_PRICES))
    for symbol, base in STOCK_START_PRICES.items():
        prices.setdefault(symbol, base)
    return prices

def move_stock_market():
    prices = stock_prices()
    for symbol in prices:
        prices[symbol] = max(2, int(prices[symbol] * random.uniform(0.92, 1.09)))
    save_economy()

@bot.command(name="stocks", aliases=["stock"])
async def stocks_command(ctx):
    move_stock_market()
    prices = stock_prices()
    key = economy_key(ctx.guild.id, ctx.author.id)
    holdings = economy_data.setdefault("stocks", {}).get(key, {})
    quotes = "\n".join(f"**{symbol}** — {price} {BRAX_COINS_EMOJI}" for symbol, price in prices.items())
    portfolio = ", ".join(f"{symbol} × {count}" for symbol, count in holdings.items() if count) or "No shares yet."
    embed = discord.Embed(title="📈 BRAX Market", description=f"{quotes}\n\n**Your shares:** {portfolio}\nBuy: b!stockbuy BRAX 2\nSell: b!stocksell BRAX 1", color=discord.Color.from_rgb(58, 48, 35))
    await ctx.reply(embed=embed, mention_author=False)

@bot.command(name="stockbuy")
async def stockbuy_command(ctx, symbol: str, shares: int):
    symbol = symbol.upper()
    prices = stock_prices()
    if symbol not in prices or not 1 <= shares <= 100:
        await ctx.reply("Choose BRAX, WISP, UWU or TICKET, and buy 1–100 shares.", mention_author=False)
        return
    move_stock_market()
    price = stock_prices()[symbol]
    cost = price * shares
    if not spend_coins(ctx.guild.id, ctx.author.id, cost):
        await ctx.reply(f"You need {cost} {BRAX_COINS_EMOJI} to buy those shares.", mention_author=False)
        return
    key = economy_key(ctx.guild.id, ctx.author.id)
    portfolio = economy_data.setdefault("stocks", {}).setdefault(key, {})
    portfolio[symbol] = int(portfolio.get(symbol, 0)) + shares
    save_economy()
    await ctx.reply(f"Bought {shares} {symbol} shares for {cost} {BRAX_COINS_EMOJI}.", mention_author=False)

@bot.command(name="stocksell")
async def stocksell_command(ctx, symbol: str, shares: int):
    symbol = symbol.upper()
    prices = stock_prices()
    key = economy_key(ctx.guild.id, ctx.author.id)
    portfolio = economy_data.setdefault("stocks", {}).setdefault(key, {})
    if symbol not in prices or shares < 1 or int(portfolio.get(symbol, 0)) < shares:
        await ctx.reply("You don't own that many shares. Check b!stocks.", mention_author=False)
        return
    move_stock_market()
    price = stock_prices()[symbol]
    portfolio[symbol] = int(portfolio.get(symbol, 0)) - shares
    proceeds = price * shares
    add_coins(ctx.guild.id, ctx.author.id, proceeds)
    save_economy()
    await ctx.reply(f"Sold {shares} {symbol} shares for {proceeds} {BRAX_COINS_EMOJI}.", mention_author=False)




@bot.command(name="mine")
async def mine_command(ctx):
    key=economy_key(ctx.guild.id,ctx.author.id); now=time.time()
    cooldowns=economy_data.setdefault("mine_cooldowns",{}); ready=float(cooldowns.get(key,0))
    if now<ready:
        await ctx.reply(f"Your digging tools need a moment. Try again in **{max(1,int(ready-now+0.999))}s**.",mention_author=False); return
    cooldowns[key]=now+MINING_COOLDOWN_SECONDS
    found=[]
    for _ in range(random.choices([1,2,3],weights=[65,28,7],k=1)[0]):
        name,_,_=random.choices(MINING_LOOT,weights=[entry[2] for entry in MINING_LOOT],k=1)[0]
        found.append(name); add_item(ctx.guild.id,ctx.author.id,name,1)
    save_economy()
    await ctx.reply("⛏️ **You finished digging!**\n"+"\n".join(f"• **{name}**" for name in found)+"\n\nCheck finds with b!inventory. Sell with b!sell <item>.",mention_author=False)

@bot.command(name="inventory",aliases=["inv","backpack","bag"])
async def inventory_command(ctx,member:discord.Member=None):
    member=member or ctx.author; inventory=get_inventory(ctx.guild.id,member.id)
    entries=sorted([(name,int(amount)) for name,amount in inventory.items() if int(amount)>0],key=lambda entry:entry[0].casefold())
    description="\n".join(f"**{name}** × {amount}" for name,amount in entries) if entries else "No items yet. Use b!mine to start digging."
    embed=discord.Embed(title=f"🎒 {member.display_name}'s Inventory",description=shorten(description,4000),color=discord.Color.from_rgb(58,48,35))
    embed.set_footer(text=f"{len(entries)} different item types • Sell with b!sell <item>")
    await ctx.reply(embed=embed,mention_author=False)

@bot.command(name="sell")
async def sell_command(ctx,*,item_and_amount:str):
    parts=item_and_amount.strip().rsplit(" ",1); amount=None; item_text=item_and_amount.strip()
    if len(parts)==2 and parts[1].isdigit(): item_text,amount=parts[0],int(parts[1])
    item=normalize_mining_item(item_text)
    if item is None:
        await ctx.reply("I don't recognize that item. Check b!inventory for exact names.",mention_author=False); return
    inventory=get_inventory(ctx.guild.id,ctx.author.id); owned=int(inventory.get(item,0)); quantity=owned if amount is None else amount
    if quantity<1 or owned<quantity:
        await ctx.reply(f"You only have **{owned} {item}**.",mention_author=False); return
    inventory[item]=owned-quantity
    if inventory[item]<=0: inventory.pop(item,None)
    proceeds=MINING_ITEM_VALUES[item]*quantity; add_coins(ctx.guild.id,ctx.author.id,proceeds); save_economy()
    await ctx.reply(f"💰 Sold **{quantity} {item}** for **{proceeds:,}** {BRAX_COINS_EMOJI}. New balance: **{coin_balance(ctx.guild.id,ctx.author.id):,}**.",mention_author=False)

@bot.command(name="trade")
async def trade_command(ctx,member:discord.Member):
    if member.bot or member.id==ctx.author.id:
        await ctx.reply("Choose another human member to trade with.",mention_author=False); return
    if not ctx.guild.me.guild_permissions.manage_channels:
        await ctx.reply("I need Manage Channels permission to open a private trade channel.",mention_author=False); return
    for active in economy_data.setdefault("trades",{}).values():
        if ctx.author.id in trade_member_ids(active) or member.id in trade_member_ids(active):
            await ctx.reply("One of you already has an active trade. Finish or cancel it first.",mention_author=False); return
    category=ctx.guild.get_channel(TRADE_CATEGORY_ID)
    if not isinstance(category,discord.CategoryChannel):
        await ctx.reply("I couldn't find the configured trade category. Check the category ID.",mention_author=False); return
    overwrites={
        ctx.guild.default_role:discord.PermissionOverwrite(view_channel=False),
        ctx.author:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True),
        member:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True),
        ctx.guild.me:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True,manage_channels=True),
    }
    for role in ctx.guild.roles:
        if role != ctx.guild.default_role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=False)
    try:
        channel=await ctx.guild.create_text_channel(name=f"trade-{ctx.author.name[:12]}-{member.name[:12]}".lower(),category=category,overwrites=overwrites,topic=f"Private BRAX trade between {ctx.author.id} and {member.id}",reason="BRAX player trade")
    except discord.HTTPException as error:
        print(f"BRAX: Could not create trade channel: {error}")
        await ctx.reply("I couldn't create the trade channel. Check Manage Channels permission and category access.",mention_author=False); return
    economy_data.setdefault("trades",{})[str(channel.id)]={
        "guild_id":ctx.guild.id,"channel_id":channel.id,"user_ids":[ctx.author.id,member.id],
        "offers":{str(ctx.author.id):{"coins":0,"items":{}},str(member.id):{"coins":0,"items":{}}},"confirmed":[],
    }
    save_economy()
    await channel.send(
        f"{ctx.author.mention} {member.mention} — your private trade is open.\n\n"
        "b!offercoins <amount> — Add BRAX Coins to your offer.\n"
        "b!offeritem <amount> <item name> — Add items, e.g. b!offeritem 2 Scrap Metal.\n"
        "b!tradeconfirm — Lock your offer. Both people must confirm to complete.\n"
        "b!tradecancel — Cancel and return all offered items and coins.\n\n"
        "Check b!inventory and b!balance. Offers are held until completion or cancellation.",
        allowed_mentions=discord.AllowedMentions(users=True,roles=False,everyone=False))
    await ctx.reply(f"Created your private trade channel: {channel.mention}",mention_author=False)

@bot.command(name="offercoins")
async def trade_offer_coins_command(ctx,amount:int):
    trade=active_trade_for_channel(ctx.channel.id)
    if trade is None or ctx.author.id not in trade_member_ids(trade):
        await ctx.reply("Use this command inside your active trade channel.",mention_author=False); return
    if amount<0:
        await ctx.reply("Offer amount must be zero or more.",mention_author=False); return
    offer=trade_offer_for(trade,ctx.author.id); old=int(offer.get("coins",0))
    if old: add_coins(ctx.guild.id,ctx.author.id,old)
    if amount and not spend_coins(ctx.guild.id,ctx.author.id,amount):
        if old: spend_coins(ctx.guild.id,ctx.author.id,old)
        await ctx.reply("You don't have enough BRAX Coins for that offer.",mention_author=False); return
    offer["coins"]=amount; trade["confirmed"]=[]; save_economy()
    await ctx.reply(f"Your coin offer is now **{amount:,}** {BRAX_COINS_EMOJI}. Both traders must confirm again.",mention_author=False)

@bot.command(name="offeritem")
async def trade_offer_item_command(ctx,amount:int,*,item_name:str):
    trade=active_trade_for_channel(ctx.channel.id)
    if trade is None or ctx.author.id not in trade_member_ids(trade):
        await ctx.reply("Use this command inside your active trade channel.",mention_author=False); return
    item=normalize_mining_item(item_name)
    if item is None or amount<1:
        await ctx.reply("Use b!offeritem <amount> <item name> with an item from b!inventory.",mention_author=False); return
    inventory=get_inventory(ctx.guild.id,ctx.author.id); offer=trade_offer_for(trade,ctx.author.id)
    current=int(offer.setdefault("items",{}).get(item,0))
    if current:
        add_item(ctx.guild.id,ctx.author.id,item,current); inventory=get_inventory(ctx.guild.id,ctx.author.id)
        offer["items"].pop(item,None)
    if int(inventory.get(item,0))<amount:
        await ctx.reply(f"You don't have **{amount} {item}** available.",mention_author=False); return
    inventory[item]=int(inventory.get(item,0))-amount
    if inventory[item]<=0: inventory.pop(item,None)
    offer["items"][item]=amount; trade["confirmed"]=[]; save_economy()
    await ctx.reply(f"Added **{amount} {item}** to your offer. Both traders must confirm again.",mention_author=False)

@bot.command(name="tradeconfirm")
async def trade_confirm_command(ctx):
    trade=active_trade_for_channel(ctx.channel.id)
    if trade is None or ctx.author.id not in trade_member_ids(trade):
        await ctx.reply("This isn't one of your active trade channels.",mention_author=False); return
    confirmed=trade.setdefault("confirmed",[])
    if ctx.author.id not in confirmed: confirmed.append(ctx.author.id)
    save_economy()
    if any(uid not in confirmed for uid in trade_member_ids(trade)):
        await ctx.reply("Your offer is locked. Waiting for the other trader to use b!tradeconfirm.",mention_author=False); return
    guild_id=ctx.guild.id; ids=trade_member_ids(trade)
    offer_a,offer_b=trade_offer_for(trade,ids[0]),trade_offer_for(trade,ids[1])
    add_coins(guild_id,ids[0],int(offer_b.get("coins",0))); add_coins(guild_id,ids[1],int(offer_a.get("coins",0)))
    for item,count in offer_b.get("items",{}).items(): add_item(guild_id,ids[0],item,int(count))
    for item,count in offer_a.get("items",{}).items(): add_item(guild_id,ids[1],item,int(count))
    economy_data.setdefault("trades",{}).pop(str(ctx.channel.id),None); save_economy()
    await ctx.send("✅ **TRADE COMPLETE!** Both offers have been exchanged. This channel will now close.")
    await asyncio.sleep(5)
    try: await ctx.channel.delete(reason="BRAX trade completed")
    except discord.HTTPException as error: print(f"BRAX: Could not delete completed trade channel: {error}")

@bot.command(name="tradecancel")
async def trade_cancel_command(ctx):
    trade=active_trade_for_channel(ctx.channel.id)
    if trade is None or ctx.author.id not in trade_member_ids(trade):
        await ctx.reply("This isn't one of your active trade channels.",mention_author=False); return
    refund_trade(ctx.guild.id,trade); economy_data.setdefault("trades",{}).pop(str(ctx.channel.id),None); save_economy()
    await ctx.send("Trade cancelled. All offered BRAX Coins and items have been returned. This channel will close.")
    await asyncio.sleep(5)
    try: await ctx.channel.delete(reason="BRAX trade cancelled")
    except discord.HTTPException as error: print(f"BRAX: Could not delete cancelled trade channel: {error}")


HELP_PAGES = [
    {
        "title": "BRAX • Command Access",
        "description": (
            "BRAX commands use the **b!** prefix. All BRAX staff commands are restricted "
            "to members with <@&1571309152440025190> (**brax usage**). Old staff-role names "
            "and IDs no longer grant command access.\n\n"
            "**Special authorization**\n"
            "The seven people listed below are specifically allowed to assign or remove "
            "the Divine punishment role:\n"
            "• noobidbody — `781537035428429866`\n"
            "• eyeless — `942862192867409941`\n"
            "• <:Brax:1571324199765549219> Braxton — `1521469840970350632`\n"
            "• <:Kaydn:1571324228127690954> kaydnn — `1511412885040009309`\n"
            "• theimpostorsyndrome/testo — `1369381936283389983`\n"
            "• bob061344/British guy — `1276932593790484636`\n"
            "• User ID `718619652187750411`\n\n"
            "Members with brax usage can use regular blacklist controls but cannot use "
            "Divine punishment unless their user ID is separately on the authorization list. "
            "The seven authorized accounts can open the blacklist menu for Divine punishment only. "
            "Only Braxton and kaydnn can grant the brax usage role with `b!usageadd @user`."
        ),
        "footer": "BRAX • Access Information",
    },
    {
        "title": "<a:Tools:1571303064256909482> Server Tools",
        "description": (
            "`b!usageadd @user` — Give the brax usage role (Braxton and kaydnn only).\n"
            "`b!lusageadd @user` — Give the Lesser B Usage role (any BRAX Usage member).\n"
            "`b!ticketpanel` — Post the ticket panel.\n"
            "`b!blacklist @user` — Open the blacklist menu.\n"
            "`b!help` — Open this interactive help menu.\n"
            "`/help` — Show help privately."
        ),
        "footer": "BRAX • Server Tools",
    },
    {
        "title": "<:Moderation:1571302568070611045> Moderation",
        "description": (
            "`b!timeout @user 10m reason` — Timeout a member. Aliases: `b!mute`, `b!tempmute`. "
            "Requires Moderate Members; mention a member and provide duration and reason (maximum 28 days).\n"
            "`b!untimeout @user [reason]` — Remove a timeout. Aliases: `b!unmute`, `b!removetimeout`.\n"
            "`b!kick @user [reason]` — Kick a mentioned member. Requires Kick Members.\n"
            "`b!ban @user [reason]` — Ban a mentioned member. Requires Ban Members.\n"
            "`b!unban userID [reason]` — Unban by user ID. Requires Ban Members.\n"
            "`b!roleadd @user @role [reason]` — Give a role. Requires Manage Roles and member/role mentions.\n"
            "`b!roleremove @user @role [reason]` — Remove a role. Requires Manage Roles and member/role mentions."
        ),
        "footer": "BRAX • Moderation",
    },
    {
        "title": "<:Logging:1571302754272542852> Logging",
        "description": (
            "`b!mlogs` — View your own BRAX actions. `b!mlogs @user` — View that member's history. Three logs per page.\n"
            "`b!mlog [#channel]` — Set the moderation log channel. "
            "If no channel is supplied, BRAX uses the channel where you run the command.\n\n"
            "Moderation, blacklist, and Fun actions are recorded with the affected member "
            "and the moderator who performed them."
        ),
        "footer": "BRAX • Logging",
    },
    {
        "title": "<:Fun:1571324174394200085> Fun",
        "description": (
            "`b!mweute @user` — Fake mute a member for fun. This does not apply a real timeout.\n"
            "`b!uwu @user` — Toggle advanced UWU lock with randomized stutters, word swaps and endings. "
            "Messages are relayed through a clearly labelled BRAX UWU webhook. Run it again to remove the lock.\n"
            "`b!balance [@user]` — Check coins. `b!shop` / `b!store` — View the store. "
            "`b!buy` — Purchase store items.\n"
            "`b!coinflip heads|tails <amount>` and `b!gamble <amount> <2-30>` — Play coin games.\n"
            "`b!coinlb` — View the BRAX Coin leaderboard. `b!coinadd @user <amount>` — Add coins (Braxton only).\n"
            "`b!stocks`, `b!stockbuy`, `b!stocksell` — View and trade simulated shares.\n"
            "`b!mine` — Dig for Mick & Rorty materials and collectibles. `b!inventory` — View your finds.\n"
            "`b!sell <item> [amount]` — Sell finds for BRAX Coins. `b!trade @member` — Open a private item/coin trade.\n"
            "Inside a trade: `b!offercoins`, `b!offeritem`, `b!tradeconfirm`, `b!tradecancel`.\n\n"
            "UWU lock requires BRAX Usage and Manage Messages. Fun actions are also sent "
            "to the moderation log and saved in the target member's `b!mlogs` history."
        ),
        "footer": "BRAX • Fun",
    },
]

GAMBLING_HELP_PAGE = {
    "title": "🎲 Gambling",
    "description": (
        "`b!gamble <amount> <2-30>` — Bet any positive amount of BRAX Coins at a 2x–30x multiplier. "
        "Bets above 10x can put your balance into debt.\n"
        "Example: `b!gamble 100 15`\n\n"
        "You have a 1-in-the-multiplier chance to win. A win pays the bet multiplied by your selected multiplier; a loss deducts the bet."
    ),
    "footer": "BRAX • Gambling",
}
LESSER_FUN_HELP_PAGE = {
    "title": "<:Fun:1571324174394200085> Fun",
    "description": (
        "`b!mweute @user` — Fake mute a member for fun. This does not apply a real timeout.\n\n"
        "You can also use b!mine to dig, b!inventory to view finds, b!sell <item> to sell, and b!trade @member to open a private trade.\n\nUse the forward button to view the gambling commands."
    ),
    "footer": "BRAX • Lesser B Usage",
}
LESSER_HELP_PAGES = [LESSER_FUN_HELP_PAGE, GAMBLING_HELP_PAGE]


def make_help_embed(page_index, pages=None):
    pages = pages or HELP_PAGES
    page = pages[page_index]
    embed = discord.Embed(
        title=page["title"],
        description=page["description"],
        color=discord.Color.from_rgb(58, 48, 35),
    )
    embed.set_footer(text=f'{page["footer"]} • Page {page_index + 1}/{len(pages)}')
    return embed


class BraxHelpView(discord.ui.View):
    def __init__(self, author_id, pages=None):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.pages = pages or HELP_PAGES
        self.page = 0
        self.back_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            emoji=discord.PartialEmoji.from_str("<:Backwards:1571304371646632077>"),
            custom_id="brax:help:back",
            disabled=True,
        )
        self.forward_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            emoji=discord.PartialEmoji.from_str("<:Forward:1571304228255957133>"),
            custom_id="brax:help:forward",
            disabled=len(self.pages) <= 1,
        )
        self.back_button.callback = self.go_back
        self.forward_button.callback = self.go_forward
        self.add_item(self.back_button)
        self.add_item(self.forward_button)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the person who opened this help menu can turn its pages.",
                ephemeral=True,
            )
            return False
        return True

    async def update_page(self, interaction):
        self.back_button.disabled = self.page == 0
        self.forward_button.disabled = self.page == len(self.pages) - 1
        await interaction.response.edit_message(
            embed=make_help_embed(self.page, self.pages),
            view=self,
        )

    async def go_back(self, interaction):
        self.page = max(0, self.page - 1)
        await self.update_page(interaction)

    async def go_forward(self, interaction):
        self.page = min(len(self.pages) - 1, self.page + 1)
        await self.update_page(interaction)


@bot.command(name="help")
async def brax_help_command(ctx):
    if has_lesser_usage(ctx.author):
        view = BraxHelpView(ctx.author.id, pages=LESSER_HELP_PAGES)
        await ctx.reply(embed=make_help_embed(0, LESSER_HELP_PAGES), view=view, mention_author=False)
        return
    if not is_high_staff(ctx.author):
        await ctx.reply(embed=make_help_embed(0, [GAMBLING_HELP_PAGE]), mention_author=False)
        return
    view = BraxHelpView(ctx.author.id)
    await ctx.reply(embed=make_help_embed(0), view=view, mention_author=False)

@bot.tree.command(name="help", description="Show BRAX help and public gambling commands.")
async def brax_slash_help_command(interaction: discord.Interaction):
    if has_lesser_usage(interaction.user):
        view = BraxHelpView(interaction.user.id, pages=LESSER_HELP_PAGES)
        await interaction.response.send_message(embed=make_help_embed(0, LESSER_HELP_PAGES), view=view, ephemeral=True)
        return
    if not is_high_staff(interaction.user):
        await interaction.response.send_message(embed=make_help_embed(0, [GAMBLING_HELP_PAGE]), ephemeral=True)
        return
    embed = discord.Embed(
        title="BRAX Commands",
        description="Commands available to members with the BRAX Usage role:",
        color=discord.Color.from_rgb(58, 48, 35),
    )
    embed.add_field(name="Moderation", value="b!timeout, b!untimeout, b!kick, b!ban, b!unban, b!roleadd, b!roleremove", inline=False)
    embed.add_field(name="Logging", value="b!mlog [#channel] sets the moderation log channel.", inline=False)
    embed.add_field(name="Server Tools", value="b!ticketpanel, b!blacklist @user, b!lusageadd @user, b!help, /help", inline=False)
    embed.add_field(name="Fun, Economy & Mining", value="b!mweute, b!uwu, b!balance, b!shop, b!buy, b!coinflip, b!gamble, b!coinlb, b!stocks, b!mine, b!inventory, b!sell, b!trade", inline=False)
    embed.set_footer(text="BRAX • BRAX Usage Role Only")
    await interaction.response.send_message(embed=embed, ephemeral=True)

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Check that Wispbyte's .env file is in the "
        "server's working directory and contains BOT_TOKEN=your_token."
    )

print("BRAX BUILD: mining-trading-2026-11-15 | persistent-inventory | private-trade-channels | uwu-ch33zee | divine-allowlist-update | full-moderation")
bot.run(TOKEN)
