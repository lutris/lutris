## Lutris Big Picture: state, navigation and the screens.
##
## This is the interface only. Lutris starts it, feeds it the library and
## carries out what the user asks for (see link.gd).
extends Control

const Link := preload("res://scripts/link.gd")
const Library := preload("res://scripts/library.gd")
const Covers := preload("res://scripts/covers.gd")
const Pad := preload("res://scripts/pad.gd")
const Sounds := preload("res://scripts/sounds.gd")
const Layer := preload("res://scripts/layer.gd")
const Splash := preload("res://scripts/splash.gd")
const Ui := preload("res://scripts/ui.gd")

enum Tab { HOME, LIBRARY }

## Rows of the on-screen keyboard; the control characters stand for
## backspace, clear and done.
const KEY_ROWS := ["1234567890", "qwertyuiop", "asdfghjkl\b", "zxcvbnm \u0001\u0002"]
const OSK_BACKSPACE := "\b"
const OSK_CLEAR := "\u0001"
const OSK_DONE := "\u0002"

## What the desktop knows Lutris by: the name of its desktop file.
const APP_ID := "net.lutris.Lutris"

const MENU_ITEMS := 5
const MENU_SOUNDS := 1
const MENU_SPLASH := 2
const MENU_EXIT := 3

## Controller presses are ignored this long after the window regains focus,
## so the press that closed a game does not also act here.
const FOCUS_GRACE := 0.35
## How long the main loop sleeps between rounds, in microseconds: while
## something is going on, once nothing has for a moment, and while another
## window (a game, as a rule) has the focus. Sleeping longer is what keeps
## an idle interface from costing anything much.
const SLEEP_ACTIVE := 6900
const SLEEP_IDLE := 40000
const SLEEP_AWAY := 250000
## Nothing going on for this long counts as idle.
const IDLE_AFTER := 1.0

## A held direction repeats after this long, and then this often.
const REPEAT_DELAY := 0.38
const REPEAT_INTERVAL := 0.095
const STICK_PRESS := 0.6
const STICK_RELEASE := 0.4

var link := Link.new()
var library := Library.new()
var covers := Covers.new()
var sounds: Node
var splash: RefCounted

var strings := {}
## What a launching game is doing, by game ID.
var statuses := {}
var got_library := false
var debug_protocol := false
var splash_enabled := true

var tab := Tab.HOME
## The pages and menus open over the screen, the last one on top:
## {kind: detail, id, button}, {kind: menu, index}, {kind: keyboard, row, col}.
var overlays: Array[Dictionary] = []
## What the user last used: pad, keyboard or mouse.
var device := "pad"
var pad_style := Pad.Style.NONE
## What the mouse can point at, noted while drawing: [rect, hit].
var hits: Array = []
var toasts: Array[Dictionary] = []
var pending_sound := ""

var home_row := 0
var home_cols: Array[int] = []
var home_scroll_x: Array[float] = []
var home_target_x: Array[float] = []
var home_scroll_y := 0.0
var home_reveal := true

var filter_scroll := 0.0
var lib_on_filters := false
var lib_index := 0
var lib_cols := 7
var lib_rows_visible := 2
var lib_scroll := 0.0
var lib_target := 0.0
var lib_reveal := true

## Cover paths behind the previous and the current backdrop.
var backdrop := ["", ""]
var backdrop_since := 0.0
var backdrop_fade := 1.0

var now := 0.0
var draw_dt := 0.0
var u := 1.0
var _last_draw := 0.0
var _anims := {}
var _animating := false
var _shown_minute := -1
var _next_check := 0.0
var _focused_at := 0.0
var _stirred_at := 0.0

var _dpad := ""
var _stick := Vector2.ZERO
var _stick_dir := ""
var _held := ""
var _next_repeat := 0.0
var _triggers := [false, false]

var _chips: Control
var _rows: Control
var _grid: Control
var _front: Control
var _backdrop_shade: Texture2D
var _footer_shade: Texture2D


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	debug_protocol = args.has("--debug-protocol")
	splash_enabled = not args.has("--no-splash")
	if args.has("--windowed"):
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)

	if not link.open():
		printerr("This is the Big Picture interface of Lutris, which Lutris starts itself:")
		printerr("use the Big Picture button in the Lutris window, or run `lutris --big-picture`.")
		get_tree().quit(2)

		return

	link.received.connect(_on_message)
	link.closed.connect(func(): get_tree().quit())

	_set_window_identity()

	# Nothing here moves by physics, so the engine need not step any.
	PhysicsServer2D.set_active(false)
	PhysicsServer3D.set_active(false)

	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	_backdrop_shade = Ui.vertical_gradient([[0.0, Ui.alpha(Ui.BG, 0.35)], [1.0, Ui.alpha(Ui.BG, 0.94)]])
	_footer_shade = Ui.vertical_gradient([[0.0, Ui.alpha(Ui.BG, 0.0)], [0.53, Ui.BG], [1.0, Ui.BG]])

	_chips = _add_layer(_draw_chips, true)
	_rows = _add_layer(_draw_rows, true)
	_grid = _add_layer(_draw_grid, true)
	_front = _add_layer(_draw_front, false)

	sounds = Sounds.new()
	add_child(sounds)

	covers.loaded.connect(redraw)
	resized.connect(redraw)
	get_window().focus_entered.connect(func(): _focused_at = _time())
	Input.joy_connection_changed.connect(func(_device, _connected): _pick_pad())
	_pick_pad()

	if splash_enabled:
		splash = Splash.new()

	redraw()


## Gives the window Lutris's name and icon, in place of Godot's.
func _set_window_identity() -> void:
	get_window().title = "Lutris Big Picture"
	_set_plain_title.call_deferred()

	var icon := Image.new()
	if icon.load_png_from_buffer(FileAccess.get_file_as_bytes("res://assets/lutris.png")) == OK:
		icon.resize(256, 256, Image.INTERPOLATE_LANCZOS)
		DisplayServer.set_icon(icon)

	# On Wayland the project's name does it. On X11 the window says it is
	# "Godot_Engine", which desktops match to Godot before anything else,
	# unless it names its desktop file; Godot has no way to, but xprop has.
	if DisplayServer.get_name() == "X11":
		var window := str(DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE))
		for property in ["_KDE_NET_WM_DESKTOP_FILE", "_GTK_APPLICATION_ID"]:
			OS.create_process("xprop", ["-id", window, "-f", property, "8u", "-set", property, APP_ID])


## Godot's own builds for running projects add "(DEBUG)" to a window's
## title; setting it on the display server, once the window is up, does not.
func _set_plain_title() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

	DisplayServer.window_set_title("Lutris Big Picture")


func _exit_tree() -> void:
	Ui.release()


func _add_layer(painter: Callable, clips: bool) -> Control:
	var layer := Layer.new()
	layer.painter = painter
	layer.clip_contents = clips
	add_child(layer)

	return layer


func _time() -> float:
	return Time.get_ticks_msec() / 1000.0


## Notes that something is going on, so that the interface stays quick.
func stir() -> void:
	_stirred_at = _time()


## Sets how often the main loop comes round, by how much is going on.
func _pace() -> void:
	var sleep := SLEEP_ACTIVE
	if _held == "" and not _animating and splash == null and now - _stirred_at > IDLE_AFTER:
		sleep = SLEEP_IDLE if get_window().has_focus() else SLEEP_AWAY

	if sleep != OS.low_processor_usage_mode_sleep_usec:
		OS.low_processor_usage_mode_sleep_usec = sleep


## The translation of an interface string.
func t(text: String) -> String:
	return strings.get(text, text)


func redraw() -> void:
	stir()
	queue_redraw()
	for layer in [_chips, _rows, _grid, _front]:
		if layer != null:
			layer.queue_redraw()


func _process(_delta: float) -> void:
	now = _time()
	link.poll()
	_pace()

	if _held != "" and now >= _next_repeat:
		_next_repeat = now + REPEAT_INTERVAL
		_pad_action(_held)

	# The clock and the toasts are looked at once a second, which is often
	# enough for them and costs next to nothing.
	if now >= _next_check:
		_next_check = now + 1.0
		var minute: int = Time.get_time_dict_from_system().minute
		if minute != _shown_minute or toasts.any(func(toast): return toast.until <= now):
			redraw()

	if _animating or splash != null:
		_animating = false
		redraw()


# -------------------------------------------------------------------- data

func _on_message(message: Dictionary) -> void:
	match message.get("type", ""):
		"init":
			strings = message.get("strings", {})

			var config: Dictionary = message.get("sounds", {})
			sounds.configure(config.get("dirs", []), str(config.get("pack", "")))
		"library":
			_set_library(message.get("games", []))
		"game_state":
			var id := str(message.get("id", ""))
			var state := str(message.get("state", "stopped"))
			var status := str(message.get("status", ""))
			var index := library.index_of(id)
			if index >= 0:
				library.games[index].state = state

			if state == "stopped" or status.is_empty():
				statuses.erase(id)
			else:
				statuses[id] = status
		"error":
			sounds.play("error")
			toasts.append({"text": str(message.get("message", "")), "until": now + 9.0})
		"quit":
			get_tree().quit()
		"debug_action":
			if debug_protocol:
				# A test has no patience for the opening animation.
				splash = null
				device = "pad"
				handle_action(str(message.get("action", "")))
		"debug_screenshot":
			if debug_protocol:
				_screenshot(str(message.get("path", "")))

	redraw()


func _screenshot(path: String) -> void:
	# Frames are only drawn when asked for, so ask for each one waited on.
	for frame in 2:
		redraw()
		await RenderingServer.frame_post_draw

	get_viewport().get_texture().get_image().save_png(path)
	printerr("screenshot saved to ", path)


func _set_library(games: Array) -> void:
	var focused_home := ""
	var home_index := home_game()
	if home_index >= 0:
		focused_home = library.games[home_index].id

	var focused_lib := ""
	if lib_index < library.view.size():
		focused_lib = library.games[library.view[lib_index]].id

	library.set_games(games)
	got_library = true

	for id in statuses.keys():
		if library.index_of(id) < 0:
			statuses.erase(id)

	# A game that is gone takes its page with it.
	overlays = overlays.filter(func(overlay): return overlay.kind != "detail" or library.index_of(overlay.id) >= 0)

	var count := library.rows.size()
	home_row = mini(home_row, maxi(count - 1, 0))
	home_cols.resize(count)
	home_scroll_x.resize(count)
	home_target_x.resize(count)
	for row in count:
		var items: Array = library.rows[row].items
		home_cols[row] = mini(home_cols[row], items.size() - 1)
		if row == home_row:
			for col in items.size():
				if library.games[items[col]].id == focused_home:
					home_cols[row] = col

	home_reveal = true
	_build_view(focused_lib)


## Recomputes the games the library shows, keeping the focus on a game.
func _build_view(keep_id := "") -> void:
	lib_index = library.build_view(keep_id)
	if library.view.is_empty() and library.query.is_empty():
		lib_on_filters = true

	lib_reveal = true


func _refresh_view() -> void:
	var keep := ""
	if lib_index < library.view.size():
		keep = library.games[library.view[lib_index]].id

	_build_view(keep)


## The game focused on the home screen, as an index into the games, or -1.
func home_game() -> int:
	if home_row >= library.rows.size() or home_row >= home_cols.size():
		return -1

	var items: Array = library.rows[home_row].items
	var col := home_cols[home_row]

	return items[col] if col >= 0 and col < items.size() else -1


## The game the screen is about right now, which sets the backdrop.
func current_game() -> int:
	for depth in range(overlays.size() - 1, -1, -1):
		if overlays[depth].kind == "detail":
			return library.index_of(overlays[depth].id)

	if tab == Tab.HOME:
		return home_game()

	return library.view[lib_index] if lib_index < library.view.size() else -1


# ------------------------------------------------------------------- input

func _pick_pad() -> void:
	var pads := Input.get_connected_joypads()
	pad_style = Pad.style_of(pads[0]) if not pads.is_empty() else Pad.Style.NONE
	redraw()


func shows_pad_hints() -> bool:
	return device == "pad" and pad_style != Pad.Style.NONE


func _input(event: InputEvent) -> void:
	now = _time()

	# A stick at rest still reports its jitter, which is nothing going on.
	if not event is InputEventJoypadMotion or absf(event.axis_value) > STICK_RELEASE:
		stir()

	if event is InputEventJoypadButton:
		_pad_button(event)
	elif event is InputEventJoypadMotion:
		_pad_motion(event)
	elif event is InputEventKey:
		_key(event)
	elif event is InputEventMouseMotion:
		_mouse_moved(event.position)
	elif event is InputEventMouseButton:
		_mouse_button(event)


## A controller is read whether or not we have the focus, so what is pressed
## while a game is in front must not reach this interface.
func _pad_allowed() -> bool:
	return get_window().has_focus() and now - _focused_at >= FOCUS_GRACE


func _pad_action(action: String) -> void:
	if _pad_allowed():
		device = "pad"
		Input.mouse_mode = Input.MOUSE_MODE_HIDDEN
		handle_action(action)


func _pad_button(event: InputEventJoypadButton) -> void:
	var directions := {
		JOY_BUTTON_DPAD_UP: "up",
		JOY_BUTTON_DPAD_DOWN: "down",
		JOY_BUTTON_DPAD_LEFT: "left",
		JOY_BUTTON_DPAD_RIGHT: "right",
	}
	if directions.has(event.button_index):
		var direction: String = directions[event.button_index]
		if event.pressed:
			_dpad = direction
		elif _dpad == direction:
			_dpad = ""

		_update_held()

		return

	if not event.pressed:
		return

	# Whichever controller is being used is the one whose buttons get named.
	var style := Pad.style_of(event.device)
	if style != pad_style:
		pad_style = style
		redraw()

	var actions := {
		JOY_BUTTON_A: "accept",
		JOY_BUTTON_B: "back",
		JOY_BUTTON_X: "alt",
		JOY_BUTTON_Y: "search",
		JOY_BUTTON_START: "menu",
		JOY_BUTTON_GUIDE: "menu",
		JOY_BUTTON_LEFT_SHOULDER: "tab_prev",
		JOY_BUTTON_RIGHT_SHOULDER: "tab_next",
	}
	if actions.has(event.button_index):
		_pad_action(actions[event.button_index])


func _pad_motion(event: InputEventJoypadMotion) -> void:
	match event.axis:
		JOY_AXIS_LEFT_X:
			_stick.x = event.axis_value
		JOY_AXIS_LEFT_Y:
			_stick.y = event.axis_value
		JOY_AXIS_TRIGGER_LEFT, JOY_AXIS_TRIGGER_RIGHT:
			var side := 0 if event.axis == JOY_AXIS_TRIGGER_LEFT else 1
			var pulled := event.axis_value > 0.5
			if pulled and not _triggers[side]:
				_pad_action("page_up" if side == 0 else "page_down")

			_triggers[side] = pulled

			return
		_:
			return

	_stick_dir = stick_direction(_stick, _stick_dir)
	_update_held()


## The direction a stick points in, with some give so that it does not
## chatter around the threshold.
static func stick_direction(stick: Vector2, current: String) -> String:
	var threshold := STICK_RELEASE if current != "" else STICK_PRESS
	if absf(stick.x) < threshold and absf(stick.y) < threshold:
		return ""

	# Keep the current direction unless the other axis clearly dominates.
	var horizontal := absf(stick.x) > absf(stick.y)
	if current in ["left", "right"]:
		horizontal = absf(stick.x) * 1.3 > absf(stick.y)
	elif current != "":
		horizontal = absf(stick.x) > absf(stick.y) * 1.3

	if horizontal:
		return "right" if stick.x > 0.0 else "left"

	return "down" if stick.y > 0.0 else "up"


## Turns the held direction into a first press plus repeats.
func _update_held() -> void:
	var direction := _dpad if _dpad != "" else _stick_dir
	if direction == _held:
		return

	_held = direction
	if direction != "":
		_next_repeat = now + REPEAT_DELAY
		_pad_action(direction)


## Whether holding a key down repeats what it does: moving about does, and
## so does deleting; accepting, going back and the rest do not.
static func key_repeats(keycode: Key) -> bool:
	return keycode in [KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_PAGEUP, KEY_PAGEDOWN, KEY_BACKSPACE]


## What is open on top of the screen: detail, menu, keyboard, or nothing.
func _top_kind() -> String:
	return overlays[-1].kind if not overlays.is_empty() else ""


## Whether typing on a real keyboard goes into the search.
func typing_searches() -> bool:
	if overlays.is_empty():
		return tab == Tab.LIBRARY

	return _top_kind() == "keyboard"


func _key(event: InputEventKey) -> void:
	if not event.pressed:
		return

	redraw()

	var typing := typing_searches()
	var on_keyboard := _top_kind() == "keyboard"
	var command := event.ctrl_pressed or event.meta_pressed
	var action := ""

	match event.keycode:
		KEY_UP:
			action = "up"
		KEY_DOWN:
			action = "down"
		KEY_LEFT:
			action = "left"
		KEY_RIGHT:
			action = "right"
		KEY_ENTER, KEY_KP_ENTER:
			# With a real keyboard, Enter finishes the search.
			action = "back" if on_keyboard else "accept"
		KEY_SPACE:
			if not typing or library.query.is_empty():
				action = "accept"
		KEY_ESCAPE:
			action = "back"
		KEY_TAB:
			action = "tab_prev" if event.shift_pressed else "tab_next"
		KEY_PAGEUP:
			action = "page_up"
		KEY_PAGEDOWN:
			action = "page_down"
		KEY_F10:
			action = "menu"
		KEY_F11:
			if not event.echo:
				_toggle_fullscreen()

			return
		KEY_S:
			if command:
				action = "alt"
		KEY_F:
			if command:
				action = "search"
		KEY_Q:
			if command:
				get_tree().quit()

				return
		KEY_BACKSPACE:
			if typing and not library.query.is_empty():
				device = "keyboard"
				sounds.play("key")
				library.query = library.query.left(-1)
				_build_view()

			return

	if action != "":
		# Holding a key down moves on and on, but accepts once.
		if event.echo and not key_repeats(event.keycode):
			return

		device = "keyboard"
		Input.mouse_mode = Input.MOUSE_MODE_HIDDEN
		handle_action(action)

		return

	if typing and not command and event.unicode >= 32:
		_type(String.chr(event.unicode).to_lower())


func _type(character: String) -> void:
	# No leading or doubled spaces: they would match nothing useful.
	if character == " " and (library.query.is_empty() or library.query.ends_with(" ")):
		return

	device = "keyboard"
	sounds.play("key")
	library.query += character
	lib_on_filters = false
	_build_view()


func _toggle_fullscreen() -> void:
	var windowed := DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_WINDOWED
	var mode := DisplayServer.WINDOW_MODE_FULLSCREEN if windowed else DisplayServer.WINDOW_MODE_WINDOWED
	DisplayServer.window_set_mode(mode)


func _hit_at(point: Vector2):
	for index in range(hits.size() - 1, -1, -1):
		if hits[index][0].has_point(point):
			return hits[index][1]

	return null


func _mouse_moved(point: Vector2) -> void:
	redraw()
	device = "mouse"
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if _splash_blocks():
		return

	# Pointing at something focuses it.
	var hit = _hit_at(point)
	if hit != null:
		_focus_hit(hit, false)


func _mouse_button(event: InputEventMouseButton) -> void:
	if not event.pressed:
		return

	redraw()

	# A click counts only once the pointer is out and can be seen to be on
	# something; before that it just brings the pointer out.
	var pointer_shown := device == "mouse"
	device = "mouse"
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

	if _skips_splash() or not pointer_shown:
		return

	match event.button_index:
		MOUSE_BUTTON_WHEEL_UP:
			_scroll(-1.0)
		MOUSE_BUTTON_WHEEL_DOWN:
			_scroll(1.0)
		MOUSE_BUTTON_LEFT:
			var hit = _hit_at(event.position)
			if hit != null and _focus_hit(hit, true):
				handle_action("accept")


func _scroll(direction: float) -> void:
	if not overlays.is_empty():
		return

	if tab == Tab.LIBRARY:
		lib_target += direction * 120.0 * u
	elif home_row < home_target_x.size():
		home_target_x[home_row] += direction * 254.0 * u


## Moves the focus to what the mouse is on. Returns whether a click on it
## should go on to activate it.
func _focus_hit(hit: Dictionary, clicked: bool) -> bool:
	match hit.kind:
		"block":
			return false
		"dismiss":
			if clicked:
				handle_action("back")

			return false
		"tab":
			if clicked and tab != hit.tab:
				tab = hit.tab
				sounds.play("tab")

			return false
		"home":
			if hit.row == home_row:
				home_cols[hit.row] = hit.col

				return true

			# Clicking another row scrolls to it; a second click opens.
			if clicked:
				home_row = hit.row
				home_cols[hit.row] = hit.col
				home_reveal = true

			return false
		"lib":
			lib_on_filters = false
			lib_index = hit.index

			return true
		"filter":
			if clicked and hit.index != library.filter:
				sounds.play("move")
				library.filter = hit.index
				_build_view()

			return false
		"button":
			overlays[-1].button = hit.index

			return true
		"menu":
			overlays[-1].index = hit.index

			return true
		"key":
			overlays[-1].row = hit.row
			overlays[-1].col = hit.col

			return true

	return false


func _splash_blocks() -> bool:
	return splash != null and splash.blocks_input(now)


## True if the opening animation is still playing: then what the user just
## did is not passed on, and cuts the animation short instead.
func _skips_splash() -> bool:
	if _splash_blocks():
		splash.skip(now)

		return true

	return false


## Where the user is, as far as navigation goes. When an action leaves this
## unchanged, nothing happened and nothing is heard.
func nav_state() -> Array:
	var top := 0
	if not overlays.is_empty():
		var overlay := overlays[-1]
		match overlay.kind:
			"detail":
				top = overlay.button
			"menu":
				top = overlay.index
			"keyboard":
				top = overlay.row * 16 + overlay.col

	var col := home_cols[home_row] if home_row < home_cols.size() else 0

	return [
		tab, overlays.size(), home_row, col, lib_on_filters, lib_index,
		library.filter, library.sort, top, library.query.length(),
	]


func handle_action(action: String) -> void:
	if _skips_splash():
		return

	var before := nav_state()
	pending_sound = ""
	_dispatch(action)

	var after := nav_state()

	# What the pointer could hit was noted when the last frame was drawn.
	# Once the screen has changed, none of it is there any more.
	if after[0] != before[0] or after[1] != before[1]:
		hits.clear()

	var sound := pending_sound
	if sound == "" and after != before:
		match action:
			"accept":
				sound = "select"
			"back":
				sound = "back"
			"tab_prev", "tab_next":
				sound = "tab"
			"menu", "search":
				sound = "open" if after[1] > before[1] else "back"
			"alt":
				sound = "toggle"
			_:
				sound = "move"

	if sound != "":
		sounds.play(sound)

	redraw()


func _dispatch(action: String) -> void:
	if overlays.is_empty():
		_screen_action(action)

		return

	match overlays[-1].kind:
		"detail":
			_detail_action(action)
		"menu":
			_menu_action(action)
		"keyboard":
			_keyboard_action(action)


func _screen_action(action: String) -> void:
	match action:
		"tab_prev", "tab_next":
			tab = Tab.LIBRARY if tab == Tab.HOME else Tab.HOME
		"menu":
			overlays.append({"kind": "menu", "index": 0})
		"search":
			tab = Tab.LIBRARY
			lib_on_filters = false
			overlays.append({"kind": "keyboard", "row": 1, "col": 0})
		"back":
			if tab == Tab.LIBRARY and not library.query.is_empty():
				library.query = ""
				_refresh_view()
			elif tab == Tab.LIBRARY:
				tab = Tab.HOME
			else:
				overlays.append({"kind": "menu", "index": 0})
		_:
			if tab == Tab.HOME:
				_home_action(action)
			else:
				_library_action(action)


func _home_action(action: String) -> void:
	if home_row >= library.rows.size():
		return

	var last: int = library.rows[home_row].items.size() - 1
	var col := home_cols[home_row]
	match action:
		"left":
			home_cols[home_row] = maxi(col - 1, 0)
		"right":
			home_cols[home_row] = mini(col + 1, last)
		"page_up":
			home_cols[home_row] = maxi(col - 5, 0)
		"page_down":
			home_cols[home_row] = mini(col + 5, last)
		"up":
			home_row = maxi(home_row - 1, 0)
		"down":
			home_row = mini(home_row + 1, library.rows.size() - 1)
		"accept":
			_open_detail(home_game())

	home_reveal = true


func _library_action(action: String) -> void:
	if action == "alt":
		library.sort = (library.sort + 1) % 3 as Library.Sort
		_refresh_view()

		return

	if lib_on_filters:
		match action:
			"left":
				if library.filter > 0:
					library.filter -= 1
					_build_view()
			"right":
				if library.filter + 1 < library.filters.size():
					library.filter += 1
					_build_view()
			"down", "accept":
				if not library.view.is_empty():
					lib_on_filters = false
					lib_reveal = true

		return

	var count := library.view.size()
	if count == 0:
		if action == "up":
			lib_on_filters = true

		return

	var cols := maxi(lib_cols, 1)
	var page := maxi(lib_rows_visible, 1) * cols
	var index := lib_index
	match action:
		"left":
			if index % cols > 0:
				lib_index -= 1
		"right":
			if index % cols < cols - 1 and index + 1 < count:
				lib_index += 1
		"up":
			if index >= cols:
				lib_index -= cols
			else:
				lib_on_filters = true
		"down":
			if index + cols < count:
				lib_index += cols
			elif index / cols < (count - 1) / cols:
				# From the row above a short last row, land on its last game.
				lib_index = count - 1
		"page_up":
			lib_index = maxi(index - page, 0)
		"page_down":
			lib_index = mini(index + page, count - 1)
		"accept":
			_open_detail(library.view[index])

	lib_reveal = true


func _open_detail(index: int) -> void:
	if index >= 0:
		overlays.append({"kind": "detail", "id": library.games[index].id, "button": 0})


func _detail_action(action: String) -> void:
	var overlay := overlays[-1]
	var index := library.index_of(overlay.id)
	if index < 0:
		overlays.pop_back()

		return

	var game := library.games[index]
	match action:
		"left":
			overlay.button = 0
		"right":
			overlay.button = 1
		"accept":
			if overlay.button == 1:
				game.favorite = not game.favorite
				link.send({"type": "set_favorite", "id": game.id, "favorite": game.favorite})
				pending_sound = "toggle"
			elif game.state == "stopped":
				# Show the launch at once; Lutris corrects us if it fails.
				game.state = "launching"
				link.send({"type": "launch", "id": game.id})
				pending_sound = "launch"
			else:
				link.send({"type": "stop", "id": game.id})
				pending_sound = "select"
		"back":
			overlays.pop_back()
		"menu":
			overlays.append({"kind": "menu", "index": 0})


func _menu_action(action: String) -> void:
	var overlay := overlays[-1]
	match action:
		"up":
			overlay.index = maxi(overlay.index - 1, 0)
		"down":
			overlay.index = mini(overlay.index + 1, MENU_ITEMS - 1)
		"back", "menu":
			overlays.pop_back()
		"left", "right":
			if overlay.index == MENU_SOUNDS:
				_cycle_sounds(action == "right")
			elif overlay.index == MENU_SPLASH:
				_toggle_splash()
		"accept":
			match overlay.index:
				0:
					overlays.pop_back()
				MENU_SOUNDS:
					_cycle_sounds(true)
				MENU_SPLASH:
					_toggle_splash()
				MENU_EXIT:
					get_tree().quit()
				_:
					get_tree().quit(Link.EXIT_QUIT_LUTRIS)


## Switches to the next set of navigation sounds, and lets it be heard.
func _cycle_sounds(forward: bool) -> void:
	link.send({"type": "set_sound_pack", "pack": sounds.cycle(forward)})
	pending_sound = "select"


## Switches the opening animation on or off, for the next time.
func _toggle_splash() -> void:
	splash_enabled = not splash_enabled
	link.send({"type": "set_splash", "enabled": splash_enabled})
	pending_sound = "toggle"


func _keyboard_action(action: String) -> void:
	var overlay := overlays[-1]
	var row: int = overlay.row
	var col: int = overlay.col
	var width := func(of_row: int) -> int: return KEY_ROWS[of_row].length()

	match action:
		"left":
			col = width.call(row) - 1 if col == 0 else col - 1
		"right":
			col = 0 if col + 1 >= width.call(row) else col + 1
		"up":
			row = maxi(row - 1, 0)
		"down":
			row = mini(row + 1, KEY_ROWS.size() - 1)
		"accept":
			_press_key(KEY_ROWS[row][col])

			return
		"alt":
			_press_key(OSK_BACKSPACE)

			return
		"search":
			_press_key(" ")

			return
		"back", "menu":
			overlays.pop_back()

			return

	overlay.row = row
	overlay.col = mini(col, width.call(row) - 1)


func _press_key(key: String) -> void:
	match key:
		OSK_BACKSPACE:
			library.query = library.query.left(-1)
		OSK_CLEAR:
			library.query = ""
		OSK_DONE:
			overlays.pop_back()
			pending_sound = "back"

			return
		" ":
			if library.query.is_empty() or library.query.ends_with(" "):
				return

			library.query += " "
		_:
			library.query += key

	pending_sound = "key"
	_build_view()


# ----------------------------------------------------------------- drawing

## Eases a value from 0 to 1 and back as something gains and loses the focus.
func anim(key: String, on: bool, seconds: float) -> float:
	var target := 1.0 if on else 0.0
	var entry: Array = _anims.get(key, [target, now])
	var value: float = move_toward(entry[0], target, minf(now - entry[1], 0.05) / seconds)
	if value != target:
		_animating = true

	if _anims.size() > 4000:
		_anims.clear()

	_anims[key] = [value, now]

	return value


## Moves a value towards a target with an ease-out, asking for another frame
## until it gets there.
func approach(current: float, target: float) -> float:
	var distance := target - current
	if absf(distance) < 0.5:
		return target

	_animating = true

	return current + distance * (1.0 - exp(-draw_dt * 16.0))


func _hit(rect: Rect2, hit: Dictionary) -> void:
	hits.append([rect, hit])


func _draw() -> void:
	if _front == null:
		return

	now = _time()
	draw_dt = minf(now - _last_draw, 0.05)
	_last_draw = now
	u = maxf(minf(size.x / 1920.0, size.y / 1080.0), 0.1)

	covers.begin_frame()
	hits.clear()
	_layout()

	_update_backdrop()
	_paint_backdrop(self, 0.45 if tab == Tab.LIBRARY else 0.8)
	_draw_top_bar()

	if tab == Tab.HOME:
		_draw_hero()
	else:
		_draw_library_header()


## Places the parts of the screen that scroll, which are clipped to their place.
func _layout() -> void:
	var margin := 72.0 * u
	var library_shown := tab == Tab.LIBRARY

	_rows.visible = not library_shown
	_rows.position = Vector2(0, 358.0 * u)
	_rows.size = Vector2(size.x, size.y - 358.0 * u)

	_chips.visible = library_shown
	_chips.position = Vector2(0, 92.0 * u)
	_chips.size = Vector2(size.x - margin - 560.0 * u, 100.0 * u)

	_grid.visible = library_shown
	_grid.position = Vector2(0, 196.0 * u)
	_grid.size = Vector2(size.x, size.y - 92.0 * u - 196.0 * u)

	_front.position = Vector2.ZERO
	_front.size = size


func _update_backdrop() -> void:
	var index := current_game()
	var wanted: String = library.games[index].cover if index >= 0 else ""
	if wanted != backdrop[1]:
		backdrop = [backdrop[1], wanted]
		backdrop_since = now

	# The fade only starts once the new image is there to fade to.
	if backdrop[1] != "" and covers.lookup(backdrop[1]) == null:
		backdrop_since = now

	backdrop_fade = clampf((now - backdrop_since) / 0.4, 0.0, 1.0)
	if backdrop_fade < 1.0:
		_animating = true


## Paints the blurred cover of the current game over the whole screen.
func _paint_backdrop(ci: CanvasItem, brightness: float) -> void:
	var screen := Rect2(Vector2.ZERO, size)
	ci.draw_rect(screen, Ui.BG)

	var strengths := [1.0 - backdrop_fade, backdrop_fade]
	for slot in 2:
		if backdrop[slot] == "" or strengths[slot] <= 0.0:
			continue

		var cover = covers.lookup(backdrop[slot])
		if cover != null:
			var texture: Texture2D = cover.blurred
			var uv := Ui.cover_uv(cover.aspect, size)
			var source := Rect2(uv.position * texture.get_size(), uv.size * texture.get_size())
			var tint := Color(brightness, brightness, brightness, strengths[slot])
			ci.draw_texture_rect_region(texture, screen, source, tint)

	# Darker towards the bottom, where the covers are.
	ci.draw_texture_rect(_backdrop_shade, screen, false)


func _draw_top_bar() -> void:
	var y := 58.0 * u
	var x := 72.0 * u
	var logo := Ui.text(self, Vector2(x, y), "LUTRIS", 30.0 * u, Ui.ACCENT, true)
	x = logo.end.x + 56.0 * u

	var bumpers := shows_pad_hints() and overlays.is_empty()
	if bumpers:
		x = _bumper(Vector2(x, y), Pad.glyph(pad_style, Pad.Use.TAB_PREV)) + 22.0 * u

	for entry in [[Tab.HOME, "Home"], [Tab.LIBRARY, "Library"]]:
		var selected: bool = tab == entry[0]
		var rect := Ui.text(self, Vector2(x, y), t(entry[1]), 28.0 * u, Ui.TEXT if selected else Ui.DIM, true)
		if selected:
			var underline := Rect2(rect.position.x, rect.end.y + 8.0 * u, rect.size.x, 4.0 * u)
			Ui.fill(self, underline, 2.0 * u, Ui.ACCENT)

		_hit(rect.grow(16.0 * u), {"kind": "tab", "tab": entry[0]})
		x = rect.end.x + 44.0 * u

	if bumpers:
		_bumper(Vector2(x - 22.0 * u, y), Pad.glyph(pad_style, Pad.Use.TAB_NEXT))

	_draw_status(self)


func _bumper(pos: Vector2, label: String) -> float:
	var laid = Ui.layout(label, 16.0 * u, true)
	var rect := Rect2(pos.x, pos.y - 15.0 * u, laid.get_size().x + 20.0 * u, 30.0 * u)
	Ui.stroke(self, rect, 8.0 * u, 2.0 * u, Ui.DIM)
	Ui.draw_layout(self, laid, rect.get_center() - laid.get_size() / 2.0, Ui.DIM)

	return rect.end.x


## The clock, and what is running, in the top right corner.
func _draw_status(ci: CanvasItem) -> void:
	var y := 58.0 * u
	var time := Time.get_time_dict_from_system()
	_shown_minute = time.minute

	var clock_text := "%02d:%02d" % [time.hour, time.minute]
	var clock := Ui.text(ci, Vector2(size.x - 72.0 * u, y), clock_text, 28.0 * u, Ui.TEXT, false, Vector2(1, 0.5))

	for game in library.games:
		if game.state != "stopped":
			var laid = Ui.layout(game.name, 24.0 * u, false, 520.0 * u)
			var corner := Vector2(clock.position.x - 40.0 * u - laid.get_size().x, y - laid.get_size().y / 2.0)
			ci.draw_circle(Vector2(corner.x - 18.0 * u, y), 7.0 * u, Ui.GOOD)
			Ui.draw_layout(ci, laid, corner, Ui.GOOD)

			break


## The focused game of the home screen, large, above the rows.
func _draw_hero() -> void:
	var left := 72.0 * u
	if library.rows.is_empty():
		_draw_empty(self)

		return

	var index := home_game()
	if index < 0:
		return

	var game := library.games[index]
	var title = Ui.layout(game.name, 64.0 * u, true, size.x - 2.0 * left)
	Ui.draw_layout(self, title, Vector2(left, 128.0 * u), Ui.TEXT)

	var facts := [game.runner, game.platform].filter(func(fact): return not fact.is_empty())
	if game.year > 0:
		facts.append(str(game.year))

	Ui.text(self, Vector2(left, 236.0 * u), "  ·  ".join(facts), 26.0 * u, Ui.DIM)

	var x := left
	var y := 284.0 * u
	if game.state != "stopped":
		var state := t("Running" if game.state == "running" else "Launching…")
		x = Ui.text(self, Vector2(x, y), state, 24.0 * u, Ui.GOOD, true).end.x + 36.0 * u

	for entry in [["Play time", game.playtime_text], ["Last played", game.lastplayed_text]]:
		if entry[1].is_empty():
			continue

		var label := Ui.text(self, Vector2(x, y), t(entry[0]), 24.0 * u, Ui.DIM)
		var value := Ui.text(self, Vector2(label.end.x + 12.0 * u, y), entry[1], 24.0 * u, Ui.TEXT)
		x = value.end.x + 44.0 * u


func _draw_empty(ci: CanvasItem) -> void:
	var title := "No games found"
	var detail := ""
	if not got_library:
		title = "Loading library…"
	elif library.games.is_empty():
		title = "Your library is empty"
		detail = "Install games in Lutris to see them here."

	# Stay clear of the on-screen keyboard.
	var searching := _top_kind() == "keyboard"
	var center := Vector2(size.x / 2.0, 380.0 * u if searching else size.y / 2.0)
	Ui.text(ci, center, t(title), 40.0 * u, Ui.TEXT, true, Vector2(0.5, 0.5))
	if detail != "":
		Ui.text(ci, center + Vector2(0, 60.0 * u), t(detail), 26.0 * u, Ui.DIM, false, Vector2(0.5, 0.5))


## The rows of the home screen, which scroll beneath the focused game.
func _draw_rows(ci: CanvasItem) -> void:
	var margin := 72.0 * u
	var tile := Vector2(228.0, 304.0) * u
	var step := tile.x + 26.0 * u
	var pitch := tile.y + 96.0 * u
	var rows_top := 372.0 * u
	var visible_width := size.x - 2.0 * margin
	var clip := Rect2(ci.position, ci.size)

	home_scroll_y = approach(home_scroll_y, home_row * pitch)

	for row in library.rows.size():
		var y := rows_top + row * pitch - home_scroll_y
		if y > size.y or y + pitch < clip.position.y:
			continue

		var focused_row := row == home_row
		var title: String = t(library.rows[row].title)
		Ui.text(ci, Vector2(margin, y + 14.0 * u), title, 24.0 * u, Ui.TEXT if focused_row else Ui.DIM, true)

		var items: Array = library.rows[row].items
		var col := home_cols[row]
		var max_scroll := maxf(items.size() * step - 26.0 * u - visible_width, 0.0)
		var target := home_target_x[row]
		if focused_row and home_reveal:
			var tile_left := col * step
			target = maxf(minf(target, tile_left), tile_left + tile.x - visible_width)

		target = clampf(target, 0.0, max_scroll)
		home_target_x[row] = target
		home_scroll_x[row] = approach(home_scroll_x[row], target)

		var scroll := home_scroll_x[row]
		var tiles_top := y + 48.0 * u
		var first := maxi(int(floor((scroll - margin) / step)), 0)
		var focused_rect := Rect2()
		for item in range(first, items.size()):
			var rect := Rect2(Vector2(margin + item * step - scroll, tiles_top), tile)
			if rect.position.x > size.x:
				break

			var focused := focused_row and item == col and overlays.is_empty()
			var focus := anim("home/%d/%d" % [row, item], focused, 0.12)

			# The focused tile is drawn last, so it overlaps its neighbours.
			if focused:
				focused_rect = rect
			else:
				Ui.game_tile(ci, covers, library.games[items[item]], rect, focus, u)

			if rect.intersects(clip):
				_hit(rect.intersection(clip), {"kind": "home", "row": row, "col": item})

		if focused_rect.has_area():
			var focus := anim("home/%d/%d" % [row, col], true, 0.12)
			Ui.game_tile(ci, covers, library.games[items[col]], focused_rect, focus, u)

	home_reveal = false


## Right of the filters: how many games, and their order.
func _draw_library_header() -> void:
	var sort: String = ["Sorted by name", "Sorted by last played", "Sorted by play time"][library.sort]
	var summary := "%s  ·  %s" % [t("%d games").replace("%d", str(library.view.size())), t(sort)]
	Ui.text(self, Vector2(size.x - 72.0 * u, 142.0 * u), summary, 22.0 * u, Ui.DIM, false, Vector2(1, 0.5))

	if library.view.is_empty():
		_draw_empty(self)


## The search, then the filters, in a row that scrolls sideways.
func _draw_chips(ci: CanvasItem) -> void:
	var left := 72.0 * u
	var y := 142.0 * u
	var height := 50.0 * u
	var clip := Rect2(ci.position, ci.size)
	var x := left - filter_scroll
	var searching := _top_kind() == "keyboard"

	if searching or not library.query.is_empty():
		var laid = Ui.layout("%s: %s" % [t("Search"), library.query], 22.0 * u, true)
		var rect := Rect2(x, y - height / 2.0, laid.get_size().x + 44.0 * u, height)
		Ui.fill(ci, rect, height / 2.0, Ui.ACCENT)
		Ui.draw_layout(ci, laid, Vector2(rect.position.x + 22.0 * u, y - laid.get_size().y / 2.0), Ui.BG)
		x = rect.end.x + 14.0 * u

	var selected_span := Vector2.ZERO
	for index in library.filters.size():
		var chosen := library.filters[index]
		var label: String = chosen.name
		if chosen.kind == "all":
			label = t("All games")
		elif chosen.kind == "favorites":
			label = t("Favorites")

		var selected := index == library.filter
		var laid = Ui.layout(label, 22.0 * u, false)
		var rect := Rect2(x, y - height / 2.0, laid.get_size().x + 44.0 * u, height)
		Ui.fill(ci, rect, height / 2.0, Ui.TEXT if selected else Ui.alpha(Ui.PANEL_HI, 0.85))
		Ui.draw_layout(
			ci, laid, Vector2(rect.position.x + 22.0 * u, y - laid.get_size().y / 2.0), Ui.BG if selected else Ui.TEXT
		)

		if selected and lib_on_filters and overlays.is_empty():
			Ui.stroke(ci, rect.grow(7.0 * u), height / 2.0 + 7.0 * u, 3.0 * u, Ui.ACCENT)

		if selected:
			selected_span = Vector2(rect.position.x, rect.end.x) + Vector2(filter_scroll, filter_scroll)

		if rect.intersects(clip):
			_hit(rect.intersection(clip), {"kind": "filter", "index": index})

		x = rect.end.x + 14.0 * u

	# Keep the selected filter in view.
	var room := clip.end.x - 24.0 * u
	var target := minf(maxf(filter_scroll, selected_span.y - room), selected_span.x - left)
	filter_scroll = approach(filter_scroll, maxf(target, 0.0))


## The library's grid: as many columns as fit, spread over the full width.
func _draw_grid(ci: CanvasItem) -> void:
	if library.view.is_empty():
		return

	var margin := 72.0 * u
	var tile := Vector2(216.0, 288.0) * u
	var width := size.x - 2.0 * margin
	var cols := maxi(int(floor((width + 26.0 * u) / (tile.x + 26.0 * u))), 1)
	var gap := (width - cols * tile.x) / (cols - 1) if cols > 1 else 0.0
	var pitch := tile.y + 72.0 * u
	var top := 214.0 * u
	var bottom := size.y - 92.0 * u
	var height := bottom - top
	var rows := ceili(float(library.view.size()) / cols)
	var clip := Rect2(ci.position, ci.size)

	if cols != lib_cols:
		lib_cols = cols
		lib_reveal = true

	lib_rows_visible = maxi(int(floor(height / pitch)), 1)

	if lib_reveal:
		# Scroll by whole rows, so no row is left cut in half.
		var row := lib_index / cols
		var first := int(round(lib_target / pitch))
		first = maxi(mini(first, row), row + 1 - lib_rows_visible)
		lib_target = first * pitch
		lib_reveal = false

	var max_scroll := maxf(rows * pitch - height, 0.0)
	lib_target = clampf(lib_target, 0.0, max_scroll)
	lib_scroll = approach(lib_scroll, lib_target)

	var first_row := maxi(int(floor(lib_scroll / pitch)), 0)
	var last_row := mini(ceili((lib_scroll + height) / pitch), rows)
	var grid_focused := not lib_on_filters and overlays.is_empty()
	var focused_rect := Rect2()
	for row in range(first_row, last_row):
		for col in cols:
			var index := row * cols + col
			if index >= library.view.size():
				break

			var game := library.games[library.view[index]]
			var rect := Rect2(Vector2(margin + col * (tile.x + gap), top + row * pitch - lib_scroll), tile)
			var focused := grid_focused and index == lib_index
			var focus := anim("lib/" + game.id, focused, 0.12)
			if focused:
				focused_rect = rect
			else:
				Ui.game_tile(ci, covers, game, rect, focus, u)

			var name = Ui.layout(game.name, 20.0 * u, false, tile.x)
			var corner := Vector2(rect.get_center().x - name.get_size().x / 2.0, rect.end.y + 16.0 * u)
			Ui.draw_layout(ci, name, corner, Ui.TEXT if focused else Ui.DIM)

			if rect.intersects(clip):
				_hit(rect.intersection(clip), {"kind": "lib", "index": index})

	if focused_rect.has_area():
		var game := library.games[library.view[lib_index]]
		Ui.game_tile(ci, covers, game, focused_rect, anim("lib/" + game.id, true, 0.12), u)

	# A scroll position marker, when there is something to scroll.
	if max_scroll > 0.0:
		var track := Rect2(size.x - 30.0 * u, top, 6.0 * u, height)
		var thumb_height := maxf(height / (rows * pitch) * height, 40.0 * u)
		var thumb_top := top + (height - thumb_height) * clampf(lib_scroll / max_scroll, 0.0, 1.0)
		Ui.fill(ci, track, 3.0 * u, Ui.alpha(Ui.PANEL_HI, 0.5))
		Ui.fill(ci, Rect2(track.position.x, thumb_top, track.size.x, thumb_height), 3.0 * u, Ui.DIM)


## What lies over the screens: pages, menus, the hints, and the opening.
func _draw_front(ci: CanvasItem) -> void:
	var screen := Rect2(Vector2.ZERO, size)

	# Fade whatever scrolls beneath the button hints into the background.
	ci.draw_texture_rect(_footer_shade, Rect2(0, size.y - 190.0 * u, size.x, 190.0 * u), false)

	for overlay in overlays:
		# Everything beneath an overlay is out of the mouse's reach.
		hits.clear()
		_hit(screen, {"kind": "dismiss"})

		match overlay.kind:
			"detail":
				_draw_detail(ci, overlay)
			"menu":
				_draw_menu(ci, overlay)
			"keyboard":
				_draw_keyboard(ci, overlay)

	_draw_footer(ci)
	_draw_toasts(ci)

	if splash != null and not splash.draw(ci, size, u, now):
		splash = null


func _draw_footer(ci: CanvasItem) -> void:
	var pad := shows_pad_hints()
	var glyph := func(use: Pad.Use, key: String) -> String: return Pad.glyph(pad_style, use) if pad else key
	var hints: Array = []

	if overlays.is_empty():
		hints.append([glyph.call(Pad.Use.ACCEPT, "Enter"), "Select"])
		if tab == Tab.LIBRARY:
			hints.append([glyph.call(Pad.Use.BACK, "Esc"), "Back"])
			hints.append([glyph.call(Pad.Use.ALT, "Ctrl+S"), "Sort"])

		if pad:
			hints.append([Pad.glyph(pad_style, Pad.Use.SEARCH), "Search"])
		elif tab == Tab.LIBRARY:
			hints.append(["A-Z", "Search"])
		else:
			hints.append(["Tab", "Library"])

		hints.append([glyph.call(Pad.Use.MENU, "F10"), "Menu"])
	elif overlays[-1].kind == "keyboard":
		hints.append([glyph.call(Pad.Use.ACCEPT, "Enter"), "Select" if pad else "Done"])
		if pad:
			hints.append([Pad.glyph(pad_style, Pad.Use.ALT), "Delete"])
			hints.append([Pad.glyph(pad_style, Pad.Use.SEARCH), "Space"])
			hints.append([Pad.glyph(pad_style, Pad.Use.BACK), "Done"])
	else:
		hints.append([glyph.call(Pad.Use.ACCEPT, "Enter"), "Select"])
		hints.append([glyph.call(Pad.Use.BACK, "Esc"), "Back"])

	var x := size.x - 72.0 * u
	hints.reverse()
	for entry in hints:
		x = Ui.hint(ci, Vector2(x, size.y - 48.0 * u), entry[0], t(entry[1]), u) - 36.0 * u


## A game's page, over everything else.
func _draw_detail(ci: CanvasItem, overlay: Dictionary) -> void:
	var index := library.index_of(overlay.id)
	if index < 0:
		return

	_paint_backdrop(ci, 0.8)
	_hit(Rect2(Vector2.ZERO, size), {"kind": "block"})
	_draw_status(ci)

	var game := library.games[index]
	var on_top: bool = overlays[-1] == overlay
	var cover_rect := Rect2(170.0 * u, 190.0 * u, 465.0 * u, 620.0 * u)
	Ui.game_tile(ci, covers, game, cover_rect, 0.0, u)

	var x := cover_rect.end.x + 80.0 * u
	var width := size.x - 170.0 * u - x
	var y := cover_rect.position.y
	var title = Ui.layout(game.name, 56.0 * u, true, width, 2)
	Ui.draw_layout(ci, title, Vector2(x, y), Ui.TEXT)
	y += title.get_size().y + 34.0 * u

	var facts := [
		["Runner", game.runner],
		["Platform", game.platform],
		["Year", str(game.year) if game.year > 0 else ""],
		["Play time", game.playtime_text],
		["Last played", game.lastplayed_text],
	]
	for fact in facts:
		if fact[1].is_empty():
			continue

		Ui.text(ci, Vector2(x, y), t(fact[0]), 24.0 * u, Ui.DIM, false, Vector2.ZERO)
		Ui.draw_layout(ci, Ui.layout(fact[1], 24.0 * u, false, width - 230.0 * u), Vector2(x + 230.0 * u, y), Ui.TEXT)
		y += 46.0 * u

	var buttons_top := cover_rect.end.y - 84.0 * u
	var stopped: bool = game.state == "stopped"
	if not stopped:
		var status := t("Running" if game.state == "running" else "Launching…")
		if statuses.has(game.id):
			status += "  " + statuses[game.id]

		Ui.draw_layout(ci, Ui.layout(status, 24.0 * u, false, width), Vector2(x, buttons_top - 58.0 * u), Ui.GOOD)

	var play_rect := Rect2(x, buttons_top, 300.0 * u, 84.0 * u)
	var favorite_width := minf(440.0 * u, width - 328.0 * u)
	var favorite_rect := Rect2(play_rect.end.x + 28.0 * u, buttons_top, favorite_width, 84.0 * u)
	var buttons := [
		[play_rect, t("Play" if stopped else "Stop"), Ui.ACCENT if stopped else Ui.PANEL_HI, Ui.BG if stopped else Ui.TEXT],
		[favorite_rect, t("Remove from favorites" if game.favorite else "Add to favorites"), Ui.PANEL_HI, Ui.TEXT],
	]
	for index_of_button in buttons.size():
		var entry: Array = buttons[index_of_button]
		var focus := anim("detail/%d" % index_of_button, on_top and overlay.button == index_of_button, 0.1)
		Ui.button(ci, entry[0], entry[1], entry[2], entry[3], focus, u)
		_hit(entry[0], {"kind": "button", "index": index_of_button})


func _draw_menu(ci: CanvasItem, overlay: Dictionary) -> void:
	ci.draw_rect(Rect2(Vector2.ZERO, size), Ui.alpha(Color.BLACK, 0.6))

	var items := [
		t("Resume"),
		"%s: %s" % [t("Sounds"), t(sounds.current_pack().name)],
		"%s: %s" % [t("Start animation"), t("On" if splash_enabled else "Off")],
		t("Exit Big Picture"),
		t("Quit Lutris"),
	]
	var item_height := 84.0 * u
	var padding := 28.0 * u
	var panel_size := Vector2(600.0 * u, items.size() * item_height + 2.0 * padding)
	var panel := Rect2(size / 2.0 - panel_size / 2.0, panel_size)
	Ui.fill(ci, panel, 20.0 * u, Ui.PANEL)
	_hit(panel, {"kind": "block"})

	for index in items.size():
		var corner := panel.position + Vector2(padding, padding + index * item_height)
		var rect := Rect2(corner, Vector2(panel_size.x - 2.0 * padding, item_height - 10.0 * u))
		var focused: bool = index == overlay.index
		Ui.button(ci, rect, items[index], Ui.PANEL_HI if focused else Ui.PANEL, Ui.TEXT, anim("menu/%d" % index, focused, 0.1), u)
		_hit(rect, {"kind": "menu", "index": index})


func _draw_keyboard(ci: CanvasItem, overlay: Dictionary) -> void:
	var key := Vector2(104.0, 76.0) * u
	var gap := 10.0 * u
	var padding := 30.0 * u
	var panel_size := Vector2(10.0 * key.x + 9.0 * gap, KEY_ROWS.size() * (key.y + gap) - gap) + Vector2(padding, padding) * 2.0
	var panel := Rect2(size.x / 2.0 - panel_size.x / 2.0, size.y - 96.0 * u - panel_size.y, panel_size.x, panel_size.y)
	Ui.fill(ci, panel, 20.0 * u, Ui.alpha(Ui.PANEL, 0.97))
	_hit(panel, {"kind": "block"})

	var names := {" ": "Space", OSK_BACKSPACE: "Delete", OSK_CLEAR: "Clear", OSK_DONE: "Done"}
	for row in KEY_ROWS.size():
		for col in KEY_ROWS[row].length():
			var character: String = KEY_ROWS[row][col]
			var corner := panel.position + Vector2(padding + col * (key.x + gap), padding + row * (key.y + gap))
			var rect := Rect2(corner, key)
			var focused: bool = row == overlay.row and col == overlay.col
			var focus := anim("key/%d/%d" % [row, col], focused, 0.08)
			var label: String = t(names[character]) if names.has(character) else character.to_upper()

			var color := Ui.PANEL_HI
			var text_color := Ui.TEXT
			if character == OSK_DONE:
				color = Ui.ACCENT
				text_color = Ui.BG
			elif focused:
				color = Ui.TEXT
				text_color = Ui.BG

			var grown := Rect2(rect.position - rect.size * 0.025 * focus, rect.size * (1.0 + 0.05 * focus))
			Ui.fill(ci, grown, 10.0 * u, color)

			var laid = Ui.layout(label, (18.0 if label.length() > 1 else 28.0) * u, true, key.x - 8.0 * u)
			Ui.draw_layout(ci, laid, grown.get_center() - laid.get_size() / 2.0, text_color)
			Ui.focus_ring(ci, grown, 10.0 * u, u, focus)
			_hit(rect, {"kind": "key", "row": row, "col": col})


func _draw_toasts(ci: CanvasItem) -> void:
	toasts = toasts.filter(func(toast): return toast.until > now)

	var bottom := size.y - 110.0 * u
	for index in range(toasts.size() - 1, maxi(toasts.size() - 4, -1), -1):
		var laid = Ui.layout(toasts[index].text, 24.0 * u, false, 1100.0 * u, 3)
		var extent: Vector2 = laid.get_size() + Vector2(56.0, 36.0) * u
		var rect := Rect2(size.x / 2.0 - extent.x / 2.0, bottom - extent.y, extent.x, extent.y)
		Ui.fill(ci, rect, 16.0 * u, Ui.BAD)
		Ui.draw_layout(ci, laid, rect.position + Vector2(28.0, 18.0) * u, Ui.TEXT)
		bottom = rect.position.y - 14.0 * u
