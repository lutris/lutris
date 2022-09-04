"""
Discord Rich Presence Base Objects

"""
from abc import ABCMeta


class DiscordRichPresenceBase(metaclass=ABCMeta):
    """
    Discord Rich Presence Interface

    """

    def update(self, discord_id: str) -> None:
        raise NotImplementedError()

    def clear(self) -> None:
        raise NotImplementedError()


class DiscordRPCNull(DiscordRichPresenceBase):
    """
    Null client for disabled Discord RPC
    """

    def update(self, discord_id: str) -> None:
        pass

    def clear(self) -> None:
        pass
