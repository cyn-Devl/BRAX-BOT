import os
import asyncio
from collections import OrderedDict
from datetime import timedelta

from dotenv import load_dotenv
import discord

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

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
bot = discord.Client(intents=intents)

# In-memory only: message contents are not persisted across restarts.
message_cache = OrderedDict()


def shorten(value, limit=1024):
    value = str(value or "")
    return value if len(value) <= limit else value[:limit - 3] + "..."


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
    if not added and not removed:
        return

    entry = await find_audit_entry(
        after.guild,
        discord.AuditLogAction.member_role_update,
        after.id,
    )
    actor = entry.user if entry else None

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
    if message.guild is None or message.author.bot:
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


if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Check that Wispbyte's .env file is in the "
        "server's working directory and contains BOT_TOKEN=your_token."
    )

bot.run(TOKEN)
