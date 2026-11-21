## The connection to Lutris.
##
## Lutris starts this project and owns the library, the games and the
## translations. It listens on a Unix socket, whose path it passes in
## $LUTRIS_BIGPICTURE_SOCKET, and the two exchange one JSON object per line.
##
## Leaving is not a message: we just quit, and the exit status tells Lutris
## whether to bring its window back (0) or to quit as well (EXIT_QUIT_LUTRIS).
extends RefCounted

signal received(message: Dictionary)
signal closed

## Exit status that asks Lutris to quit too.
const EXIT_QUIT_LUTRIS := 3

var _peer := StreamPeerUDS.new()
var _pending := PackedByteArray()
var _connected := false


## Connects to Lutris. False if there is nobody to connect to.
func open() -> bool:
	var path := OS.get_environment("LUTRIS_BIGPICTURE_SOCKET")
	if path.is_empty():
		return false

	return _peer.connect_to_host(path) == OK


func send(message: Dictionary) -> void:
	if not _connected:
		return

	_peer.put_data((JSON.stringify(message) + "\n").to_utf8_buffer())


## Reads what has arrived; call this every frame.
func poll() -> void:
	_peer.poll()
	var status := _peer.get_status()

	if status == StreamPeerSocket.STATUS_CONNECTED:
		if not _connected:
			_connected = true
			send({"type": "ready"})

		_read()
	elif status != StreamPeerSocket.STATUS_CONNECTING:
		if _connected or status == StreamPeerSocket.STATUS_ERROR:
			# Lutris has gone, or was never there.
			_connected = false
			closed.emit()


func _read() -> void:
	var available := _peer.get_available_bytes()
	if available <= 0:
		return

	var result := _peer.get_data(available)
	if result[0] != OK:
		return

	_pending.append_array(result[1])

	# A message is complete once its line is.
	while true:
		var end := _pending.find(10)
		if end < 0:
			break

		var line := _pending.slice(0, end).get_string_from_utf8()
		_pending = _pending.slice(end + 1)
		if line.strip_edges().is_empty():
			continue

		var message = JSON.parse_string(line)
		if message is Dictionary:
			received.emit(message)
		else:
			push_warning("Ignoring a bad message from Lutris")
