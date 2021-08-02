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

    def connect(self):
        """Make sure we are actually connected before trying to send requests"""
        if not self.presence_connected:
            self.rpc_client = PyPresence(self.client_id)
            try:
                self.rpc_client.connect()
                self.presence_connected = True
            except (ConnectionError, FileNotFoundError):
                logger.error("Could not connect to Discord")
        return self.presence_connected

    def disconnect(self):
        """Ensure we are definitely disconnected and fix broken event loop from pypresence
        That method is a huge mess of non-deterministic bs and should be nuked from orbit.
        """
        if self.rpc_client:
            try:
                self.rpc_client.close()
            except Exception as e:
                logger.exception("Unable to close Discord RPC connection: %s", e)
            if self.rpc_client.sock_writer is not None:
                try:
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

        self.last_rpc = int(time.time())
        if not self.connect():
            return
        try:
            self.rpc_client.update(details="Playing %s" % self.game_name,
                                   large_image="large_image",
                                   large_text=self.game_name,
                                   small_image="small_image")
        except PyPresenceException as ex:
            logger.error("Unable to update Discord: %s", ex)

    def clear_discord_rich_presence(self):
        """Dispatch a request to Discord to clear presence"""
        if self.connect():
            try:
                self.rpc_client.clear()
            except PyPresenceException as ex:
                logger.error("Unable to clear Discord: %s", ex)
                self.disconnect()
