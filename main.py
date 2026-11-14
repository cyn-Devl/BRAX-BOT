import os
import json
import asyncio
import time
from collections import OrderedDict
from datetime import timedelta

from dotenv import load_dotenv
import discord

from collections import deque
from discord import app_commands
from discord.ext import commands

# Load Wispbyte's .env file before reading any environment variables.
# With the server working directory set to /home/container, this loads
# /home/container/.env without hard-coding a hosting-specific path.
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "1563997203377426623"))
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
    "Staff blacklist": 1570148574480830626,
    "Divine punishment": 1571292901659644024,
}
GENERAL_CHANNEL_ID = 1561145710361976882
SUGGESTION_CHANNEL_ID = 1517259302459543714
MEDIA_CHANNEL_ID = 1561145636559003749
TICKETS_CHANNEL_ID = 1561188845154865173
TICKET_CATEGORY_ID = 1561150725588000808
TICKET_STAFF_ROLE_ID = 1563998176187260949
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
}
HIGH_STAFF_ROLE_NAMES = {
    "developers", "senior admin", "admin", "trial admin",
    "zinzicraftian admin", "senior moderator",
}
HIGH_STAFF_ROLE_IDS = {
    int(value.strip())
    for value in os.getenv("HIGH_STAFF_ROLE_IDS", "").split(",")
    if value.strip().isdigit()
}
role_blacklist_warnings = {}
BLACKLIST_ASSIGNMENTS_FILE = "blacklist_assignments.json"
try:
    with open(BLACKLIST_ASSIGNMENTS_FILE, "r", encoding="utf-8") as file:
        blacklist_assignments = json.load(file)
except (OSError, json.JSONDecodeError):
    blacklist_assignments = {}


def save_blacklist_assignments():
    with open(BLACKLIST_ASSIGNMENTS_FILE, "w", encoding="utf-8") as file:
        json.dump(blacklist_assignments, file)


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
    return any(
        role.id in HIGH_STAFF_ROLE_IDS or role.name.casefold() in HIGH_STAFF_ROLE_NAMES
        for role in member.roles
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
    embed.set_footer(text="BRAX • Server Logging")
    return embed


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

    # Blacklist enforcement: block image/GIF posts in General and all posts in Media.
    member = message.author if isinstance(message.author, discord.Member) else message.guild.get_member(message.author.id)
    if message.channel.id == MEDIA_CHANNEL_ID and member and has_blacklist(member, "Image blacklist"):
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        await send_user_warning(message.guild, member, "You're Image blacklisted, you can't do that buddy")
        return

    if message.channel.id == GENERAL_CHANNEL_ID and member and has_blacklist(member, "Image blacklist") and message_has_image(message):
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        await send_user_warning(message.guild, member, "You're Image blacklisted, you can't do that buddy")
        return

    if message.channel.id == SUGGESTION_CHANNEL_ID and member and has_blacklist(member, "Suggestion blacklist"):
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        return

    # Detect another member repeating the same text in the same channel.
    # Case and extra whitespace are ignored when comparing messages.
    normalized = " ".join(message.content.casefold().split())

    if len(normalized) >= MIN_DUPLICATE_LENGTH:
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
                    "Only the four authorized users can assign or remove Divine punishment.",
                    ephemeral=True,
                )
                return
        elif not is_high_staff(interaction.user):
            await interaction.response.send_message("Only higher staff can use BRAX blacklist controls.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("You need Manage Roles to use this.", ephemeral=True)
            return
        guild = interaction.guild
        role = guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message("That blacklist role could not be found.", ephemeral=True)
            return
        try:
            await self.target.add_roles(role, reason=f"Blacklist assigned by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "I can't assign that role. Move BRAX above the blacklist roles and grant Manage Roles.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as error:
            await interaction.response.send_message(f"Couldn't assign the role: {error}", ephemeral=True)
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
        await interaction.response.send_message(
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
        await ctx.reply("You don't have permission to use BRAX commands. This is limited to higher staff and the authorized Divine punishment users.", mention_author=False)
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
        if self.values[0] == "roleapply" and has_blacklist(member, "Application blacklist"):
            await interaction.response.send_message(
                "You're application blacklisted, so you can't open an application ticket.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
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
                topic=f"Ticket opened by {member} ({member.id}) • Type: {self.values[0]}",
                reason=f"Ticket opened by {member}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I need Manage Channels and permission to view the ticket category.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as error:
            await interaction.response.send_message(f"Couldn't create the ticket: {error}", ephemeral=True)
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
        await interaction.response.send_message(
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
        placeholder="Enter the reason for closing this ticket",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    async def on_submit(self, interaction):
        await close_ticket_channel(interaction, str(self.reason))


async def close_ticket_channel(interaction, reason=None):
    if not is_high_staff(interaction.user):
        await interaction.response.send_message("Only higher staff can close tickets with BRAX.", ephemeral=True)
        return
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel) or channel.category_id != TICKET_CATEGORY_ID:
        await interaction.response.send_message("This button can only be used inside a ticket.", ephemeral=True)
        return
    try:
        everyone = channel.guild.default_role
        overwrite = channel.overwrites_for(everyone)
        overwrite.send_messages = False
        await channel.set_permissions(everyone, overwrite=overwrite, reason="Ticket closed")
        for target, target_overwrite in list(channel.overwrites.items()):
            if isinstance(target, discord.Member):
                target_overwrite.send_messages = False
                await channel.set_permissions(target, overwrite=target_overwrite, reason="Ticket closed")
        suffix = channel.name
        if not suffix.startswith("closed-"):
            await channel.edit(name=f"closed-{suffix}"[:100])
        text = "This ticket has been closed."
        if reason:
            text += f"\n**Reason:** {reason}"
        await interaction.response.send_message(text)
    except discord.Forbidden:
        await interaction.response.send_message("I need Manage Channels to close this ticket.", ephemeral=True)
    except discord.HTTPException as error:
        await interaction.response.send_message(f"Couldn't close the ticket: {error}", ephemeral=True)


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
            await interaction.response.send_message("Only higher staff can claim tickets with BRAX.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel) or interaction.channel.category_id != TICKET_CATEGORY_ID:
            await interaction.response.send_message("This isn't a ticket channel.", ephemeral=True)
            return
        message = interaction.message
        embed = message.embeds[0] if message.embeds else discord.Embed(title="Ticket opened")
        embed.description = "Thank you for opening a ticket we will be here shortly\n\n" + f"**This ticket has been claimed by {interaction.user.mention}.**"
        await message.edit(embed=embed, view=self)
        await interaction.response.send_message("Ticket claimed.", ephemeral=True)

    @discord.ui.button(
        label="Close with a reason",
        style=discord.ButtonStyle.secondary,
        emoji=discord.PartialEmoji.from_str(TICKET_EMOJIS["reason"]),
        custom_id="brax:tickets:close_reason",
    )
    async def close_reason(self, interaction, button):
        if not is_high_staff(interaction.user):
            await interaction.response.send_message("Only higher staff can close tickets with BRAX.", ephemeral=True)
            return
        await interaction.response.send_modal(CloseReasonModal())

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        emoji=discord.PartialEmoji.from_str(TICKET_EMOJIS["close"]),
        custom_id="brax:tickets:close",
    )
    async def close(self, interaction, button):
        await close_ticket_channel(interaction)


@bot.command(name="ticketpanel")
async def ticket_panel_command(ctx):
    if not is_high_staff(ctx.author):
        await ctx.reply("You don't have permission to use BRAX commands. This is limited to higher staff.", mention_author=False)
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


@bot.command(name="help")
async def brax_help_command(ctx):
    if not is_high_staff(ctx.author):
        await ctx.reply("You don't have permission to use BRAX commands. This is limited to higher staff.", mention_author=False)
        return
    embed = discord.Embed(
        title="BRAX Commands",
        description="Commands available to higher staff:",
        color=discord.Color.from_rgb(58, 48, 35),
    )
    embed.add_field(name="b!ticketpanel", value="Posts the ticket panel in the configured tickets channel.", inline=False)
    embed.add_field(name="b!blacklist @user", value="Opens the blacklist dropdown for the selected member.", inline=False)
    embed.add_field(name="b!help", value="Shows this command list.", inline=False)
    embed.set_footer(text="BRAX • Higher Staff Only")
    await ctx.reply(embed=embed, mention_author=False)


@bot.tree.command(name="help", description="Show BRAX commands for higher staff.")
async def brax_slash_help_command(interaction: discord.Interaction):
    if not is_high_staff(interaction.user):
        await interaction.response.send_message(
            "You don't have permission to use BRAX commands. This is limited to higher staff.",
            ephemeral=True,
        )
        return
    embed = discord.Embed(
        title="BRAX Commands",
        description="Commands available to higher staff:",
        color=discord.Color.from_rgb(58, 48, 35),
    )
    embed.add_field(name="b!ticketpanel", value="Posts the ticket panel in the configured tickets channel.", inline=False)
    embed.add_field(name="b!blacklist @user", value="Opens the blacklist dropdown for the selected member.", inline=False)
    embed.add_field(name="b!help", value="Shows this command list in the server.", inline=False)
    embed.add_field(name="/help", value="Shows this command list as a private slash-command response.", inline=False)
    embed.set_footer(text="BRAX • Higher Staff Only")
    await interaction.response.send_message(embed=embed, ephemeral=True)


if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Check that Wispbyte's .env file is in the "
        "server's working directory and contains BOT_TOKEN=your_token."
    )

print("BRAX BUILD: b! prefix commands / higher-staff restriction")
bot.run(TOKEN)
