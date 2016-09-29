"""Synchronization of the game library with server and local data."""
from lutris import api, pga
from lutris.util import resources
from lutris.util.log import logger


def sync_missing_games(not_in_local, remote_library):
    """Get missing games in local library from remote library.

    :return: A set of ids of the added games
    """
    if not not_in_local:
        return set()

    missing = []
    for remote_game in remote_library:
        slug = remote_game['slug']
        if slug in not_in_local:
            logger.debug("Adding to local library: %s", slug)
            missing.append({
                'name': remote_game['name'],
                'slug': slug,
                'year': remote_game['year'],
                'updated': remote_game['updated'],
                'steamid': remote_game['steamid']
            })
    missing_ids = pga.add_games_bulk(missing)
    logger.debug("%d games added", len(missing))
    return set(missing_ids)


def sync_game_details(remote_library):
    """Update local game details,

    :return: A set of ids of the updated games.
    """
    if not remote_library:
        return set()
    updated = set()

    for remote_game in remote_library:
        slug = remote_game['slug']
        sync_required = False
        icon_sync_required = True
        local_game = pga.get_game_by_field(slug, 'slug')
        if not local_game:
            continue

        if local_game['updated'] and remote_game['updated'] > local_game['updated']:
            # The remote game's info is more recent than the local game
            sync_required = True
        else:
            for key in remote_game.keys():
                if key in local_game.keys() and remote_game[key] and not local_game[key]:
                    # Remote game has data that is missing from the local game.
                    logger.warning('Oh, that happened! ¯\_(ツ)_/¯')
                    sync_required = True
                    icon_sync_required = False
                    break

        if not sync_required:
            continue

        logger.debug("Syncing details for %s" % slug)
        game_id = pga.add_or_update(
            name=local_game['name'],
            runner=local_game['runner'],
            slug=slug,
            year=remote_game['year'],
            updated=remote_game['updated'],
            steamid=remote_game['steamid']
        )
        updated.add(game_id)

        # TODO: Only update if icon actually updated
        if icon_sync_required:
            if not local_game.get('has_custom_banner'):
                resources.download_icon(slug, 'banner', overwrite=True)
            if not local_game.get('has_custom_icon'):
                resources.download_icon(slug, 'icon', overwrite=True)

    if updated:
        logger.debug("%d games updated", len(updated))
    return updated


def sync_from_remote():
    """Synchronize from remote to local library.

    :return: The added and updated games (slugs)
    :rtype: tuple of sets, added games and updated games
    """
    local_library = pga.get_games()
    local_slugs = set([game['slug'] for game in local_library])

    try:
        remote_library = api.get_library()
    except Exception as ex:
        logger.error("Error while downloading the remote library: %s" % ex)
        remote_library = {}
    remote_slugs = set([game['slug'] for game in remote_library])

    missing_slugs = remote_slugs.difference(local_slugs)

    added = sync_missing_games(missing_slugs, remote_library)
    updated = sync_game_details(remote_library)
    return (added, updated)
