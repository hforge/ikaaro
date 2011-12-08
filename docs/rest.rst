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

**Architecture recall**. In ikaaro information is stored in what we call resources. The resources
are organized in a tree structure. The path given through the request maps
exactly to a resource. On a resource you can call a view to get a
particular representation of the resource.

A resource is a collection of key-value pairs. There are different types
of resources, every resource type has an schema which describes these
key-value pairs.


Authentication
==============

Authentication is done with a cookie named ``iauth``. To get the value of
this cookie a ``POST`` request to the ``login`` view must be send. For
instance, the given request::

  POST /;login HTTP/1.1
  Host: localhost:8080
  User-Agent: foobar
  Content-Type: application/x-www-form-urlencoded
  Content-Length: 26

  loginname=admin&password=a

May return the given response::

  HTTP/1.1 302 Found
  Server: itools.web
  Date: Thu, 08 Dec 2011 10:33:07 GMT
  Set-Cookie: iauth="MDoE5qfkFUj8aKyr3A/bresG8EVNNOaLwN54zHxW%0A"; path=/
  Location: http://localhost:8080/?info=Welcome%21
  Content-Length: 0

Grab the value of the ``iauth`` cookie and send it in subsequent requests,
like this::

  GET /;rest HTTP/1.1
  Host: localhost:8080
  User-Agent: foobar
  Cookie: iauth="MDoE5qfkFUj8aKyr3A/bresG8EVNNOaLwN54zHxW%0A"


Create
==============

TODO


Read
==============

Every resource in ikaaro has a ``rest`` view, which can be called using any
of the four methods above, for instance, the given request::

  GET /;rest HTTP/1.1
  Host: localhost:8080
  ...

May be answered with the given response::

  HTTP/1.1 200 OK
  Content-Type: application/json
  ...

  {"title": [{"lang": "en", "value": "Root"}], ...}


Update
==============

TODO


Delete
==============

TODO

