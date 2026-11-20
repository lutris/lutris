# Artwork sources

Lutris supports **Lutris.net** and **SteamGridDB** as automatic artwork sources.
Lutris.net is the default. Selecting SteamGridDB uses its **Original Steam
Assets**, not community uploads or Top Grids:

| Steam asset | Lutris artwork |
| --- | --- |
| Header | Banner |
| Capsule | Cover art |
| Icon | Icon |

SteamGridDB supplies game matching and Steam metadata. The original images are
downloaded from Valve's CDN. They retain their source resolution; the original
Steam Icon is typically only 32×32. The separate Client Icon is not substituted.

## Global source

1. Open Lutris preferences and choose **Lutris.net** or **SteamGridDB**.
2. For SteamGridDB, enter your own API key from
   [SteamGridDB preferences](https://www.steamgriddb.com/profile/preferences).

Switching the global source refreshes automatic artwork for games using the
global setting. Explicit per-game source choices and manually selected images
are protected.

The API key is stored in your local Lutris configuration file. Remove it before
sharing that file. An API key alone does not select SteamGridDB.

## Per-game source

In a game's configuration, choose **Use global**, **Lutris.net**, or
**SteamGridDB**, then save.

An explicit source choice overrides the global setting, even if both currently
select the same source. Later global switches do not replace that game's
artwork. **Use global** restores inheritance. Manually selected images still
take priority over either source.

SteamGridDB requires the game's exact title. Matching ignores case and
surrounding whitespace, but does not guess punctuation, editions, or similar
names. This applies to Steam games too. A deliberate save or rename can show a
bottom-center error toast if the title has no match. Background library scans
do not produce a toast for every unmatched game.

## Missing assets and storage

A matching game may have no original Steam assets, or only some of them. Lutris
does not substitute community artwork or silently fetch from the other source.
Failed downloads preserve existing valid images and manual selections.

API responses are cached for seven days and requests are paced. Authentication
and rate-limit errors stop the batch. Steam metadata can be incomplete or stale.

Newly managed artwork is stored separately for each game under
`artwork/<game-id>/` in the Lutris data directory. Existing shared artwork files
remain intact for compatibility. The per-game source preference is stored in
the game database; it is separate from the flags marking manually selected
images.

No images are uploaded, and no dedicated hero or logo slots are added.
