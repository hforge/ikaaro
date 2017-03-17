##  ikaaro 0.77.0 - 2017/03/10

### Added
- `Server`: Improve API (add start() and stop() method)
- `Server`: Add /ui/cached/ route (to cache ui data)
- Server: Add example script `tools/server_api_example.py` to explain how to use the server
- Move `/ui/xxx.*` to `/ui/ikaaro/xxx.*`
- `urls`: Add `/api` route to access some APIs
- Build: In development environment the `/ui/` folder take `/ui_dev/` data (so it's easier to build JS app)
- `Root`: Add `UnavailableView`
- Cache: Add cache experiment on `get_value` / `get_value_title`
- `Resource`: Load data from brain to avoid loading metadata (for better performances)

### Changes
- Now `UuidField` is stored
- PIP: Ikaaro is now PIP compliant
- `FileWidget`: Add file download link/image preview
- `get_pathto`: Avoid this usage when useless (use `abspath`)
- Use `MetadataProperty` not `Property` (due to Itools 0.77.0 change)

### Fixes
- 'Fields`: Fix handlers deletion on multilingual fields
- `Folder_view`: Fix sorting by unicode if value is None

Thanks to:

- Florent Chenebault
- J. David Ibáñez
