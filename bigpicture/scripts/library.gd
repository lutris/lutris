## The library as Lutris sent it, and the views onto it: the rows of the home
## screen, the filters, and the games the library screen shows.
extends RefCounted

enum Sort { NAME, RECENT, PLAYTIME }

## Games shown in the "recent" rows of the home screen.
const ROW_LIMIT := 24

var games: Array[Dictionary] = []
## The home screen's rows: {title, items}, items being indexes into games.
var rows: Array[Dictionary] = []
## The library's filters: {kind, name}; kind is all, favorites, category or runner.
var filters: Array[Dictionary] = [{"kind": "all", "name": ""}]
var filter := 0
var sort := Sort.NAME
var query := ""
## The games the library shows, as indexes into games.
var view: Array[int] = []


## A game with every field present and of the type it should have.
static func normalized(raw: Dictionary) -> Dictionary:
	var year = raw.get("year")

	return {
		"id": _id(raw.get("id", "")),
		"name": str(raw.get("name", "")),
		"sortname": str(raw.get("sortname", "")),
		"runner": str(raw.get("runner", "")),
		"platform": str(raw.get("platform", "")),
		"year": int(year) if year != null else 0,
		"playtime": float(raw.get("playtime", 0.0)),
		"playtime_text": str(raw.get("playtime_text", "")),
		"lastplayed": int(raw.get("lastplayed", 0)),
		"lastplayed_text": str(raw.get("lastplayed_text", "")),
		"installed_at": int(raw.get("installed_at", 0)),
		"cover": str(raw.get("cover")) if raw.get("cover") != null else "",
		"favorite": bool(raw.get("favorite", false)),
		"categories": raw.get("categories", []),
		"state": str(raw.get("state", "stopped")),
	}


## An ID as text. JSON has all numbers as floats, and 7.0 is not an ID.
static func _id(raw) -> String:
	if raw is float and raw == floorf(raw):
		return str(int(raw))

	return str(raw)


## What a game is sorted by: its sort name if it has one, without regard to case.
static func sort_key(game: Dictionary) -> String:
	var name: String = game.sortname if not game.sortname.is_empty() else game.name

	return name.to_lower()


func index_of(id: String) -> int:
	for index in games.size():
		if games[index].id == id:
			return index

	return -1


## Replaces the library, keeping the selected filter if it still exists.
func set_games(raw_games: Array) -> void:
	var selected := filters[filter] if filter < filters.size() else filters[0]

	games.clear()
	for raw in raw_games:
		if raw is Dictionary:
			games.append(normalized(raw))

	_build_rows()
	_build_filters()

	filter = 0
	for index in filters.size():
		if filters[index] == selected:
			filter = index


func _by_name(a: int, b: int) -> bool:
	return sort_key(games[a]) < sort_key(games[b])


func _build_rows() -> void:
	rows.clear()

	var recent: Array[int] = []
	var favorites: Array[int] = []
	var added: Array[int] = []
	for index in games.size():
		if games[index].lastplayed > 0:
			recent.append(index)

		if games[index].favorite:
			favorites.append(index)

		if games[index].installed_at > 0:
			added.append(index)

	recent.sort_custom(func(a, b): return games[a].lastplayed > games[b].lastplayed)
	favorites.sort_custom(_by_name)
	added.sort_custom(func(a, b): return games[a].installed_at > games[b].installed_at)

	if not recent.is_empty():
		rows.append({"title": "Recently played", "items": recent.slice(0, ROW_LIMIT)})

	if not favorites.is_empty():
		rows.append({"title": "Favorites", "items": favorites})

	if not added.is_empty():
		rows.append({"title": "Recently added", "items": added.slice(0, ROW_LIMIT)})

	if rows.is_empty() and not games.is_empty():
		var all: Array[int] = []
		all.assign(range(games.size()))
		all.sort_custom(_by_name)
		rows.append({"title": "All games", "items": all.slice(0, ROW_LIMIT)})


func _build_filters() -> void:
	filters = [{"kind": "all", "name": ""}]

	var categories := {}
	var runners := {}
	var any_favorite := false
	for game in games:
		any_favorite = any_favorite or game.favorite
		for category in game.categories:
			categories[str(category)] = true

		if not game.runner.is_empty():
			runners[game.runner] = true

	if any_favorite:
		filters.append({"kind": "favorites", "name": ""})

	var names := categories.keys()
	names.sort_custom(func(a, b): return a.to_lower() < b.to_lower())
	for name in names:
		filters.append({"kind": "category", "name": name})

	# Runners are only worth choosing between if there are several.
	names = runners.keys()
	names.sort_custom(func(a, b): return a.to_lower() < b.to_lower())
	if names.size() > 1:
		for name in names:
			filters.append({"kind": "runner", "name": name})


func _passes(game: Dictionary, needle: String) -> bool:
	var chosen := filters[filter] if filter < filters.size() else filters[0]
	match chosen.kind:
		"favorites":
			if not game.favorite:
				return false
		"category":
			if not game.categories.has(chosen.name):
				return false
		"runner":
			if game.runner != chosen.name:
				return false

	return needle.is_empty() or game.name.to_lower().contains(needle)


## Recomputes the games the library shows. Returns where the game with the ID
## given now is, or 0 if it is not shown.
func build_view(keep_id := "") -> int:
	var needle := query.strip_edges().to_lower()

	view.clear()
	for index in games.size():
		if _passes(games[index], needle):
			view.append(index)

	match sort:
		Sort.NAME:
			view.sort_custom(_by_name)
		Sort.RECENT:
			view.sort_custom(func(a, b):
				if games[a].lastplayed != games[b].lastplayed:
					return games[a].lastplayed > games[b].lastplayed

				return _by_name(a, b))
		Sort.PLAYTIME:
			view.sort_custom(func(a, b):
				if games[a].playtime != games[b].playtime:
					return games[a].playtime > games[b].playtime

				return _by_name(a, b))

	for position in view.size():
		if games[view[position]].id == keep_id:
			return position

	return 0
