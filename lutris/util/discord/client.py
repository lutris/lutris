from pypresence import Presence

from lutris.util.discord.base import DiscordRichPresenceBase
from lutris.util.discord.games import GAMES_IDS
from lutris.util.log import logger


class DiscordRichPresenceClient(DiscordRichPresenceBase):
    playing: str | None  # Identifier of the running game
    rpc: Presence | None  # Presence Object

    def __init__(self):
        self.playing = None
        self.rpc = None

    def update(self, game_identifier: str) -> None:
        logger.debug(f"Updating Discord RPC to game {game_identifier}")
        if game_identifier not in GAMES_IDS:
            logger.error(f"Discord APP ID for {game_identifier} not found")
            return
        elif self.rpc is not None:
            # Clear the old RPC before creating a new one
            self.clear()

        # Create a new Presence object with the desired app id
        self.rpc = Presence(GAMES_IDS[game_identifier])
        # Connect to discord endpoint
        self.rpc.connect()
        # Trigger an update making the status available
        self.rpc.update()
        # Internal Reference for Game Identifier
        self.playing = game_identifier

    def clear(self) -> None:
        logger.debug("Clearing Discord RPC")
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
