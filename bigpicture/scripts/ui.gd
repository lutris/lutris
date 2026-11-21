## Drawing helpers shared by the screens: colours, fonts, text and tiles.
##
## Everything draws onto a canvas item that is being drawn (`ci`), in screen
## coordinates, with sizes in units of `u`: one pixel on a 1080p screen.
extends RefCounted

const BG := Color8(11, 14, 20)
const PANEL := Color8(24, 29, 40)
const PANEL_HI := Color8(40, 47, 63)
const TEXT := Color8(240, 242, 246)
const DIM := Color8(150, 158, 172)
const ACCENT := Color8(255, 152, 0)
const GOOD := Color8(96, 208, 120)
const BAD := Color8(150, 40, 40)
const BADGE := Color8(214, 218, 226)

## Laid out text is kept, as shaping it is the costly part of drawing it.
const MAX_CACHED_TEXT := 600

static var _regular: SystemFont
static var _bold: SystemFont
static var _text_cache := {}
static var _boxes := {}


static func font(bold: bool) -> Font:
	if _regular == null:
		_regular = SystemFont.new()
		_regular.font_names = PackedStringArray(["sans-serif"])
		_regular.font_weight = 400

		_bold = SystemFont.new()
		_bold.font_names = PackedStringArray(["sans-serif"])
		_bold.font_weight = 700

	return _bold if bold else _regular


## Lets go of everything kept between frames; for when the interface closes.
static func release() -> void:
	_regular = null
	_bold = null
	_text_cache.clear()
	_boxes.clear()


static func alpha(color: Color, amount: float) -> Color:
	return Color(color.r, color.g, color.b, color.a * clampf(amount, 0.0, 1.0))


## Text laid out in at most `lines` lines of `width` (0 for no limit), ending
## in an ellipsis if it does not fit. A TextLine or a TextParagraph.
static func layout(text: String, size: float, bold: bool, width := 0.0, lines := 1):
	var px := maxi(int(round(size)), 1)
	var key := "%s|%d|%s|%d|%d" % [text, px, bold, int(width), lines]
	if _text_cache.has(key):
		return _text_cache[key]

	if _text_cache.size() > MAX_CACHED_TEXT:
		_text_cache.clear()

	var laid
	if lines <= 1:
		laid = TextLine.new()
		laid.add_string(text, font(bold), px)
		if width > 0.0:
			laid.width = width
			laid.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	else:
		laid = TextParagraph.new()
		laid.add_string(text, font(bold), px)
		laid.width = width
		laid.max_lines_visible = lines
		laid.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS

	_text_cache[key] = laid

	return laid


## Draws laid out text with its top left corner at a position.
static func draw_layout(ci: CanvasItem, laid, pos: Vector2, color: Color) -> void:
	laid.draw(ci.get_canvas_item(), pos, color)


## Draws one line of text. `anchor` says which point of the text `pos` is:
## x and y each from 0 (left, top) to 1 (right, bottom). Returns where it is.
static func text(
	ci: CanvasItem, pos: Vector2, string: String, size: float, color: Color, bold := false, anchor := Vector2(0, 0.5)
) -> Rect2:
	var laid = layout(string, size, bold)
	var extent: Vector2 = laid.get_size()
	var corner := pos - extent * anchor
	draw_layout(ci, laid, corner, color)

	return Rect2(corner, extent)


static func _box(radius: float, fill: Color, border := 0.0, border_color := Color.TRANSPARENT) -> StyleBoxFlat:
	var key := "%d|%s|%d|%s" % [int(radius), fill.to_html(), int(border * 10), border_color.to_html()]
	if _boxes.has(key):
		return _boxes[key]

	if _boxes.size() > 300:
		_boxes.clear()

	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.draw_center = fill.a > 0.0
	box.set_corner_radius_all(int(radius))
	box.corner_detail = 8
	box.anti_aliasing = true
	if border > 0.0:
		box.set_border_width_all(maxi(int(round(border)), 1))
		box.border_color = border_color

	_boxes[key] = box

	return box


static func fill(ci: CanvasItem, rect: Rect2, radius: float, color: Color) -> void:
	ci.draw_style_box(_box(radius, color), rect)


static func stroke(ci: CanvasItem, rect: Rect2, radius: float, width: float, color: Color) -> void:
	ci.draw_style_box(_box(radius, Color.TRANSPARENT, width, color), rect)


static func focus_ring(ci: CanvasItem, rect: Rect2, radius: float, u: float, strength: float) -> void:
	if strength <= 0.0:
		return

	var grown := rect.grow(7.0 * u)
	stroke(ci, grown, radius + 7.0 * u, 3.0 * u, alpha(Color.WHITE, strength))


static func _rounded_points(rect: Rect2, radius: float) -> PackedVector2Array:
	var points := PackedVector2Array()
	var r := minf(radius, minf(rect.size.x, rect.size.y) / 2.0)
	var centers := [
		rect.position + Vector2(r, r),
		Vector2(rect.end.x - r, rect.position.y + r),
		rect.end - Vector2(r, r),
		Vector2(rect.position.x + r, rect.end.y - r),
	]
	for corner in 4:
		for step in 5:
			var angle := PI + corner * PI / 2.0 + step * PI / 8.0
			points.append(centers[corner] + Vector2(cos(angle), sin(angle)) * r)

	return points


## Draws a texture into a rounded rectangle, cropped so that it fills it
## without distortion.
static func textured(ci: CanvasItem, rect: Rect2, radius: float, texture: Texture2D, aspect: float, tint: Color) -> void:
	var uv := cover_uv(aspect, rect.size)
	var points := _rounded_points(rect, radius)
	var uvs := PackedVector2Array()
	for point in points:
		uvs.append(uv.position + (point - rect.position) / rect.size * uv.size)

	ci.draw_colored_polygon(points, tint, uvs, texture)


## The part of a texture to show so that it fills a size without distortion.
static func cover_uv(image_aspect: float, size: Vector2) -> Rect2:
	var rect_aspect := size.x / maxf(size.y, 1.0)
	if image_aspect > rect_aspect:
		var width := rect_aspect / image_aspect

		return Rect2(0.5 - width / 2.0, 0.0, width, 1.0)

	var height := image_aspect / rect_aspect

	return Rect2(0.0, 0.5 - height / 2.0, 1.0, height)


## A stable colour for a game without a cover, from its name.
static func placeholder_color(name: String) -> Color:
	return Color.from_hsv((name.hash() % 360) / 360.0, 0.45, 0.32)


## Draws a game's cover in a rectangle, growing with `focus` (0 to 1).
static func game_tile(ci: CanvasItem, covers, game: Dictionary, rect: Rect2, focus: float, u: float) -> void:
	var grown := Rect2(rect.position - rect.size * 0.035 * focus, rect.size * (1.0 + 0.07 * focus))
	var radius := 10.0 * u

	if focus > 0.0:
		var shadow := StyleBoxFlat.new()
		shadow.draw_center = false
		shadow.set_corner_radius_all(int(radius))
		shadow.shadow_color = alpha(Color.BLACK, 0.6 * focus)
		shadow.shadow_size = int(30.0 * u)
		shadow.shadow_offset = Vector2(0, 10.0 * u)
		ci.draw_style_box(shadow, grown)

	var cover = covers.lookup(game.cover)
	if cover != null:
		textured(ci, grown, radius, cover.texture, cover.aspect, Color.WHITE)
	else:
		fill(ci, grown, radius, placeholder_color(game.name))

		# With no cover on file the name is all there is to show.
		if game.cover.is_empty():
			var name = layout(game.name, 22.0 * u, true, grown.size.x - 28.0 * u, 4)
			draw_layout(ci, name, grown.get_center() - name.get_size() / 2.0, TEXT)

	if game.state != "stopped":
		var center := grown.position + Vector2(22.0, 22.0) * u
		ci.draw_circle(center, 11.0 * u, alpha(Color.BLACK, 0.6))
		ci.draw_circle(center, 7.0 * u, GOOD)

	focus_ring(ci, grown, radius, u, focus)


## A rounded button with its label in the middle.
static func button(
	ci: CanvasItem, rect: Rect2, label: String, color: Color, text_color: Color, focus: float, u: float
) -> void:
	var grown := Rect2(rect.position - rect.size * 0.02 * focus, rect.size * (1.0 + 0.04 * focus))
	var radius := 12.0 * u
	fill(ci, grown, radius, color)

	var laid = layout(label, 26.0 * u, true, grown.size.x - 24.0 * u)
	draw_layout(ci, laid, grown.get_center() - laid.get_size() / 2.0, text_color)
	focus_ring(ci, grown, radius, u, focus)


## A button hint such as "(A) Select", ending at `right`. Returns the x where
## it starts, so the next one can go to its left.
static func hint(ci: CanvasItem, right: Vector2, glyph: String, label: String, u: float) -> float:
	var label_rect := text(ci, right, label, 22.0 * u, DIM, false, Vector2(1, 0.5))
	var height := 34.0 * u
	var badge_right := label_rect.position.x - 10.0 * u

	if glyph in ["cross", "circle", "square", "triangle"]:
		var center := Vector2(badge_right - height / 2.0, right.y)
		ci.draw_circle(center, height / 2.0, BADGE)
		pad_symbol(ci, center, glyph, 7.5 * u, 2.6 * u)

		return center.x - height / 2.0

	var laid = layout(glyph, 18.0 * u, true)
	var width := maxf(laid.get_size().x + 18.0 * u, height)
	var badge := Rect2(badge_right - width, right.y - height / 2.0, width, height)
	fill(ci, badge, height / 2.0, BADGE)
	draw_layout(ci, laid, badge.get_center() - laid.get_size() / 2.0, BG)

	return badge.position.x


## Draws one of the symbols on a PlayStation controller's buttons.
static func pad_symbol(ci: CanvasItem, center: Vector2, symbol: String, size: float, width: float) -> void:
	match symbol:
		"cross":
			var arm := size * 0.85
			ci.draw_line(center + Vector2(-arm, -arm), center + Vector2(arm, arm), BG, width, true)
			ci.draw_line(center + Vector2(-arm, arm), center + Vector2(arm, -arm), BG, width, true)
		"circle":
			ci.draw_arc(center, size, 0.0, TAU, 32, BG, width, true)
		"square":
			var side := size * 0.9
			ci.draw_rect(Rect2(center - Vector2(side, side), Vector2(side, side) * 2.0), BG, false, width)
		"triangle":
			var points := PackedVector2Array([
				center + Vector2(0.0, -size * 1.1),
				center + Vector2(size * 1.05, size * 0.72),
				center + Vector2(-size * 1.05, size * 0.72),
				center + Vector2(0.0, -size * 1.1),
			])
			ci.draw_polyline(points, BG, width, true)


## A texture that fades from one colour at the top to another at the bottom,
## by way of the stops given: [[offset, colour], ...].
static func vertical_gradient(stops: Array) -> GradientTexture2D:
	var gradient := Gradient.new()
	var offsets := PackedFloat32Array()
	var colors := PackedColorArray()
	for stop in stops:
		offsets.append(stop[0])
		colors.append(stop[1])

	gradient.offsets = offsets
	gradient.colors = colors

	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.width = 4
	texture.height = 256
	texture.fill_from = Vector2(0, 0)
	texture.fill_to = Vector2(0, 1)

	return texture
