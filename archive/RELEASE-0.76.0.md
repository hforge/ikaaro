##  ikaaro 0.76.0 - 2017/01/18
### Added
- `UUID_Fields` : Add on all resources (unique id for all resources)
- `change_class_id()`: New method to simplify code migration:
  `user.change_class_id('toto')``
- Translations : Support Netherlands (nl)
- `config.conf`: Allow to configure if CORS is accepted (0 by default)
- `UserEmail_Field`: New field for email
- `Abspath_Field`: New Field for abspaths
- `Context`: New variable `is_cron` improved CRON access rights management
- `return_json`: New parameter context

### Changes
- `setup.py`: Improved to support package name
- Server : Move the API to start/stop/reindex catalog from scripts
- Update : Requirements.txt
- Calendar: We've removed the meeting CRON reminders
- CRON : Now cron-interval value is used (cron interval is not 1 anymore - so check your config.conf !)
- Resources : ctime/mtime/last_author are initialized on all resources at creation
- Resources : Allow to exclude patterns on copy
- Resources : `class_version` field is now indexed
- `get_value_title` : Take a new attribute 'mode'
  `user.get_value_title('ctime', mode='details') | user.get_value_title('ctime', mode='ago')`
- Translations : Update French translations
- Resources : Bug fixed when deleting (referential integrity was buggy)
- CSV : Bug fixed on Views
- Archives : Extractions improved
- `hidden_by_default` : Mechanism removed
- Errors : Improved error messages
- Errors : Cron errors are now logged
- `Context` : The context can be overridden into Root cls via "context_cls" variable
- `Context` : Allow to set user in "context.search" method so we can simulate access for others users
- `CSS` : Replaced "_" by "-" in table head css classes
- `Website` : New view `;update_instance` to launch update methods
- DB/Commits: Fix bug if author email is None
- DB/Commits : commits are faster avoiding complex OrQuery (21523e189c681e358bb6c560f617f3fde13cce81)
- Root: "make_user" improved. Now checked if user already exists and return None in case

Thanks to:

- Florent Chenebault
- J. David Ibáñez