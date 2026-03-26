# Insurgency Sandstorm AMP Fork

This folder is the working copy for the custom AMP Sandstorm template.

Edit these files here:
- `insurgency_sandstorm_custom.kvp`
- `insurgency_sandstorm_customconfig.json`
- `insurgency_sandstorm_custommetaconfig.json`
- `insurgency_sandstorm_customgame.ini`
- `insurgency_sandstorm_customgameusersettings.ini`
- `insurgency_sandstorm_customupdates.json`
- `insurgency_sandstorm_customports.json`

`insurgency_sandstorm_customgameusersettings.ini` is where the mod.io server access token goes:

`/Script/ModKit.ModIOClient`

`AccessToken=<your token>`

In AMP, the matching server setting is `mod.io Access Token`.

When publishing to AMP's configuration repository, the same files must be placed at the repository root with the same lowercase names.
