"""Discord integration"""
# Standard Library
import asyncio
import time

# Lutris Modules
from lutris.util.log import logger

try:
    from pypresence import Presence as PyPresence
    from pypresence.exceptions import PyPresenceException
except ImportError:
    PyPresence = None
    PyPresenceException = None


class DiscordPresence(object):

    """Provide rich presence integration with Discord for games"""

    def __init__(self):
        self.available = bool(PyPresence)
        self.game_name = ""
        self.runner_name = ""
        self.last_rpc = 0
        self.rpc_interval = 60
        self.presence_connected = False
        self.rpc_client = None
        self.client_id = None
        self.custom_game_name = ''
        self.show_runner = True
        self.custom_runner_name = ''
        self.rpc_enabled = True

    def connect(self):
        """Make sure we are actually connected before trying to send requests"""
        logger.debug("Ensuring connected.")
        if self.presence_connected:
            logger.debug("Already connected!")
        else:
            logger.debug("Creating Presence object.")
            self.rpc_client = PyPresence(self.client_id)
            try:
                logger.debug("Attempting to connect.")
                self.rpc_client.connect()
                self.presence_connected = True
            except (ConnectionError, FileNotFoundError):
                logger.error("Could not connect to Discord")
        return self.presence_connected

    def disconnect(self):
        """Ensure we are definitely disconnected and fix broken event loop from pypresence
        That method is a huge mess of non-deterministic bs and should be nuked from orbit.
        """
        logger.debug("Disconnecting from Discord")
        if self.rpc_client:
            try:
                self.rpc_client.close()
            except Exception as e:
                logger.exception("Unable to close Discord RPC connection: %s", e)
            if self.rpc_client.sock_writer is not None:
                try:
                    logger.debug("Forcefully closing sock writer.")
                    self.rpc_client.sock_writer.close()
                except Exception:
                    logger.exception("Sock writer could not be closed.")
            try:
                logger.debug("Forcefully closing event loop.")
                self.rpc_client.loop.close()
            except Exception:
                logger.debug("Could not close event loop.")
            try:
                logger.debug("Forcefully replacing event loop.")
                self.rpc_client.loop = None
                asyncio.set_event_loop(asyncio.new_event_loop())
            except Exception as e:
                logger.exception("Could not replace event loop: %s", e)
            try:
                logger.debug("Forcefully deleting RPC client.")
                self.rpc_client = None
            except Exception as ex:
                logger.exception(ex)
        self.rpc_client = None
        self.presence_connected = False

    def update_discord_rich_presence(self):
        """Dispatch a request to Discord to update presence"""
        if int(time.time()) - self.rpc_interval < self.last_rpc:
            logger.debug("Not enough time since last RPC")
            return
        if self.rpc_enabled:
            self.last_rpc = int(time.time())
            if not self.connect():
                return
            try:
                state_text = "via %s" % self.runner_name if self.show_runner else "  "
                logger.info("Attempting to update Discord status: %s, %s", self.game_name, state_text)
                self.rpc_client.update(details="Playing %s" % self.game_name, state=state_text,
                                       large_image="large_image", large_text="Using Lutris")
            except PyPresenceException as ex:
                logger.error("Unable to update Discord: %s", ex)

    def clear_discord_rich_presence(self):
        """Dispatch a request to Discord to clear presence"""
        if self.rpc_enabled:
            if self.connect():
                try:
                    logger.info('Attempting to clear Discord status.')
                    self.rpc_client.clear()
                except PyPresenceException as ex:
                    logger.error("Unable to clear Discord: %s", ex)
                    self.disconnect()
