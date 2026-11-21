## Navigation sounds.
##
## The sounds come in packs. A pack is a directory holding one audio file per
## sound, named after it (move.ogg, select.ogg, ...; Ogg Vorbis for
## preference, WAV and MP3 are understood too), and optionally a pack.json:
##
##     {"name": "My Pack", "volume": 0.8, "silent": ["move", "key"]}
##
## Lutris ships one pack, called default, and says where packs are and which
## is selected. A sound that a pack has no file for is taken from the default
## pack, unless the pack lists it as silent.
extends Node

## The sounds, by the name of their file in a pack.
const NAMES := ["move", "select", "back", "tab", "open", "key", "toggle", "launch", "error"]
const PACK_DEFAULT := "default"
const PACK_OFF := "off"
const EXTENSIONS := ["ogg", "wav", "mp3"]
## How many sounds can ring at once.
const VOICES := 6
## With nothing playing for this long, the audio thread is put to sleep.
const REST_AFTER := 1.5

## The packs to choose from: {id, name, dir}; dir is empty for no sounds.
var packs: Array[Dictionary] = [{"id": PACK_OFF, "name": "Off", "dir": ""}]
var current := PACK_OFF

## What to play for each sound: {stream, volume}. A sound not in here is silent.
var _sounds := {}
var _players: Array[AudioStreamPlayer] = []
var _next_player := 0
var _resting := false
var _played_at := 0.0


func _ready() -> void:
	for index in VOICES:
		var player := AudioStreamPlayer.new()
		add_child(player)
		_players.append(player)


## Looks for packs in the directories given (earlier ones win) and selects one.
func configure(dirs: Array, pack: String) -> void:
	var found: Array[Dictionary] = []
	for dir in dirs:
		for candidate in scan_packs(str(dir)):
			if not found.any(func(known): return known.id == candidate.id):
				found.append(candidate)

	# The default pack first, and no sounds last, after all that make some.
	found.sort_custom(func(a, b):
		if (a.id == PACK_DEFAULT) != (b.id == PACK_DEFAULT):
			return a.id == PACK_DEFAULT

		return a.name.to_lower() < b.name.to_lower())

	packs = found
	packs.append({"id": PACK_OFF, "name": "Off", "dir": ""})
	select(pack)


func current_pack() -> Dictionary:
	for pack in packs:
		if pack.id == current:
			return pack

	return packs[0]


## Switches to the next (or previous) pack and returns its ID.
func cycle(forward: bool) -> String:
	var index := packs.find(current_pack())
	var count := packs.size()
	select(packs[(index + (1 if forward else count - 1)) % count].id)

	return current


## Selects a pack: the default one if the one asked for is not there.
func select(id: String) -> void:
	current = packs[0].id
	for pack in packs:
		if pack.id == id:
			current = id

	_sounds.clear()

	var chosen := load_pack(current_pack().dir)
	var fallback := {}
	if current != PACK_DEFAULT and current != PACK_OFF:
		for pack in packs:
			if pack.id == PACK_DEFAULT:
				fallback = load_pack(pack.dir)

	for sound in NAMES:
		if chosen.has(sound):
			# Its own sound, or its own silence.
			if chosen[sound] != null:
				_sounds[sound] = chosen[sound]
		elif fallback.get(sound) != null:
			_sounds[sound] = fallback[sound]


## Godot's audio thread mixes and sends on silence for as long as it runs,
## which is most of what an idle interface costs. It takes the audio
## server's lock for each round, so holding that lock while there is nothing
## to hear stops it, and letting go starts it again.
func _process(_delta: float) -> void:
	if _resting or Time.get_ticks_msec() / 1000.0 - _played_at < REST_AFTER:
		return

	if _players.any(func(player): return player.playing):
		_played_at = Time.get_ticks_msec() / 1000.0

		return

	AudioServer.lock()
	_resting = true


func _wake() -> void:
	_played_at = Time.get_ticks_msec() / 1000.0
	if _resting:
		AudioServer.unlock()
		_resting = false


func _exit_tree() -> void:
	_wake()


func play(sound: String) -> void:
	if not _sounds.has(sound):
		return

	_wake()

	var entry: Dictionary = _sounds[sound]
	var player := _players[_next_player]
	_next_player = (_next_player + 1) % _players.size()
	player.stream = entry.stream
	player.volume_db = linear_to_db(maxf(entry.volume, 0.0001))
	player.play()


# ------------------------------------------------------------------- packs

## The packs in a directory: its subdirectories that hold a sound or a pack.json.
static func scan_packs(dir: String) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var listing := DirAccess.open(dir)
	if listing == null:
		return found

	for id in listing.get_directories():
		if id == PACK_OFF or id.begins_with("."):
			continue

		var path := dir.path_join(id)
		var manifest := read_manifest(path)
		var has_sounds := NAMES.any(func(sound): return not sound_file(path, sound).is_empty())
		if not has_sounds and manifest.is_empty():
			continue

		var name := str(manifest.get("name", "")).strip_edges()
		found.append({"id": id, "name": name if not name.is_empty() else id, "dir": path})

	found.sort_custom(func(a, b): return a.name.to_lower() < b.name.to_lower())

	return found


static func read_manifest(dir: String) -> Dictionary:
	var path := dir.path_join("pack.json")
	if not FileAccess.file_exists(path):
		return {}

	var manifest = JSON.parse_string(FileAccess.get_file_as_string(path))

	return manifest if manifest is Dictionary else {}


static func sound_file(dir: String, sound: String) -> String:
	for extension in EXTENSIONS:
		var path := dir.path_join("%s.%s" % [sound, extension])
		if FileAccess.file_exists(path):
			return path

	return ""


static func load_stream(path: String) -> AudioStream:
	match path.get_extension().to_lower():
		"wav":
			return AudioStreamWAV.load_from_file(path)
		"ogg":
			return AudioStreamOggVorbis.load_from_file(path)
		"mp3":
			return AudioStreamMP3.load_from_file(path)

	return null


## What a pack has for each sound: {stream, volume}, or null for a sound it
## silences. Sounds it says nothing about are left out.
static func load_pack(dir: String) -> Dictionary:
	var sounds := {}
	if dir.is_empty():
		return sounds

	var manifest := read_manifest(dir)
	var volume := clampf(float(manifest.get("volume", 1.0)), 0.0, 1.0)
	var silent: Array = manifest.get("silent", [])
	for sound in NAMES:
		if silent.has(sound):
			sounds[sound] = null

			continue

		var path := sound_file(dir, sound)
		if not path.is_empty():
			var stream := load_stream(path)
			if stream != null:
				sounds[sound] = {"stream": stream, "volume": volume}

	return sounds
