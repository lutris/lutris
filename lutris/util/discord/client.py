import typing as ty

from pypresence import Presence

from lutris.util.discord.base import DiscordRichPresenceBase


class DiscordRichPresenceClient(DiscordRichPresenceBase):
    rpc: ty.Optional[Presence]  # Presence Object

    def __init__(self):
        self.playing = None
        self.rpc = None

    def update(self, discord_id: str) -> None:
        if self.rpc is not None:
            # Clear the old RPC before creating a new one
            self.clear()

        # Create a new Presence object with the desired app id
        self.rpc = Presence(discord_id)
        # Connect to discord endpoint
        self.rpc.connect()
        # Trigger an update making the status available
        self.rpc.update()

    def clear(self) -> None:
        if self.rpc is None:
            # Skip already deleted rpc
            return
        # Clear and Close Presence connection
        self.rpc.clear()
        self.rpc.close()
        # Clear Presence Object
        self.rpc = None
        # Clear Internal Reference
        self.playing = None
