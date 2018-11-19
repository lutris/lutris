from lutris import pga
from lutris.config import LutrisConfig, make_game_config_id


def migrate():
    games = pga.get_games(filter_installed=True)
    for game_info in games:
        if game_info["runner"] != "steam" or game_info["configpath"]:
            continue
        slug = game_info["slug"]
        config_id = make_game_config_id(slug)

        # Add configpath to db
        pga.add_or_update(
            name=game_info["name"], runner="steam", slug=slug, configpath=config_id
        )

        # Add appid to config
        game_config = LutrisConfig(runner_slug="steam", game_config_id=config_id)
        game_config.raw_game_config.update({"appid": str(game_info["steamid"])})
        game_config.save()
