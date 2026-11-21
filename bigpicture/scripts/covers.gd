## Cover art. Images are decoded on worker threads and kept as textures only
## while they are on screen or were recently, so a library of thousands of
## games costs no more than the covers being looked at.
extends RefCounted

signal loaded

## Covers are never shown taller than this, so more is not kept.
const MAX_HEIGHT := 720
## How many covers to keep before dropping the least recently shown.
const MAX_CACHED := 320
## Requests waiting beyond this are for covers scrolled past, and dropped.
const MAX_QUEUED := 96
## How many covers are decoded at a time.
const WORKERS := 3

## path -> {texture, blurred, aspect, used}; texture is null while loading
## or if the file cannot be read.
var _slots := {}
var _queue: Array[String] = []
var _busy := 0
var _frame := 0


## Call once per frame drawn.
func begin_frame() -> void:
	_frame += 1
	if _slots.size() > MAX_CACHED:
		_evict()


## The cover at a path if it is loaded: {texture, blurred, aspect}. Otherwise
## it is requested and null is returned until it arrives.
func lookup(path: String):
	if path.is_empty():
		return null

	if not _slots.has(path):
		_slots[path] = {"texture": null, "blurred": null, "aspect": 1.0, "used": _frame, "loading": true}
		_queue.append(path)
		if _queue.size() > MAX_QUEUED:
			_slots.erase(_queue.pop_front())

		_start_next()

	var slot: Dictionary = _slots[path]
	slot.used = _frame

	return slot if slot.texture != null else null


func _start_next() -> void:
	# Newest first: what was asked for last is what is on screen now.
	while _busy < WORKERS and not _queue.is_empty():
		var path: String = _queue.pop_back()
		_busy += 1
		WorkerThreadPool.add_task(_decode.bind(path))


## Runs on a worker thread.
func _decode(path: String) -> void:
	var image := read_image(path)
	var blurred: Image = null
	if image != null:
		if image.get_height() > MAX_HEIGHT:
			var width := int(image.get_width() * float(MAX_HEIGHT) / image.get_height())
			image.resize(maxi(width, 1), MAX_HEIGHT, Image.INTERPOLATE_BILINEAR)

		# Shrunk to a few pixels and stretched back, it is a soft backdrop.
		blurred = image.duplicate()
		var height := clampi(int(24.0 * image.get_height() / image.get_width()), 8, 96)
		blurred.resize(24, height, Image.INTERPOLATE_CUBIC)
		blurred.resize(96, height * 4, Image.INTERPOLATE_CUBIC)

	_finish.call_deferred(path, image, blurred)


## Reads an image whatever its file is called: Lutris stores PNGs as .jpg.
static func read_image(path: String) -> Image:
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.size() < 12:
		return null

	var image := Image.new()
	var result := ERR_FILE_UNRECOGNIZED
	if bytes[0] == 0x89 and bytes[1] == 0x50:
		result = image.load_png_from_buffer(bytes)
	elif bytes[0] == 0xff and bytes[1] == 0xd8:
		result = image.load_jpg_from_buffer(bytes)
	elif bytes.slice(8, 12).get_string_from_ascii() == "WEBP":
		result = image.load_webp_from_buffer(bytes)

	if result != OK or image.is_empty():
		return null

	return image


func _finish(path: String, image: Image, blurred: Image) -> void:
	_busy -= 1
	_start_next()

	# A cover that was dropped while it loaded is simply forgotten.
	if _slots.has(path):
		var slot: Dictionary = _slots[path]
		slot.loading = false
		if image != null:
			slot.texture = ImageTexture.create_from_image(image)
			slot.blurred = ImageTexture.create_from_image(blurred)
			slot.aspect = float(image.get_width()) / image.get_height()

	loaded.emit()


func _evict() -> void:
	var idle: Array = []
	for path in _slots:
		var slot: Dictionary = _slots[path]
		if slot.used + 2 < _frame and not slot.loading:
			idle.append([slot.used, path])

	idle.sort()

	var excess := _slots.size() - MAX_CACHED * 3 / 4
	for entry in idle.slice(0, excess):
		_slots.erase(entry[1])
