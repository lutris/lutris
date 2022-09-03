"""
Discord Rich Presence Loader

This will enable DiscordRichPresenceClient if pypresence is installed.
Otherwise, it will provide a dummy client that does nothing
"""


from lutris.util.discord.base import DiscordRPCNull

try:
    from lutris.util.discord.client import DiscordRichPresenceClient
except ImportError:
    # If PyPresence is not present, and ImportError will raise, so we provide dummy client
    client = DiscordRPCNull()
else:
    # PyPresence is present, so we provide the client
    client = DiscordRichPresenceClient()
