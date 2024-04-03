============================
Moderating Lutris installers
============================

Every Lutris installer must receive approval from a moderator before being public.

Here are some guidelines on how to accept or reject installer submissions.

Base guidelines
===============

You should be comfortable with the syntax of Lutris install scripts and ideally have written a few scripts.
You do not have to test the games for which you validate the script for.

Valid submissions
=================

Those cases are usually valid and can be accepted.

- Version upgrade: The version number of a downloaded file is increased.
- GOG installers with fixes, installers that differ enough from the default Lutris generated one
- Steam installers for games without a Steam ID in the Lutris DB (usually free games)
- Fixes to existing installers that make sense or provide a good reason for the fix
- Simplification of installers. Removing Winetricks commands, removing the pinned wine version.

Non ideal submissions but are most likely to get approved anyway
================================================================

- Installers that install a launcher like EGS or EA App for a single game, bypassing the Lutris integrations.
- Scripts that reimplement existing Lutris features with Shell commands.
- Windows games using a win32 prefix: With modern Wine, all games should work with a 64bit prefix

Invalid submissions
===================

- Unmodified content. While we have code to prevent this, some still manage to get through.
- Suspicious URL changes. If a file changes to a different domain, make sure the new URL is referenced by the game's authors.
- Version downgrade: Unless given very good reasons, downgrade in versions are rejected.
- Runner changes: Submissions changing the runner to another one are almost always invalid.
- Mentions of disabling the Lutris runtime: We make Lutris with the intention of having the runtime work. If it doesn't that's an user problem or something that needs to be fixed in the runtime.
- Submissions for "Apes VS Helium". This games somehow attract kids who have no clue what Lutris installers are.
- Submissions for "League of Legends". Most submissions should be rejected.
- Submissions for "Fortnite". The game doesn't run on Linux. Nothing will change that.

