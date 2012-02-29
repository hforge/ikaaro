Web Services: RESTful interface
###############################

.. contents::

.. highlight:: sh


Introduction
==============

The Web Services interface provided follows the `REST
<http://en.wikipedia.org/wiki/Representational_state_transfer>`_ paradigm.
Information is exchanged using a subset of the `JSON
<http://en.wikipedia.org/wiki/JSON>`_ format (only objects, arrays, strings
and nulls are used). The only encoding supported is UTF-8.

The table below summurizes the interface::

  POST /;rest_login          # Authentication
  GET /.../;rest_query       # Query the database
  POST /.../;rest_create     # Create a new resource
  GET /.../;rest_read        # Read a resource
  POST /.../;rest_update     # Update a resource
 

Architecture recall
-------------------

In ikaaro information is stored in what we call resources. Resources are
organized in a tree structure. The path given in the request URI maps exactly
to a resource. On a resource you can call a view to get a particular
representation of the resource.

A resource is a collection of key-value pairs (fields). There are different
types of resources, every resource type has an schema which describes these
fields.

A standard simple field looks like this in JSON::

  "mtime": {"value": "2011-12-12T09:45:11+0000"}

Some fields may have multiple values::

  "share": [{"value": "everybody"}, {"value": "authenticated"}]

Other fields have parameters, for instance multilingual fields like the
title have a language parameter::

  "title": [{"lang": "en", "value": "Root"}, {"lang": "fr", "value": "Racine"}]


Authentication
==============

Authentication is done with a cookie named ``iauth``. To get the value of
this cookie a ``POST`` request to the ``rest_login`` view must be send. For
instance, the given request::

  POST /;rest_login HTTP/1.1
  Host: localhost:8080
  User-Agent: foobar
  Content-Type: application/x-www-form-urlencoded
  Content-Length: 26

  loginname=admin&password=a

May return the given response::

  HTTP/1.1 204 No Content
  Server: itools.web
  Date: Thu, 08 Dec 2011 10:33:07 GMT
  Set-Cookie: iauth="MDoE5qfkFUj8aKyr3A/bresG8EVNNOaLwN54zHxW%0A"; path=/
  Content-Length: 0

Grab the value of the ``iauth`` cookie and send it in subsequent requests,
like this::

  GET /;rest HTTP/1.1
  Host: localhost:8080
  User-Agent: foobar
  Cookie: iauth="MDoE5qfkFUj8aKyr3A/bresG8EVNNOaLwN54zHxW%0A"

If the authentication failed (wrong login-name or password), the cookie
will be missing.


Query
==============

The view to query the database is named ``rest_query``. It is available in
all the resources, and makes a search on the sub-tree. For instance calling
``GET /a/b/;rest_query`` will return only the resources below the ``/a/b``
sub-tree. So, to get all the resources in the database, call
``GET /;rest_query``.

Example::

  GET /;rest_query?format=webpage&fields=title HTTP/1.1
  Host: localhost:8080
  User-Agent: foobar
  Cookie: iauth="MDoE5qfkFUj8aKyr3A/bresG8EVNNOaLwN54zHxW%0A"

  HTTP/1.1 200 OK
  Server: itools.web
  Date: Thu, 08 Dec 2011 15:01:47 GMT
  Content-Type: application/json
  Content-Length: 66

  [{"abspath": "/page", "title": [{"lang": "en", "value": "Page"}]}]

By default only the path to the resource is returned. The ``fields`` query
parameter can be passed to ask for further fields.

Other query parameters can be passed to refine the search. For instance in
the example above we ask for resources of the ``webpage`` type.


Read
==============

The GET request method is used to get information about a resource. For
instance, the given request::

  GET /;rest_read HTTP/1.1
  Host: localhost:8080
  ...

May be answered with the given response::

  HTTP/1.1 200 OK
  Content-Type: application/json
  ...

  {"title": [{"lang": "en", "value": "Root"}], ...}


Update
==============

The PUT request method is used to update a resource. Such a request looks
like this::

  POST /;rest_update HTTP/1.1
  Content-Type: application/json
  ...

  [["title", "NEW TITLE", {"lang": "en"}]]

The JSON data represents a list of changes to be applied to the resource.
Every change has three elements:

- The name of the field
- The new value for the field
- The associated parameters

For multilingual fields (like title shown in the example above), the *lang*
parameter is required.


Create
==============

The POST request method is used to create a new resource::

  POST /;rest_create HTTP/1.1
  Content-Type: application/json
  ...

  ["page", "webpage", []]

The JSON data is a list with three fields:

- The name of the new resource
- The resource type identifier
- And the list of changes to apply to the new resource once it has been
  created (similar to the data sent in PUT requests)

On success a *201 Created* response is returned, with the URI of the
created resource in the ``Location`` header field.


Delete
==============

TODO
