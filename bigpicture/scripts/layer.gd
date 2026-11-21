## A part of the screen that is drawn by the main script, clipped to this
## control's rectangle if it is set to clip. Drawing is in screen coordinates.
extends Control

var painter: Callable


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS


func _draw() -> void:
	draw_set_transform(-position)
	painter.call(self)
