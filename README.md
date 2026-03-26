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

To seed the server mods directly, use `scripts/modio_download_mods.py` with:

```bash
python3 scripts/modio_download_mods.py \
  --mods-file /AMP/insurgencysandstorm/581330/Insurgency/Config/Server/Mods.txt \
  --content-dir /AMP/insurgencysandstorm/581330/Steam/steamapps/workshop/content/581330 \
  --token "$MODIO_TOKEN"
```

When publishing to AMP's configuration repository, the same files must be placed at the repository root with the same lowercase names.
