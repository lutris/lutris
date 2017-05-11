from lutris.services.steam import sync_with_lutris as _sync_with_lutris


def sync_with_lutris():
    _sync_with_lutris(platform='windows')
