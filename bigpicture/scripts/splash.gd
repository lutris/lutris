## The opening animation: the Lutris otter rolls in around its ball and the
## name appears under it; then, in one clean cut, the interface is there,
## having got itself ready underneath in the meantime.
extends RefCounted

const Ui := preload("res://scripts/ui.gd")

## How long the icon takes to roll in, when the name starts to appear, and
## when it is all over.
const ROLL_SECONDS := 0.9
const NAME_AT := 0.5
const END_AT := 2.3

var _icon: Texture2D
var _glow: Texture2D
## When the animation began, once it has.
var _started := -1.0


func _init() -> void:
	var image := Image.new()
	if image.load_png_from_buffer(FileAccess.get_file_as_bytes("res://assets/lutris.png")) == OK:
		image.generate_mipmaps()
		_icon = ImageTexture.create_from_image(image)

	# The ball's glow: bright in the middle, fading to nothing at the rim.
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 1.0])
	gradient.colors = PackedColorArray([Ui.alpha(Ui.ACCENT, 0.3), Ui.alpha(Ui.ACCENT, 0.0)])

	var glow := GradientTexture2D.new()
	glow.gradient = gradient
	glow.fill = GradientTexture2D.FILL_RADIAL
	glow.fill_from = Vector2(0.5, 0.5)
	glow.fill_to = Vector2(1.0, 0.5)
	glow.width = 256
	glow.height = 256
	_glow = glow


static func smooth(x: float) -> float:
	x = clampf(x, 0.0, 1.0)

	return x * x * (3.0 - 2.0 * x)


## Eases out, going a little too far and coming back.
static func overshoot(x: float) -> float:
	x = clampf(x, 0.0, 1.0) - 1.0

	return 1.0 + 2.70158 * x * x * x + 1.70158 * x * x


## Where everything is, a time into the animation: how solid the icon is,
## how far it has still to turn, its scale, and how far the name has appeared.
static func pose(seconds: float) -> Dictionary:
	var roll := 1.0 - pow(1.0 - clampf(seconds / ROLL_SECONDS, 0.0, 1.0), 3.0)

	return {
		"icon": smooth(seconds / 0.4),
		"angle": (1.0 - roll) * deg_to_rad(-110.0),
		"scale": 0.55 + 0.45 * overshoot(seconds / 0.8),
		"name": smooth((seconds - NAME_AT) / 0.5),
	}


func _seconds(now: float) -> float:
	return now - _started if _started >= 0.0 else 0.0


## True while the animation is playing; what the user does then is not meant
## for the interface underneath, but cuts the animation short.
func blocks_input(now: float) -> bool:
	return _seconds(now) < END_AT


## Ends the animation at once.
func skip(now: float) -> void:
	_started = now - END_AT


## Draws the animation over everything else. False once it is over.
func draw(ci: CanvasItem, size: Vector2, u: float, now: float) -> bool:
	if _started < 0.0:
		_started = now

	var seconds := now - _started
	if seconds >= END_AT:
		return false

	var state := pose(seconds)
	var center := size / 2.0 - Vector2(0.0, 44.0 * u)
	var extent: float = 220.0 * u * state.scale

	ci.draw_rect(Rect2(Vector2.ZERO, size), Ui.BG)

	var glow: float = state.icon * (0.75 + 0.25 * sin(seconds * 2.4))
	var halo := Vector2(extent, extent) * 2.5
	ci.draw_texture_rect(_glow, Rect2(center - halo / 2.0, halo), false, Color(1, 1, 1, glow))

	if _icon != null:
		ci.draw_set_transform(center, state.angle, Vector2.ONE)
		ci.draw_texture_rect(_icon, Rect2(-extent / 2.0, -extent / 2.0, extent, extent), false, Color(1, 1, 1, state.icon))
		ci.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

	# The name, letter by letter so that it can be spaced out, rising into
	# place as it appears.
	var letters: Array = []
	var spacing := 13.0 * u
	var width := -spacing
	for letter in "LUTRIS":
		var laid = Ui.layout(letter, 44.0 * u, true)
		letters.append(laid)
		width += laid.get_size().x + spacing

	var x := size.x / 2.0 - width / 2.0
	var y: float = size.y / 2.0 + 104.0 * u + (1.0 - state.name) * 16.0 * u
	for laid in letters:
		Ui.draw_layout(ci, laid, Vector2(x, y), Ui.alpha(Ui.TEXT, state.name))
		x += laid.get_size().x + spacing

	return true
