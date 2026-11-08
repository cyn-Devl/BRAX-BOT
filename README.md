# BRAX

BRAX is a logging-only Discord bot built with Python and discord.py.

## Events logged
- Member joins and departures
- Kicks and bans, with moderator attribution when Discord's audit log is available
- All role additions and removals
- Enhanced logs for staff-role changes
- Deleted messages
- Edited messages

All logs go to the configured logging channel.

## Files
- main.py: bot source
- requirements.txt: Python dependency

## Environment variables
- BOT_TOKEN: Discord bot token; keep this secret
- LOG_CHANNEL_ID: logging channel; defaults to 1563997203377426623
- STAFF_ROLE_IDS: optional comma-separated list of exact staff role IDs

## Discord setup
Enable Server Members Intent and Message Content Intent in the Developer Portal.

Grant View Channels, Send Messages, Embed Links, and View Audit Log permissions. Read Message History is recommended.

## Limitations
Deleted message content is available only when BRAX has received and cached the message. Audit-log attribution depends on Discord making the entry available and granting BRAX View Audit Log permission. The message cache is in memory and clears when BRAX restarts.
