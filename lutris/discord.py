import asyncio
import time

try:
    from pypresence import Presence as PyPresence
except ImportError:
    PyPresence = None
try:
    from pypresence.exceptions import PyPresenceException
except ImportError:
    PyPresenceException = None

from lutris.util.log import logger


class Presence(object):
    """This class provides rich presence integration
       with Discord for games.
    """

    def __init__(self):
        if PyPresence is not None:
            logger.debug('Discord Rich Presence enabled')
            self.rich_presence_available = True
        else:
            logger.debug('Discord Rich Presence not available due to lack of pypresence')
            self.rich_presence_available = False
        self.last_rpc = 0
        self.rpc_interval = 60
        self.presence_connected = False
        self.rpc_client = None
        self.client_id = None
        self.custom_game_name = ''
        self.show_runner = True
        self.custom_runner_name = ''
        self.rpc_enabled = True

    def available(self):
        """Confirm that we can run Rich Presence functions"""
        return self.rich_presence_available

    def ensure_discord_connected(self):
        """Make sure we are actually connected before trying to send requests"""
        if not self.available():
            logger.debug("Discord Rich Presence not available due to lack of pypresence")
            return
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
            except Exception as e:
                logger.error("Unable to reach Discord.  Skipping update: %s", e)
                self.ensure_discord_disconnected()
        return self.presence_connected

    def ensure_discord_disconnected(self):
        """Ensure we are definitely disconnected and fix broken event loop from pypresence"""
        if not self.available():
            logger.debug("Discord Rich Presence not available due to lack of pypresence")
            return
        logger.debug("Ensuring disconnected.")
        if self.rpc_client is not None:
            try:
                self.rpc_client.close()
            except Exception as e:
                logger.error("Unable to close Discord RPC connection: %s", e)
            if self.rpc_client.sock_writer is not None:
                try:
                    logger.debug("Forcefully closing sock writer.")
                    self.rpc_client.sock_writer.close()
                except Exception:
                    logger.debug("Sock writer could not be closed.")
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
                logger.debug("Could not replace event loop: %s", e)
            try:
                logger.debug("Forcefully deleting RPC client.")
                del self.rpc_client
            except Exception:
                pass
        self.rpc_client = None
        self.presence_connected = False

    def update_discord_rich_presence(self):
        """Dispatch a request to Discord to update presence"""
        if not self.available():
            logger.debug("Discord Rich Presence not available due to lack of pypresence")
            return
        if int(time.time()) - self.rpc_interval < self.last_rpc:
            logger.debug("Not enough time since last RPC")
            return
        if self.rpc_enabled:
            logger.debug("RPC is enabled")
            self.last_rpc = int(time.time())
            connected = self.ensure_discord_connected()
            if not connected:
                return
            try:
                state_text = "via {}".format(self.runner_name) if self.show_runner else "  "
                logger.info("Attempting to update Discord status: %s, %s", self.game_name, state_text)
                self.rpc_client.update(details="Playing {}".format(self.game_name), state=state_text)
            except PyPresenceException as e:
                logger.error("Unable to update Discord: %s", e)
        else:
            logger.debug("RPC disabled")

    def clear_discord_rich_presence(self):
        """Dispatch a request to Discord to clear presence"""
        if not self.available():
            logger.debug("Discord Rich Presence not available due to lack of pypresence")
            return
        if self.rpc_enabled:
            connected = self.ensure_discord_connected()
            if connected:
                try:
                    logger.info('Attempting to clear Discord status.')
                    self.rpc_client.clear()
                except PyPresenceException as e:
                    logger.error("Unable to clear Discord: %s", e)
                    self.ensure_discord_disconnected()

