##  ikaaro 0.77.0 - 2017/03/10

### Added

- Works on server API (to stop/start server)
- Add example script `tools/server_api_example.py`
- Add /ui/cached/ route (that cache ui data)
- Move /ui/xxx.* to /ui/ikaaro/xxx.*
- Add /api route that give some API
- In development environment the `/ui/` folder take `/ui_dev/` data (so it's easier to build JS app)
- Root: Add Unavailable view (503)
- Add cache experiment on `get_value` / `get_value_title`
- Resource: Load data from brain to avoid loading metadata (for better performances)

### Changes

- Now uuidField is stored
- ikaaro is PIP compliant
- FileWidget: Add file download link/image preview
- Avoid the use of getpathto when useless (use abspaths)
- Use MetadataProperty not Property

### Fixes

- Fix deletion of handlers on multilingual fields
- Folder view: Fix sorting by unicode if value is None

Thanks to:

- Florent Chenebault
- J. David Ibáñez
