## Tests for the parts of the interface that can be tried without a screen.
##
## Run with: godot --headless --path bigpicture --script res://tests/run.gd
extends SceneTree

const Library := preload("res://scripts/library.gd")
const Pad := preload("res://scripts/pad.gd")
const Sounds := preload("res://scripts/sounds.gd")
const Splash := preload("res://scripts/splash.gd")
const Covers := preload("res://scripts/covers.gd")
const Ui := preload("res://scripts/ui.gd")
const Main := preload("res://scripts/main.gd")

var _failures := 0
var _checks := 0


func _init() -> void:
	for test in [
		_test_games_are_normalized,
		_test_home_rows,
		_test_filters_and_view,
		_test_sorting,
		_test_controllers_are_told_apart,
		_test_buttons_are_named_as_on_the_controller,
		_test_stick_direction,
		_test_held_keys_move_on_but_accept_once,
		_test_the_default_pack_has_every_sound,
		_test_sound_packs,
		_test_splash_pose,
		_test_cover_crop,
		_test_images_are_read_whatever_they_are_called,
	]:
		test.call()

	print("%d checks, %d failed" % [_checks, _failures])
	quit(1 if _failures > 0 else 0)


func check(condition: bool, what: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		printerr("FAILED: ", what)


func check_eq(actual, expected, what: String) -> void:
	check(actual == expected, "%s: got %s, expected %s" % [what, actual, expected])


func _game(id: int, name: String, extra := {}) -> Dictionary:
	var game := {"id": id, "name": name, "runner": "Wine"}
	game.merge(extra, true)

	return game


func _library() -> Library:
	var library := Library.new()
	library.set_games([
		_game(1, "Zelda", {"lastplayed": 300, "installed_at": 10, "favorite": true, "categories": ["RPG"]}),
		_game(2, "alan wake", {"lastplayed": 100, "installed_at": 30, "playtime": 9.0}),
		_game(3, "Mario", {"installed_at": 20, "runner": "Steam", "playtime": 2.0}),
		_game(4, "The Witcher", {"sortname": "Witcher", "lastplayed": 200, "categories": ["RPG"]}),
	])

	return library


func _names(library: Library, indexes: Array) -> Array:
	return indexes.map(func(index): return library.games[index].name)


func _test_games_are_normalized() -> void:
	var game := Library.normalized({"id": 7.0, "name": "A Game", "year": null, "cover": null, "state": "running"})

	check_eq(game.id, "7", "IDs are strings")
	check_eq(game.year, 0, "a missing year")
	check_eq(game.cover, "", "a missing cover")
	check_eq(game.state, "running", "the state")
	check_eq(game.categories, [], "missing categories")


func _test_home_rows() -> void:
	var library := _library()
	var titles := library.rows.map(func(row): return row.title)

	check_eq(titles, ["Recently played", "Favorites", "Recently added"], "the rows")
	check_eq(_names(library, library.rows[0].items), ["Zelda", "The Witcher", "alan wake"], "recent, newest first")
	check_eq(_names(library, library.rows[1].items), ["Zelda"], "favorites")
	check_eq(_names(library, library.rows[2].items), ["alan wake", "Mario", "Zelda"], "added, newest first")

	# With nothing played or added, there is still something to show.
	var bare := Library.new()
	bare.set_games([_game(1, "B"), _game(2, "a")])

	check_eq(bare.rows[0].title, "All games", "the fallback row")
	check_eq(_names(bare, bare.rows[0].items), ["a", "B"], "the fallback row, by name")


func _test_filters_and_view() -> void:
	var library := _library()
	var kinds := library.filters.map(func(filter): return "%s:%s" % [filter.kind, filter.name])

	check_eq(kinds, ["all:", "favorites:", "category:RPG", "runner:Steam", "runner:Wine"], "the filters")

	library.build_view()

	check_eq(_names(library, library.view), ["alan wake", "Mario", "The Witcher", "Zelda"], "all, by sort name")

	library.filter = 2
	library.build_view()

	check_eq(_names(library, library.view), ["The Witcher", "Zelda"], "one category")

	library.filter = 0
	library.query = " WAK "
	library.build_view()

	check_eq(_names(library, library.view), ["alan wake"], "a search, whatever its case")

	# The focus stays on a game that is still shown.
	library.query = ""

	check_eq(library.build_view("1"), 3, "where the kept game is")
	check_eq(library.build_view("gone"), 0, "a game that is not shown")

	# The selected filter survives a new library, if it is still there.
	library.filter = 2
	library.set_games([_game(9, "Other", {"categories": ["RPG"], "favorite": true})])

	check_eq(library.filters[library.filter].name, "RPG", "the filter kept")


func _test_sorting() -> void:
	var library := _library()

	library.sort = Library.Sort.RECENT
	library.build_view()

	check_eq(_names(library, library.view), ["Zelda", "The Witcher", "alan wake", "Mario"], "by last played")

	library.sort = Library.Sort.PLAYTIME
	library.build_view()

	check_eq(_names(library, library.view), ["alan wake", "Mario", "The Witcher", "Zelda"], "by play time")


func _test_controllers_are_told_apart() -> void:
	# Over Bluetooth a DualSense has a name but may have no vendor ID.
	check_eq(Pad.detect("DualSense Wireless Controller", 0), Pad.Style.PLAYSTATION, "a DualSense")
	check_eq(Pad.detect("Wireless Controller", 0x054c), Pad.Style.PLAYSTATION, "Sony by vendor")
	check_eq(Pad.detect("PS4 Controller", 0), Pad.Style.PLAYSTATION, "a DualShock")
	check_eq(Pad.detect("Nintendo Switch Pro Controller", 0), Pad.Style.NINTENDO, "a Pro Controller")
	check_eq(Pad.detect("Some Pad", 0x057e), Pad.Style.NINTENDO, "Nintendo by vendor")
	check_eq(Pad.detect("Xbox Wireless Controller", 0x045e), Pad.Style.XBOX, "an Xbox controller")
	check_eq(Pad.detect("Steam Deck", 0x28de), Pad.Style.XBOX, "everything else")


func _test_buttons_are_named_as_on_the_controller() -> void:
	check_eq(Pad.glyph(Pad.Style.PLAYSTATION, Pad.Use.ACCEPT), "cross", "PlayStation accept")
	check_eq(Pad.glyph(Pad.Style.PLAYSTATION, Pad.Use.BACK), "circle", "PlayStation back")
	check_eq(Pad.glyph(Pad.Style.PLAYSTATION, Pad.Use.TAB_PREV), "L1", "PlayStation bumper")
	check_eq(Pad.glyph(Pad.Style.XBOX, Pad.Use.ACCEPT), "A", "Xbox accept")
	check_eq(Pad.glyph(Pad.Style.NINTENDO, Pad.Use.ACCEPT), "B", "Nintendo accept")


func _test_stick_direction() -> void:
	check_eq(Main.stick_direction(Vector2(0.1, -0.2), ""), "", "at rest")
	check_eq(Main.stick_direction(Vector2(0.9, 0.2), ""), "right", "right")
	check_eq(Main.stick_direction(Vector2(-0.9, 0.2), ""), "left", "left")
	check_eq(Main.stick_direction(Vector2(0.1, -0.8), ""), "up", "up is negative")
	check_eq(Main.stick_direction(Vector2(0.1, 0.8), ""), "down", "down")

	# It holds its direction until clearly released, and on a near diagonal.
	check_eq(Main.stick_direction(Vector2(0.5, 0.0), "right"), "right", "held below the press threshold")
	check_eq(Main.stick_direction(Vector2(0.5, 0.0), ""), "", "not pressed that lightly")
	check_eq(Main.stick_direction(Vector2(0.3, 0.0), "right"), "", "released")
	check_eq(Main.stick_direction(Vector2(0.7, 0.75), "right"), "right", "no flip to vertical")
	check_eq(Main.stick_direction(Vector2(0.7, -0.75), "up"), "up", "no flip to horizontal")


func _test_held_keys_move_on_but_accept_once() -> void:
	for key in [KEY_LEFT, KEY_DOWN, KEY_PAGEDOWN, KEY_BACKSPACE]:
		check(Main.key_repeats(key), "key %d repeats" % key)

	for key in [KEY_ENTER, KEY_SPACE, KEY_ESCAPE, KEY_TAB, KEY_F10]:
		check(not Main.key_repeats(key), "key %d does not repeat" % key)


## Where the sound packs that Lutris ships are, in the source tree.
func _shipped_packs() -> String:
	return ProjectSettings.globalize_path("res://").path_join("../share/lutris/bigpicture/sounds").simplify_path()


func _test_the_default_pack_has_every_sound() -> void:
	var pack := Sounds.load_pack(_shipped_packs().path_join(Sounds.PACK_DEFAULT))

	for sound in Sounds.NAMES:
		check(pack.get(sound) != null, "the default pack has %s" % sound)

		if pack.get(sound) != null:
			var seconds: float = pack[sound].stream.get_length()

			check(seconds > 0.01 and seconds < 1.5, "%s lasts %s s" % [sound, seconds])
			check(pack[sound].volume < 0.5, "%s is played quietly" % sound)

	check_eq(Sounds.read_manifest(_shipped_packs().path_join(Sounds.PACK_DEFAULT)).get("name"), "Default", "its name")


func _test_sound_packs() -> void:
	var shipped := _shipped_packs().path_join(Sounds.PACK_DEFAULT)
	var dir := OS.get_cache_dir().path_join("lutris-bigpicture-test-%d" % OS.get_process_id())
	for pack in ["default", "zeta", "retro", "empty"]:
		DirAccess.make_dir_recursive_absolute(dir.path_join(pack))

	for sound in Sounds.NAMES:
		DirAccess.copy_absolute(shipped.path_join(sound + ".ogg"), dir.path_join("default/%s.ogg" % sound))

	DirAccess.copy_absolute(shipped.path_join("move.ogg"), dir.path_join("zeta/move.ogg"))
	DirAccess.copy_absolute(shipped.path_join("key.ogg"), dir.path_join("retro/select.ogg"))

	var manifest := FileAccess.open(dir.path_join("retro/pack.json"), FileAccess.WRITE)
	manifest.store_string('{"name": "Arcade", "volume": 0.5, "silent": ["key"]}')
	manifest.close()

	var found := Sounds.scan_packs(dir).map(func(pack): return "%s=%s" % [pack.id, pack.name])

	check_eq(found, ["retro=Arcade", "default=default", "zeta=zeta"], "packs are found, named and sorted")

	# Selecting falls back on the default pack, and cycles through to off.
	var sounds = Sounds.new()
	sounds.configure([dir], "gone")
	var ids: Array = sounds.packs.map(func(pack): return pack.id)

	check_eq(ids, ["default", "retro", "zeta", "off"], "the default pack first and off last")
	check_eq(sounds.current, Sounds.PACK_DEFAULT, "an unknown pack")
	check_eq(sounds._sounds.size(), Sounds.NAMES.size(), "the default pack plays everything")

	check_eq(sounds.cycle(true), "retro", "the next pack")
	check_eq(sounds._sounds["select"].volume, 0.5, "its own sound, at its volume")
	check(not sounds._sounds.has("key"), "a sound it silences")
	check_eq(sounds._sounds["move"].volume, 1.0, "a sound it leaves to the default pack")

	check_eq(sounds.cycle(true), "zeta", "and the next")
	check_eq(sounds.cycle(true), Sounds.PACK_OFF, "then off")
	check(sounds._sounds.is_empty(), "which plays nothing")
	check_eq(sounds.cycle(true), Sounds.PACK_DEFAULT, "and round again")
	check_eq(sounds.cycle(false), Sounds.PACK_OFF, "or backwards")

	# With no packs at all there is only silence, and no harm done.
	sounds.configure([dir.path_join("empty")], "")

	check_eq(sounds.current, Sounds.PACK_OFF, "nothing to select")

	sounds.play("move")
	sounds.free()
	OS.move_to_trash(dir)


func _test_splash_pose() -> void:
	var start := Splash.pose(0.0)

	check_eq(start.icon, 0.0, "nothing to see at first")
	check(start.angle < -1.5, "turned well away")
	check_eq(start.name, 0.0, "no name yet")

	# Well before the end it has arrived, and stays as it is.
	for seconds in [1.3, Splash.END_AT]:
		var arrived := Splash.pose(seconds)

		check_eq(arrived.icon, 1.0, "solid")
		check_eq(arrived.angle, 0.0, "upright")
		check(absf(arrived.scale - 1.0) < 0.0001, "at its size")
		check_eq(arrived.name, 1.0, "and named")

	# It only ever turns one way, and never past upright.
	var previous := -10.0
	for step in 21:
		var angle: float = Splash.pose(step * 0.05).angle

		check(angle >= previous and angle <= 0.0, "turning at %s" % (step * 0.05))
		previous = angle


func _test_cover_crop() -> void:
	var wide := Ui.cover_uv(2.0, Vector2(100, 200))

	check(absf(wide.size.x - 0.25) < 0.0001 and absf(wide.size.y - 1.0) < 0.0001, "a wide image is cropped at the sides")
	check(absf(wide.get_center().x - 0.5) < 0.0001, "about its middle")

	var tall := Ui.cover_uv(0.5, Vector2(200, 100))

	check(absf(tall.size.x - 1.0) < 0.0001 and absf(tall.size.y - 0.25) < 0.0001, "a tall image, top and bottom")

	var same := Ui.cover_uv(0.75, Vector2(300, 400))

	check(absf(same.size.x - 1.0) < 0.0001 and absf(same.size.y - 1.0) < 0.0001, "a matching image is shown whole")


func _test_images_are_read_whatever_they_are_called() -> void:
	# The icon is a PNG; under a JPEG's name it is still read as what it is.
	var bytes := FileAccess.get_file_as_bytes("res://assets/lutris.png")
	var path := OS.get_cache_dir().path_join("lutris-bigpicture-test-%d.jpg" % OS.get_process_id())
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_buffer(bytes)
	file.close()

	var image := Covers.read_image(path)

	check(image != null and image.get_width() == 768, "a PNG called .jpg")
	check(Covers.read_image(path + ".missing") == null, "a file that is not there")

	DirAccess.remove_absolute(path)
