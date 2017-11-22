##  ikaaro 0.78.0 - 2017/09/XX

### Changes
- The `GIT` database now use a bare repository
- We replaced `libsoup` server by `gevent.WSGIServer`
- Unused packages have been removed to simplify migration to python 3 (`itools.blog`, `itools.cc`, `itools.agenda`, `itools.comments`)
- Static view `/ui/xxx` now use `context.get_template` so there's a cache (Now served files should be loadable via handlers - so with no errors)
- `Catalog` don't flush data on disk at each transaction to increase commits speed
- `itools.web`: Cache headers to increase speed of cookies decoding
- `itools.database`: Add new unitests on database, & fix many bugs
- `Resource.del_resource`: Do not check cookies, that should be done in views
- Now we clearly identify the differences between `Folder` and `Resource` (for performances: Don't need to do DB queries to search resources childs)
- Resource: the `index` field has been removed (not used & avoid useless call to `get_links` on each resources)
- Add Dockerfile to simplify tests: https://hub.docker.com/r/hforge/
- Continous Integration: Connect to CircleCI https://circleci.com/gh/hforge
- `Resource.get_names()` return an iterator
- Add method `Server.launch_at_stop()`
- Log cron informations into `example.com/log/cron`
- Cron actions are called via HTTP requests
- Improve unitests workflows
- Folders: Resources can be added in current folder only (List with childs didn't scale)
- Remove 'is_content' index (never that simple)
- We've removed `obsolete package`

### Migration guide
- `notify_subscribers` method has been removed
- `itools.agenda` was removed
- `itools.blog` was removed
- `itools.cc` was removed
- `itools.comment` was removed
- Import of widgets from `itools.autoform` is now obsolete, use `itools.widgets` instead
- Calls to `database.fs.*` should be removed
- `len(resource.get_names())` should be replace by `len(list(resource.get_names()))`
- `Folder_View` view has been removed
- `database.worktree` has been removed

### Futur

- We replaced the `libsoup` server by `gevent.WSGIServer` to simplify Python 3 migration.
- The goal is to migrate itools/ikaaro to Python 3 and to use a simple WSGI server with asyncio.
- In next version we'll move some packages from itools to ikaaro.
- We'll remove many unused packages to simplify migration to Python 3
