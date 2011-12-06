Web Services: RESTful interface
###############################

.. contents::

.. highlight:: sh


Introduction
==============

The Web Services interface provided follows the `REST
<http://en.wikipedia.org/wiki/Representational_state_transfer>`_ paradigm.
Four operations are supported (`CRUD
<http://en.wikipedia.org/wiki/Create,_read,_update_and_delete>`_), for
each one a different HTTP method is used:

- Create (POST)
- Read (GET)
- Update (PUT)
- Delete (DELETE)

Information is exchanged using the `JSON
<http://en.wikipedia.org/wiki/JSON>`_ format.

Every resource in ikaaro has a ``rest`` view, which can be called using any
of the four methods above, for instance, the given request::

  GET /;rest HTTP/1.1
  Host: localhost:8080
  ...

May be answred with the given response::

  HTTP/1.1 200 OK
  Content-Type: application/json
  ...

  {"title": [{"lang": "en", "value": "Root"}], ...}



Create
==============

TODO


Read
==============

TODO


Update
==============

TODO


Delete
==============

TODO



Authentication
==============

TODO
