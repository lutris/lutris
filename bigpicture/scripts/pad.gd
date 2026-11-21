## Controllers: what kind one is, and what its buttons are called on screen.
extends RefCounted

enum Style { NONE, XBOX, PLAYSTATION, NINTENDO }

## The buttons that are named on screen, by what they do here.
enum Use { ACCEPT, BACK, ALT, SEARCH, MENU, TAB_PREV, TAB_NEXT }

## The symbols on a PlayStation controller, which are drawn, not written.
const SYMBOLS := ["cross", "circle", "square", "triangle"]

const SONY := 0x054c
const NINTENDO := 0x057e


## Works out the kind of a controller from its vendor ID, where it has one,
## and from its name, which is all that Bluetooth may leave us with.
static func detect(name: String, vendor_id: int) -> Style:
	var lower := name.to_lower()

	for word in ["dualsense", "dualshock", "playstation", "ps3", "ps4", "ps5", "sony"]:
		if lower.contains(word):
			return Style.PLAYSTATION

	if vendor_id == SONY:
		return Style.PLAYSTATION

	for word in ["nintendo", "switch", "joy-con", "pro controller"]:
		if lower.contains(word):
			return Style.NINTENDO

	if vendor_id == NINTENDO:
		return Style.NINTENDO

	return Style.XBOX


## The kind of the controller connected as the device given.
static func style_of(device: int) -> Style:
	if not Input.get_connected_joypads().has(device):
		return Style.NONE

	var info := Input.get_joy_info(device)
	var vendor := int(info.get("vendor_id", 0)) if info.has("vendor_id") else 0

	return detect(Input.get_joy_name(device), vendor)


## What a button is called on a kind of controller: its letter or name, or
## one of SYMBOLS. Buttons are told apart by where they are, so the bottom
## one accepts on every controller, and only the names differ.
static func glyph(style: Style, use: Use) -> String:
	match style:
		Style.PLAYSTATION:
			return ["cross", "circle", "square", "triangle", "OPTIONS", "L1", "R1"][use]
		Style.NINTENDO:
			# Nintendo's letters are the other way round from Xbox's.
			return ["B", "A", "Y", "X", "+", "L", "R"][use]

	return ["A", "B", "X", "Y", "MENU", "LB", "RB"][use]
