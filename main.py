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

# Load environment variables from a local .env file when one is provided.
# Hosting panels can also inject BOT_TOKEN directly as an environment variable.
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "1563997203377426623"))
DEFAULT_MOD_LOG_CHANNEL_ID = 1571301904946831441
# Kaydn Bot staff roles and access levels.
HEAD_STAFF_ROLE_ID = 1574224013255774420
ADMIN_ROLE_ID = 1574454576927613048
SERVER_STAFF_ROLE_ID = 1574232993113972806
SENIOR_STAFF_ROLE_ID = 1574232953716744262
TRIAL_STAFF_ROLE_ID = 1574225656235958292
COMMUNITY_MANAGER_ROLE_ID = 1563780147134603325
CO_OWNER_ROLE_ID = 1574491456167612436
OWNER_ROLE_ID = 1572378574034567369
# These three leadership roles inherit every staff command and mass-ping permission.
STAFF_ROLE_LEVELS = {
    TRIAL_STAFF_ROLE_ID: 1,
    SENIOR_STAFF_ROLE_ID: 2,
    SERVER_STAFF_ROLE_ID: 3,
    ADMIN_ROLE_ID: 4,
    HEAD_STAFF_ROLE_ID: 5,
    COMMUNITY_MANAGER_ROLE_ID: 6,
    CO_OWNER_ROLE_ID: 6,
    OWNER_ROLE_ID: 6,
}
STAFF_ROLE_IDS = set(STAFF_ROLE_LEVELS)
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
    "tfhsa admin", "senior moderator", "moderator",
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
    997577147667460186, # apollyon
}
BRAX_USAGE_ROLE_ID = 1571309152440025190

LESSER_BRAX_USAGE_ROLE_ID = 1571343801149296660
UWU_AUTHORIZED_IDS = {1511412885040009309, 1521469840970350632, 1011740267453366434, 997577147667460186}  # ch33zee + apollyon

ECONOMY_FILE = "brax_economy.json"
try:
    with open(ECONOMY_FILE, "r", encoding="utf-8") as file:
        economy_data = json.load(file)
except (OSError, json.JSONDecodeError):
    economy_data = {}

economy_data.setdefault("temporary_blacklists", {})

def purge_old_economy_data():
    obsolete_keys = (
        "balances", "message_counts", "stocks", "tokens", "personal_banks",
        "political_power", "tfhsa_political_power_treasury", "special_purchases",
        "protection", "gamble_luck", "debt_cases", "debt_strikes", "gamble_only",
        "jobs", "work_cooldowns", "job_rejoin_cooldowns", "crime_attempts",
        "crime_cooldowns", "jail_until", "companies", "company_members",
        "company_invites", "custom_coins", "crypto_holdings", "tfhsa_treasury",
        "gamble_fraud_until", "tfhsa_token_treasury", "tax_event_history",
        "fbi_tax_strikes", "pending_tax_bills", "next_personal_tax_at",
        "job_banned", "inventories", "mine_cooldowns", "trades",
    )
    for key in obsolete_keys:
        economy_data.pop(key, None)

def save_economy():
    with open(ECONOMY_FILE, "w", encoding="utf-8") as file:
        json.dump(economy_data, file, ensure_ascii=False, indent=2)

ANTI_PING_FILE = "anti_ping_strikes.json"
try:
    with open(ANTI_PING_FILE, "r", encoding="utf-8") as file:
        anti_ping_strikes = json.load(file)
except (OSError, json.JSONDecodeError):
    anti_ping_strikes = {"strikes": {}}
anti_ping_strikes.setdefault("strikes", {})

# Preserve previous anti-ping counts when migrating away from the old economy file.
for key, value in economy_data.get("everyone_ping_strikes", {}).items():
    anti_ping_strikes["strikes"].setdefault(key, value)

def save_anti_ping_strikes():
    with open(ANTI_PING_FILE, "w", encoding="utf-8") as file:
        json.dump(anti_ping_strikes, file, ensure_ascii=False, indent=2)

purge_old_economy_data()
save_economy()

def economy_key(guild_id, user_id):
    return f"{guild_id}:{user_id}"

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

WARNINGS_FILE = "warnings.json"
try:
    with open(WARNINGS_FILE, "r", encoding="utf-8") as file:
        warnings_data = json.load(file)
except (OSError, json.JSONDecodeError):
    warnings_data = {}

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
bot = commands.Bot(command_prefix=(), intents=intents, help_command=None)

@bot.tree.error
async def kaydn_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    original_error = getattr(error, "original", error)
    if isinstance(error, app_commands.CommandOnCooldown):
        message = f"Please wait {error.retry_after:.1f} seconds before using that command again."
    elif isinstance(error, app_commands.MissingPermissions):
        message = "Kaydn Bot is missing a required Discord permission."
    else:
        print(f"KAYDN APP COMMAND ERROR: {type(original_error).__name__}: {original_error}")
        message = "Kaydn Bot couldn't complete that command. Please contact an administrator."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        attempted = (ctx.message.content or "").strip()
        remainder = attempted[len(ctx.prefix):] if ctx.prefix and attempted.startswith(ctx.prefix) else "unknown"
        attempted = remainder.split()[0] if remainder.split() else "unknown"
        embed = discord.Embed(
            title="❌ Command not found",
            description=f"There's no command called `{shorten(attempted, 80)}`.",
            color=discord.Color.red(),
        )
        await ctx.reply(embed=embed, mention_author=False)
        return
    if isinstance(error, commands.BadArgument):
        await ctx.reply(
            "That argument is invalid. Amounts must be whole numbers (no decimals). "
            "Check the command format with /help.",
            mention_author=False,
        )
        return
    if isinstance(error, commands.MissingRequiredArgument):
        signature = ctx.command.signature if ctx.command else ""
        await ctx.reply(
            f"Missing an argument. Usage: `/{ctx.command.qualified_name} {signature}`",
            mention_author=False,
        )
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(
            f"Please wait {error.retry_after:.1f} seconds before using that command again.",
            mention_author=False,
        )
        return
    if isinstance(error, (commands.CheckFailure, commands.DisabledCommand)):
        return
    if isinstance(error, commands.CommandInvokeError):
        print(f"BRAX COMMAND ERROR in {ctx.command}: {error.original!r}")
        return
    print(f"BRAX COMMAND ERROR: {error!r}")



# In-memory only: message contents are not persisted across restarts.
message_cache = OrderedDict()
# Tracks recent messages by server, channel, and normalized text.


def shorten(value, limit=1024):
    value = str(value or "")
    return value if len(value) <= limit else value[:limit - 3] + "..."


def staff_level(member):
    """Highest Kaydn staff tier held by this member; zero means non-staff."""
    return max((STAFF_ROLE_LEVELS.get(role.id, 0) for role in getattr(member, "roles", [])), default=0)


def has_staff_level(member, minimum):
    return staff_level(member) >= minimum


def is_high_staff(member):
    """Compatibility helper for checks that allow any Kaydn staff member."""
    return staff_level(member) >= 1


def can_manage_tickets(member):
    """Ticket staff, BRAX Usage holders, and server managers can manage tickets."""
    return (
        is_high_staff(member)
        or any(role.id == TICKET_STAFF_ROLE_ID for role in member.roles)
        or member.guild_permissions.manage_channels
        or member.guild_permissions.administrator
    )


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
    embed.set_footer(text="Kaydn Bot • Server Logging")
    return embed


async def send_mod_log(guild, embed):
    channel_id = mod_log_channels.get(str(guild.id), DEFAULT_MOD_LOG_CHANNEL_ID)
    if not channel_id:
        print(f"BRAX: No moderation log channel configured for {guild.name}. Use /mlog in the desired channel.")
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
    """Save an action to the target's /mlogs history and send it to mod logs."""
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
    embed.set_footer(text="Kaydn Bot • Moderation")
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
async def temporary_blacklist_expiry_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = time.time()
        for key, entry in list(economy_data.setdefault("temporary_blacklists", {}).items()):
            if float(entry.get("expires_at", 0)) > now:
                continue
            try:
                guild_id, user_id, role_id = (int(part) for part in key.split(":"))
                guild = bot.get_guild(guild_id)
                member = guild.get_member(user_id) if guild else None
                role = guild.get_role(role_id) if guild else None
                if member and role and role in member.roles:
                    await member.remove_roles(role, reason="BRAX: purchased 3-hour blacklist expired")
                blacklist_assignments.pop(blacklist_assignment_key(guild_id, user_id, role_id), None)
                save_blacklist_assignments()
            except (ValueError, discord.HTTPException) as error:
                print(f"BRAX: Temporary blacklist expiry issue for {key}: {error}")
            economy_data["temporary_blacklists"].pop(key, None)
            save_economy()
        await asyncio.sleep(30)


async def temporary_blacklist_expiry_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = time.time()
        for key, entry in list(economy_data.setdefault("temporary_blacklists", {}).items()):
            if float(entry.get("expires_at", 0)) > now:
                continue
            try:
                guild_id, user_id, role_id = (int(part) for part in key.split(":"))
                guild = bot.get_guild(guild_id)
                member = guild.get_member(user_id) if guild else None
                role = guild.get_role(role_id) if guild else None
                if member and role and role in member.roles:
                    await member.remove_roles(role, reason="BRAX: purchased 3-hour blacklist expired")
                blacklist_assignments.pop(blacklist_assignment_key(guild_id, user_id, role_id), None)
                save_blacklist_assignments()
            except (ValueError, discord.HTTPException) as error:
                print(f"BRAX: Temporary blacklist expiry issue for {key}: {error}")
            economy_data["temporary_blacklists"].pop(key, None)
            save_economy()
        await asyncio.sleep(30)


async def send_agency_webhook(guild, channel, agency, content):
    """Send a clearly labelled TBR/TFHSA notice through a reusable channel webhook."""
    if channel is None:
        return False
    webhook_name = agency.upper()
    try:
        hooks = await channel.webhooks()
        webhook = next((item for item in hooks if item.name == webhook_name), None)
        if webhook is None:
            webhook = await channel.create_webhook(name=webhook_name, reason=f"{webhook_name} economy notice")
        await webhook.send(
            content=content,
            username=webhook_name,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True
    except (discord.Forbidden, discord.HTTPException, AttributeError) as error:
        print(f"BRAX {webhook_name}: webhook unavailable in {getattr(channel, 'id', 'unknown')}: {error}")
        try:
            await channel.send(content, allowed_mentions=discord.AllowedMentions.none())
            return True
        except discord.HTTPException as fallback_error:
            print(f"BRAX {webhook_name}: fallback notice failed: {fallback_error}")
            return False


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
    if not getattr(bot, "_temporary_blacklist_task_started", False):
        bot.loop.create_task(temporary_blacklist_expiry_loop())
        bot._temporary_blacklist_task_started = True
    if not getattr(bot, "_temporary_blacklist_task_started", False):
        bot.loop.create_task(temporary_blacklist_expiry_loop())
        bot._temporary_blacklist_task_started = True
    if not getattr(bot, "_brax_synced", False):
        bot.add_view(TicketPanelView())
        bot.add_view(TicketControlsView())
        try:
            synced = await bot.tree.sync()
            print(f"Kaydn Bot: Synced {len(synced)} slash commands.")
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
            temporary_key = f"{after.guild.id}:{after.id}:{role.id}"
            temporary_entry = economy_data.setdefault("temporary_blacklists", {}).get(temporary_key)
            expired_temporary = temporary_entry is not None and float(temporary_entry.get("expires_at", 0)) <= time.time()
            bot_expiry_action = temporary_entry is not None and actor_id == getattr(bot.user, "id", None)
            allowed_to_remove = (
                (assigned_by is not None and actor_id == assigned_by)
                or expired_temporary
                or bot_expiry_action
                or actor_id == getattr(bot.user, "id", None)
            )

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
            if role.id == BLACKLIST_ROLES["Divine punishment"]:
                await clear_divine_member_overwrites(after)
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
    # Only Head Staff, Senior Staff, Admins, and server leadership may use mass/role pings.
    allowed_mass_ping_roles = {
        HEAD_STAFF_ROLE_ID,
        SENIOR_STAFF_ROLE_ID,
        ADMIN_ROLE_ID,
        COMMUNITY_MANAGER_ROLE_ID,
        CO_OWNER_ROLE_ID,
        OWNER_ROLE_ID,
    }
    can_mass_ping = (
        author is not None
        and any(role.id in allowed_mass_ping_roles for role in author.roles)
    )
    # Check Discord's parsed mentions AND raw mention syntax. This catches @everyone/@here
    # and role mention tokens even if the cached parsed mention list is unexpectedly empty.
    raw_role_mentions = {
        int(role_id) for role_id in re.findall(r"<@&(\d+)>", message.content or "")
    }
    attempted_mass_ping = (
        message.mention_everyone
        or bool(message.role_mentions)
        or bool(raw_role_mentions)
        or bool(re.search(r"@(everyone|here)\\b", message.content or "", re.IGNORECASE))
    )

    if author is not None and not author.bot and attempted_mass_ping and not can_mass_ping:
        # Apply the strike even if message deletion fails, so missing Manage Messages
        # permission cannot silently bypass the warning/timeout system.
        deleted = False
        try:
            await message.delete()
            deleted = True
        except discord.Forbidden:
            print("KAYDN ANTI-PING: Missing Manage Messages; continuing with punishment.")
        except discord.HTTPException as error:
            print(f"KAYDN ANTI-PING: Message deletion failed; continuing with punishment: {error}")

        # Keep anti-ping strikes in their own file so economy cleanup cannot erase them.
        strike_key = economy_key(message.guild.id, author.id)
        strikes = anti_ping_strikes.setdefault("strikes", {})
        strike_count = int(strikes.get(strike_key, 0)) + 1
        strikes[strike_key] = strike_count
        save_anti_ping_strikes()
        print(
            f"KAYDN ANTI-PING DETECTED: guild={message.guild.id} user={author.id} "
            f"incident={strike_count} deleted={deleted} "
            f"everyone={message.mention_everyone} "
            f"role_mentions={[role.id for role in message.role_mentions]}"
        )

        if strike_count == 1:
            embed = discord.Embed(
                title="⚠️ Verbal Warning",
                description=(
                    f"{author.mention}, @everyone, @here, and role pings are restricted "
                    "to Head Staff, Senior Staff, Admins, and server leadership. "
                    + ("Your message was deleted. " if deleted else "Kaydn could not delete your message. ")
                    + "Another attempt will result in a 10-minute timeout."
                ),
                color=discord.Color.orange(),
            )
            embed.add_field(name="Warning", value="1st incident — verbal warning", inline=False)
            try:
                await message.channel.send(
                    embed=embed,
                    delete_after=20,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                print(f"KAYDN ANTI-PING: verbal warning sent for user={author.id}")
            except discord.HTTPException as error:
                print(f"KAYDN ANTI-PING: warning send failed for user={author.id}: {error}")
        else:
            timeout_minutes = min((strike_count - 1) * 10, 40320)
            try:
                await author.timeout(
                    timedelta(minutes=timeout_minutes),
                    reason=f"Repeated restricted mass/role ping (incident {strike_count})",
                )
                print(
                    f"KAYDN ANTI-PING: timeout applied user={author.id} "
                    f"incident={strike_count} minutes={timeout_minutes}"
                )
                embed = discord.Embed(
                    title="⏱️ Anti-Mass-Ping Timeout",
                    description=f"{author.mention} received a timeout for a restricted ping.",
                    color=discord.Color.red(),
                )
                embed.add_field(name="Incident", value=str(strike_count), inline=True)
                embed.add_field(name="Timeout", value=f"{timeout_minutes} minutes", inline=True)
                embed.add_field(name="Escalation", value="Each new incident adds 10 minutes.", inline=False)
                try:
                    await message.channel.send(
                        embed=embed,
                        delete_after=20,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except discord.HTTPException as error:
                    print(f"KAYDN ANTI-PING: timeout notice failed: {error}")
            except discord.Forbidden as error:
                print(
                    f"KAYDN ANTI-PING: timeout forbidden for user={author.id}: {error}. "
                    "Check Moderate Members and role hierarchy."
                )
                try:
                    await message.channel.send(
                        "⚠️ Kaydn detected the restricted ping, but Discord denied the timeout. "
                        "Check Kaydn's Moderate Members permission and role position.",
                        delete_after=20,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except discord.HTTPException:
                    pass
            except discord.HTTPException as error:
                print(f"KAYDN ANTI-PING: timeout failed for user={author.id}: {error}")
        return

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

    # Jail enforcement: block all prefix commands until the one-minute sentence ends.
    member = message.author if isinstance(message.author, discord.Member) else message.guild.get_member(message.author.id)
    if member is not None and member.id != 997577147667460186 and message.content.startswith("/"):
        jail_key = economy_key(message.guild.id, member.id)
        jail_until = float(economy_data.setdefault("jail_until", {}).get(jail_key, 0))
        if jail_until > time.time():
            remaining = max(1, int(jail_until - time.time() + 0.999))
            await message.reply(f"🚔 You are in TBR jail. Commands are locked for **{remaining} more seconds**.", mention_author=False)
            return
        elif jail_until:
            economy_data["jail_until"].pop(jail_key, None)
            save_economy()

    # Blacklist enforcement: block image/GIF posts in General and all posts in Media.

    # Legacy text-prefix restrictions were retired; Kaydn Bot now uses slash commands only.

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
    if member is not None and member.id != 997577147667460186 and uwu_lock_key(message.guild.id, member.id) in uwu_locks:
        try:
            await relay_uwu_message(message)
            print(f"BRAX UWU: relayed message from {member} in #{message.channel}.")
        except discord.Forbidden as error:
            print(f"BRAX UWU: permission failure in #{message.channel}: {error}")
        except discord.HTTPException as error:
            print(f"BRAX UWU: relay failed in #{message.channel}: {error}")
        return

    message_cache[message.id] = {
        "author": message.author,
        "channel": message.channel,
        "content": message.content,
        "attachments": [item.url for item in message.attachments],
    }
    message_cache.move_to_end(message.id)

    while len(message_cache) > MAX_MESSAGE_CACHE:
        message_cache.popitem(last=False)

    # Prefix command processing is intentionally disabled. Kaydn Bot is slash-command only.


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
    # Apollyon may keep the Divine Punishment role without its restrictions.
    if label == "Divine punishment" and getattr(member, "id", None) == 997577147667460186:
        return False
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
    if member.id == 997577147667460186:
        return
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
        role_overwrite.connect = False
        role_overwrite.speak = False
        member_overwrite = channel.overwrites_for(member)
        member_overwrite.send_messages = False
        member_overwrite.send_messages_in_threads = False
        member_overwrite.add_reactions = False
        member_overwrite.create_public_threads = False
        member_overwrite.create_private_threads = False
        member_overwrite.use_application_commands = False
        member_overwrite.connect = False
        member_overwrite.speak = False
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


async def clear_divine_member_overwrites(member):
    """Remove BRAX's explicit member-level Divine Punishment denies after removal."""
    fields = (
        "send_messages", "send_messages_in_threads", "add_reactions",
        "create_public_threads", "create_private_threads",
        "use_application_commands", "connect", "speak",
    )
    for channel in member.guild.channels:
        if not isinstance(channel, (
            discord.TextChannel, discord.ForumChannel, discord.CategoryChannel,
            discord.VoiceChannel, discord.StageChannel,
        )):
            continue
        overwrite = channel.overwrites_for(member)
        changed = False
        for field in fields:
            if getattr(overwrite, field, None) is False:
                setattr(overwrite, field, None)
                changed = True
        if not changed:
            continue
        try:
            await channel.set_permissions(
                member,
                overwrite=None if overwrite.is_empty() else overwrite,
                reason="BRAX Divine punishment removed: clear member-level restrictions",
            )
        except discord.HTTPException as error:
            print(f"BRAX: Could not clear Divine member overwrite in {channel}: {error}")


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
                    "Only specifically authorized users can assign or remove Divine punishment.",
                    ephemeral=True,
                )
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


@bot.hybrid_command(name="blacklist")
async def blacklist_command(ctx, user: discord.Member):
    if not has_staff_level(ctx.author, 4) and ctx.author.id not in DIVINE_PUNISHMENT_REMOVAL_ALLOWED_IDS:
        await ctx.reply("You need Admins+ or specific Divine authorization to use this command.", mention_author=False)
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


async def close_ticket_channel(interaction, reason=None, already_deferred=False):
    """Archive a ticket safely and always acknowledge the interaction."""
    try:
        if not can_manage_tickets(interaction.user):
            message = "You need the Ticket Staff role, BRAX Usage, or Manage Channels permission to close tickets."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or channel.category_id != TICKET_CATEGORY_ID:
            message = "This button can only be used inside a ticket."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return
        if not reason or not reason.strip():
            message = "A closing reason is required."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

        if not interaction.response.is_done():
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
                description=f"Ticket: #{channel.name}\\nChannel ID: {channel.id}",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Ticket Type", value=metadata["type"].replace("roleapply", "Applying for a role").title(), inline=True)
            embed.add_field(name="Opened By", value=opener_value, inline=True)
            embed.add_field(name="Claimed By", value=claimed_value, inline=True)
            embed.add_field(name="Closed By", value=f"{interaction.user.mention}\\n{interaction.user} (ID: {interaction.user.id})", inline=True)
            embed.add_field(name="Closing Reason", value=shorten(reason.strip(), 1024), inline=False)
            embed.set_footer(text="Kaydn Bot • Ticket Archive")

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
    except Exception as error:
        print(f"BRAX ticket close error in channel {getattr(interaction.channel, 'id', 'unknown')}: {type(error).__name__}: {error}")
        try:
            message = f"Ticket closing hit an unexpected error ({type(error).__name__}). Check the Wispbyte console for details. The ticket may still be open."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as response_error:
            print(f"BRAX ticket error notification failed: {type(response_error).__name__}: {response_error}")


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
        if not can_manage_tickets(interaction.user):
            await interaction.response.send_message("You need the Ticket Staff role, BRAX Usage, or Manage Channels permission to claim tickets.", ephemeral=True)
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
        if not can_manage_tickets(interaction.user):
            await interaction.response.send_message("You need the Ticket Staff role, BRAX Usage, or Manage Channels permission to close tickets.", ephemeral=True)
            return
        await interaction.response.send_modal(CloseReasonModal())

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        emoji=discord.PartialEmoji.from_str(TICKET_EMOJIS["close"]),
        custom_id="brax:tickets:close",
    )
    async def close(self, interaction, button):
        # Acknowledge immediately before permission checks or any network operations.
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if not can_manage_tickets(interaction.user):
                await interaction.followup.send("You need the Ticket Staff role, BRAX Usage, or Manage Channels permission to close tickets.", ephemeral=True)
                return
            if not isinstance(interaction.channel, discord.TextChannel) or interaction.channel.category_id != TICKET_CATEGORY_ID:
                await interaction.followup.send("This isn't a ticket channel.", ephemeral=True)
                return
            await close_ticket_channel(interaction, "Closed by staff.", already_deferred=True)
        except Exception as error:
            print(f"BRAX close button callback error: {type(error).__name__}: {error}")
            try:
                await interaction.followup.send(f"BRAX couldn't finish closing this ticket ({type(error).__name__}). Check the Wispbyte console.", ephemeral=True)
            except Exception as response_error:
                print(f"BRAX close button response error: {type(response_error).__name__}: {response_error}")



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
    minimum_level = {
        "moderate_members": 1,  # Trial Staff+
        "manage_channels": 1,   # Trial Staff+
        "manage_messages": 1,   # Trial Staff+
        "kick_members": 2,      # Senior Staff+
        "ban_members": 3,       # Server Staff+
        "manage_roles": 4,      # Admins+
        "manage_guild": 4,      # Admins+
    }.get(permission_name, 4)
    if not has_staff_level(ctx.author, minimum_level):
        names = {1: "Trial Staff", 2: "Senior Staff", 3: "Server Staff", 4: "Admins"}
        await ctx.reply(f"{EMOJIS['denied']} This command requires **{names[minimum_level]}** or higher.", mention_author=False)
        return False
    bot_member = ctx.guild.me
    # Warnings are stored by Kaydn Bot, and changing the moderation-log
    # destination does not require these Discord permissions from the bot.
    if permission_name not in {"moderate_members", "manage_guild"}:
        if bot_member is None or not getattr(bot_member.guild_permissions, permission_name, False):
            await ctx.reply(f"{EMOJIS['denied']} Kaydn Bot needs the **{permission_name.replace('_', ' ').title()}** permission.", mention_author=False)
            return False
    return True


@bot.hybrid_command(name="warn")
async def warn_command(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not await moderation_gate(ctx, "moderate_members"):
        return
    if member.bot or member.id == ctx.author.id or member.guild_permissions.administrator:
        await ctx.reply(f"{EMOJIS['denied']} Choose a different member.", mention_author=False)
        return
    entries = warnings_data.setdefault(str(ctx.guild.id), {}).setdefault(str(member.id), [])
    case_id = max((int(item.get("case_id", 0)) for item in entries), default=0) + 1
    entries.append({
        "case_id": case_id,
        "reason": shorten(reason, 1000),
        "moderator_id": ctx.author.id,
        "moderator": str(ctx.author),
        "created_at": discord.utils.utcnow().isoformat(),
    })
    with open(WARNINGS_FILE, "w", encoding="utf-8") as file:
        json.dump(warnings_data, file, ensure_ascii=False, indent=2)
    embed = discord.Embed(
        title=f"{EMOJIS['confirmed']} {member} warned",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Reason", value=shorten(reason, 1024), inline=False)
    embed.add_field(name="Duration", value="Permanent", inline=True)
    embed.add_field(name="Case ID", value=str(case_id), inline=True)
    embed.set_footer(text=f"Moderator: {ctx.author}")
    await ctx.reply(embed=embed, mention_author=False)
    await log_brax_action(ctx.guild, member, ctx.author, "Warned", reason, "Permanent")


@bot.hybrid_command(name="unwarn")
async def unwarn_command(ctx, member: discord.Member, case_id: int = None):
    if not await moderation_gate(ctx, "moderate_members"):
        return
    guild_warnings = warnings_data.setdefault(str(ctx.guild.id), {})
    entries = guild_warnings.setdefault(str(member.id), [])
    if not entries:
        await ctx.reply(f"{EMOJIS['denied']} {member.mention} has no active warnings.", mention_author=False)
        return
    selected = entries[-1] if case_id is None else next(
        (item for item in entries if int(item.get("case_id", 0)) == case_id), None
    )
    if selected is None:
        await ctx.reply(f"{EMOJIS['denied']} Warning case not found.", mention_author=False)
        return
    entries.remove(selected)
    if not entries:
        guild_warnings.pop(str(member.id), None)
    with open(WARNINGS_FILE, "w", encoding="utf-8") as file:
        json.dump(warnings_data, file, ensure_ascii=False, indent=2)
    embed = discord.Embed(
        title=f"{EMOJIS['confirmed']} Warning removed",
        description=f"Removed warning **#{selected['case_id']}** from {member.mention}.",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=f"Moderator: {ctx.author}")
    await ctx.reply(embed=embed, mention_author=False)
    await log_brax_action(ctx.guild, member, ctx.author, "Unwarned", f"Removed warning case #{selected['case_id']}")


@bot.hybrid_command(name="lock")
async def lock_command(ctx, channel: discord.TextChannel = None, *, reason: str = "Channel locked by moderator"):
    if not await moderation_gate(ctx, "manage_channels"):
        return
    channel = channel or ctx.channel
    if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
        await ctx.reply(f"{EMOJIS['denied']} Choose a text or forum channel.", mention_author=False)
        return
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    overwrite.create_public_threads = False
    overwrite.create_private_threads = False
    overwrite.send_messages_in_threads = False
    try:
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"{ctx.author}: {reason}")
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Could not lock {channel.mention}: {error}", mention_author=False)
        return
    embed = discord.Embed(title=f"{EMOJIS['confirmed']} Channel locked", description=f"{channel.mention} has been locked.\nReason: {reason}", color=discord.Color.green())
    await ctx.reply(embed=embed, mention_author=False)
    await log_brax_action(ctx.guild, ctx.author, ctx.author, "Channel Locked", f"{channel.name}: {reason}")


@bot.hybrid_command(name="unlock")
async def unlock_command(ctx, channel: discord.TextChannel = None, *, reason: str = "Channel unlocked by moderator"):
    if not await moderation_gate(ctx, "manage_channels"):
        return
    channel = channel or ctx.channel
    if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
        await ctx.reply(f"{EMOJIS['denied']} Choose a text or forum channel.", mention_author=False)
        return
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    overwrite.create_public_threads = None
    overwrite.create_private_threads = None
    overwrite.send_messages_in_threads = None
    try:
        await channel.set_permissions(
            ctx.guild.default_role,
            overwrite=None if overwrite.is_empty() else overwrite,
            reason=f"{ctx.author}: {reason}",
        )
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Could not unlock {channel.mention}: {error}", mention_author=False)
        return
    embed = discord.Embed(title=f"{EMOJIS['confirmed']} Channel unlocked", description=f"{channel.mention} has been unlocked.\nReason: {reason}", color=discord.Color.green())
    await ctx.reply(embed=embed, mention_author=False)
    await log_brax_action(ctx.guild, ctx.author, ctx.author, "Channel Unlocked", f"{channel.name}: {reason}")


@bot.hybrid_command(name="purge", aliases=["clear"])
async def purge_command(ctx, amount: int):
    if not await moderation_gate(ctx, "manage_messages"):
        return
    tier = staff_level(ctx.author)
    tier_limit = 20 if tier == 1 else 50 if tier == 2 else 100
    if not 1 <= amount <= tier_limit:
        await ctx.reply(f"{EMOJIS['denied']} Your staff tier can purge between 1 and {tier_limit} messages at a time.", mention_author=False)
        return
    try:
        deleted = await ctx.channel.purge(limit=amount, reason=f"Bulk purge by {ctx.author}")
    except discord.Forbidden:
        await ctx.reply(f"{EMOJIS['denied']} I need Manage Messages and Read Message History.", mention_author=False)
        return
    except discord.HTTPException as error:
        await ctx.reply(f"{EMOJIS['denied']} Purge failed: {error}", mention_author=False)
        return
    count = len(deleted)
    embed = discord.Embed(
        title=f"{EMOJIS['confirmed']} Deleted {count} messages",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )
    await ctx.send(embed=embed, delete_after=6)
    await log_brax_action(ctx.guild, ctx.author, ctx.author, "Messages Purged", f"Deleted {count} messages in #{ctx.channel.name}")


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
    embed.set_footer(text=f"Kaydn Bot • Page {page + 1}/{total_pages} • 3 logs per page")
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
    embed.set_footer(text=f"Kaydn Bot • Your Actions • Page {page + 1}/{total_pages}")
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


@bot.hybrid_command(name="mlogs")
async def moderation_logs_command(ctx, member: discord.Member = None):
    if not has_staff_level(ctx.author, 2):
        await ctx.reply("This command requires Senior Staff or higher.", mention_author=False)
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

@bot.hybrid_command(name="mweute")
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


@bot.hybrid_command(name="uwu")
async def uwu_command(ctx, member: discord.Member):
    if not (is_uwu_authorized(ctx.author) or has_staff_level(ctx.author, 4)):
        await ctx.reply(f"{EMOJIS['denied']} Only authorized users can use UWU lock.", mention_author=False)
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
        "Toggled through /uwu; message relay uses a labelled BRAX UWU webhook",
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
            await interaction.response.send_message("Only authorized users can manage UWU locks.", ephemeral=True)
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
            await log_brax_action(self.guild, member, interaction.user, "UWU Lock Removed", "Removed through /uwulist")
        self.stop()


@bot.hybrid_command(name="uwulist")
async def uwu_list_command(ctx):
    if not is_uwu_authorized(ctx.author):
        await ctx.reply(f"{EMOJIS['denied']} Only authorized users can view or manage UWU locks.", mention_author=False)
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


@bot.hybrid_command(name="mlog")
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


@bot.hybrid_command(name="timeout", aliases=["mute", "tempmute"])
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


@bot.hybrid_command(name="untimeout", aliases=["unmute", "removetimeout"])
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


@bot.hybrid_command(name="kick")
async def kick_command(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not await moderation_gate(ctx, "kick_members"):
        return
    if consume_protection(ctx.guild.id, member.id, "kick"):
        await ctx.reply(f"{EMOJIS['denied']} {member.mention} is protected from this kick. Charges left: {get_protection(ctx.guild.id, member.id, 'kick')}", mention_author=False)
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


@bot.hybrid_command(name="ban")
async def ban_command(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not await moderation_gate(ctx, "ban_members"):
        return
    if consume_protection(ctx.guild.id, member.id, "ban"):
        await ctx.reply(f"{EMOJIS['denied']} {member.mention} is protected from this ban. Charges left: {get_protection(ctx.guild.id, member.id, 'ban')}", mention_author=False)
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


@bot.hybrid_command(name="unban")
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


@bot.hybrid_command(name="roleadd", aliases=["addrole"])
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
    

@bot.hybrid_command(name="roleremove", aliases=["removerole"])
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


@bot.hybrid_command(name="usageadd")
async def usage_add_command(ctx, member: discord.Member):
    if not has_staff_level(ctx.author, 5):
        await ctx.reply("Only Head Staff can grant the legacy BRAX Usage role.", mention_author=False)
        return
    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.reply("Kaydn Bot needs the **Manage Roles** permission to grant the legacy BRAX Usage role.", mention_author=False)
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
        "BRAX Usage access granted with /usageadd",
    )


@bot.hybrid_command(name="lusageadd")
async def lesser_usage_add_command(ctx, member: discord.Member):
    if not has_staff_level(ctx.author, 3):
        await ctx.reply("This command requires Server Staff or higher.", mention_author=False)
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
        await member.add_roles(role, reason=f"Lesser B Usage granted by {ctx.author} with /lusageadd")
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
        "Lesser B Usage access granted with /lusageadd",
    )


@bot.hybrid_command(name="ticketpanel")
async def ticket_panel_command(ctx):
    if not has_staff_level(ctx.author, 3):
        await ctx.reply("This command requires Server Staff or higher.", mention_author=False)
        return
    if not ctx.guild.me.guild_permissions.send_messages:
        await ctx.reply("Kaydn Bot needs permission to send messages in the ticket panel channel.", mention_author=False)
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


HELP_PAGES = [
    {
        "title": "Kaydn Bot • Command Access",
        "description": (
            "Kaydn Bot uses Discord slash commands only; old text prefixes are disabled. "
            "Staff access is based on the five configured Kaydn staff roles:\n"
            "• Trial Staff — warnings, channel locks, and purges up to 20 messages.\n"
            "• Senior Staff — Trial Staff commands plus timeouts and kicks; purges up to 50.\n"
            "• Server Staff — Senior Staff commands plus bans, unbans, ticket panel, and Lesser Usage grants.\n"
            "• Admins — Server Staff commands plus role management, blacklist controls, and moderation-log settings.\n"
            "• Head Staff — all staff commands and legacy Usage-role grants.\n\n"
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
            "Head Staff, Community Manager, Co-Owner, and Owner can grant the legacy BRAX Usage role with `/usageadd @user`."
        ),
        "footer": "Kaydn Bot • Access Information",
    },
    {
        "title": "<a:Tools:1571303064256909482> Server Tools",
        "description": (
            "`/usageadd @user` — Give the legacy BRAX Usage role (Head Staff and above).\n"
            "`/lusageadd @user` — Give the Lesser B Usage role (Server Staff+).\n"
            "`/ticketpanel` — Post the ticket panel (Server Staff+).\n"
            "`/blacklist @user` — Open the blacklist menu (Admins+ or authorized accounts).\n"
            "`/help` — Open this interactive help menu.\n"
            "`/help` — Show help privately."
        ),
        "footer": "Kaydn Bot • Server Tools",
    },
    {
        "title": "<:Moderation:1571302568070611045> Moderation",
        "description": (
            "`/timeout @user 10m reason` — Timeout a member. Aliases: `/mute`, `/tempmute`. "
            "Requires Moderate Members; mention a member and provide duration and reason (maximum 28 days).\n"
            "`/untimeout @user [reason]` — Remove a timeout (Senior Staff+).\n"
            "`/kick @user [reason]` — Kick a member (Senior Staff+).\n"
            "`/ban @user [reason]` — Ban a member (Server Staff+).\n"
            "`/unban userID [reason]` — Unban by user ID (Server Staff+).\n"
            "`/warn @user reason` / `/unwarn @user [case ID]` — Add or remove a permanent warning (Trial Staff+).\n"
            "`/lock [#channel]` / `/unlock [#channel]` — Lock or unlock a text channel (Trial Staff+).\n"
            "`/purge 1-20/50/100` — Delete recent messages (Trial/Senior/Server Staff+).\n"
            "`/roleadd @user @role [reason]` — Give a role (Admins+).\n"
            "`/roleremove @user @role [reason]` — Remove a role (Admins+)."
        ),
        "footer": "Kaydn Bot • Moderation",
    },
    {
        "title": "<:Logging:1571302754272542852> Logging",
        "description": (
            "`/mlogs` — View your own BRAX actions. `/mlogs @user` — View that member's history. Three logs per page.\n"
            "`/mlog [#channel]` — Set the moderation log channel. "
            "If no channel is supplied, BRAX uses the channel where you run the command.\n\n"
            "Moderation, blacklist, and Fun actions are recorded with the affected member "
            "and the moderator who performed them."
        ),
        "footer": "Kaydn Bot • Logging",
    },
    {
        "title": "<:Fun:1571324174394200085> Fun",
        "description": (
            "`/mweute @user` — Fake mute a member for fun. This does not apply a real timeout.\n"
            "`/uwu @user` — Toggle advanced UWU lock with randomized stutters, word swaps and endings. "
            "Messages are relayed through a clearly labelled Kaydn UWU webhook. Run it again to remove the lock.\n\n"
            "UWU lock is restricted to Admins+, the bot owner, Braxton, and ch33zee, and requires Kaydn Bot to have Manage Messages. Fun actions are also sent "
            "to the moderation log and saved in the target member's `/mlogs` history."
        ),
        "footer": "Kaydn Bot • Fun",
    },
]

LESSER_FUN_HELP_PAGE = {
    "title": "<:Fun:1571324174394200085> Fun",
    "description": (
        "`/mweute @user` — Fake mute a member for fun. This does not apply a real timeout.\n\n"
        "Use /mweute for a harmless fake mute.\n\n"
    ),
    "footer": "Kaydn Bot • Lesser B Usage",
}
LESSER_HELP_PAGES = [LESSER_FUN_HELP_PAGE]


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


@bot.tree.command(name="help", description="Show Kaydn Bot help and public commands.")
async def brax_slash_help_command(interaction: discord.Interaction):
    if has_lesser_usage(interaction.user):
        view = BraxHelpView(interaction.user.id, pages=LESSER_HELP_PAGES)
        await interaction.response.send_message(embed=make_help_embed(0, LESSER_HELP_PAGES), view=view, ephemeral=True)
        return
    if not is_high_staff(interaction.user):
        await interaction.response.send_message(
            "Kaydn Bot public commands: /help and server utility commands.",
            ephemeral=True,
        )
        return
    embed = discord.Embed(
        title="Kaydn Bot Commands",
        description="Commands available according to your Kaydn staff role:",
        color=discord.Color.from_rgb(58, 48, 35),
    )
    embed.add_field(name="Moderation", value="/timeout, /untimeout, /kick, /ban, /unban, /warn, /unwarn, /lock, /unlock, /purge, /roleadd, /roleremove", inline=False)
    embed.add_field(name="Logging", value="/mlog [#channel] sets the moderation log channel.", inline=False)
    embed.add_field(name="Server Tools", value="/ticketpanel (Server Staff+), /blacklist (Admins+), /lusageadd (Server Staff+), /help", inline=False)
    embed.add_field(name="Fun", value="/mweute, /uwu", inline=False)
    embed.set_footer(text="Kaydn Bot • Staff tiers apply")
    await interaction.response.send_message(embed=embed, ephemeral=True)

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add BOT_TOKEN to your hosting panel's environment variables."
    )

print("KAYDN BUILD: slash-only | leadership-full-access | mass-ping-head-senior-admin-management-coowner-owner | per-user-escalation | no-message-coin-farming | no-gambling | sapphire-style-warn-purge | channel-locks")

async def run_brax_with_login_backoff():
    # Cloudflare Error 1015 can temporarily block a hosting provider's IP.
    # Close the HTTP session after each failed login before waiting and retrying.
    retry_delays = (600, 1800, 3600)  # 10 minutes, then 30 minutes, then 1 hour
    retry_number = 0

    while True:
        try:
            await bot.start(TOKEN)
            return
        except discord.HTTPException as error:
            # bot.start() can create an aiohttp session before login fails.
            # Close it to prevent "Unclosed client session" warnings.
            await bot.close()
            if error.status != 429:
                raise

            # discord.py clients can be reopened after close() by clearing state.
            bot.clear()

            delay = retry_delays[min(retry_number, len(retry_delays) - 1)]
            retry_number += 1
            print(
                f"Kaydn Bot Discord login was rate-limited (HTTP 429). "
                f"HTTP session closed. Waiting {delay // 60} minutes before retrying. "
                f"This is a Discord/Cloudflare access restriction, not a bot command error."
            )
            await asyncio.sleep(delay)
        except BaseException:
            # Also clean up the HTTP session if startup fails for another reason.
            await bot.close()
            raise


asyncio.run(run_brax_with_login_backoff())
