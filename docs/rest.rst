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
 

The database
--------------

Ikaaro uses the ``itools.database`` NoSQL database system, of the
`document-store <http://en.wikipedia.org/wiki/Document-oriented_database>`_
type, except the main unit of information is called *resource* (instead of
document).

Resources are organized in a hierarchical structure, so the key to lookup
a resource in the the database is its absolute path. A query API is also
available to retrieve a collection of resources matching some criterias,
this query API is backed by the `Xapian <http://xapian.org/>`_ search engine
library.

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


The URL
--------------

The URL path is split in two parts, first the path to the resource, last
the view on the resource. A view returns a particular representation of the
resource::

    http://example.com/a/b/c/;rest_read

In the URL above the path to the resource is ``/a/b/c`` and the name of
the view is ``rest_read``. Note the semicolon, it allows to unambigously
specify where the resource path ends, and where the view name starts.


Authentication
==============

Authentication is done with a cookie named ``iauth``. To get the value of
this cookie a ``POST`` request to the ``rest_login`` view must be send. Such
a request looks like this::

  POST /;rest_login HTTP/1.1
  Host: localhost:8080
  User-Agent: foobar
  Content-Type: application/x-www-form-urlencoded
  Content-Length: 26

  loginname=admin&password=a

There are two possible results:

============ =================== ========
.            Success             Failure
============ =================== ========
Status       200                 204
Set-Cookie   iauth="..."; path=/
Body         /users/0
============ =================== ========

Example, on success::

  HTTP/1.1 200 Ok
  Server: itools.web
  Date: Thu, 08 Dec 2011 10:33:07 GMT
  Set-Cookie: iauth="MDoE5qfkFUj8aKyr3A/bresG8EVNNOaLwN54zHxW%0A"; path=/
  Content-Length: 8

  /users/0

Example, on failure::

  HTTP/1.1 204 No Content
  Server: itools.web
  Date: Thu, 08 Dec 2011 10:33:07 GMT
  Content-Length: 0

Grab the value of the ``iauth`` cookie and send it in subsequent requests,
like this::

  GET /;rest HTTP/1.1
  Host: localhost:8080
  User-Agent: foobar
  Cookie: iauth="MDoE5qfkFUj8aKyr3A/bresG8EVNNOaLwN54zHxW%0A"


Schema
==============

This view is intended to help developers learn about the application. It
shows the schema of the resource, which describes its fields::

  GET /;rest_schema
  Host: localhost:8080
  User-Agent: foobar
  Cookie: iauth="MDoE5qfkFUj8aKyr3A/bresG8EVNNOaLwN54zHxW%0A"

  HTTP/1.1 200 OK
  Server: itools.web
  Date: Fri, 02 Mar 2012 17:45:56 GMT
  Content-Type: application/json
  Content-Length: 1428

  {"index": {...}, ...}

The value returned is a dictionary, where the key is the name of the field
and the value is another dictionary describing that field:

- *type* -- the field type (text, datetime, etc.)
- *default* -- the default value for the field, when the resource does not
  define one.
- *multiple* -- boolean indicating whether the field may have multiple values
  or not.
- *multilingual* -- boolean indicating whether the field is multilingual or
  not.
- *parameters* -- the parameters of the field, for instance multilingual
  fields have a language paramer.
- *readonly* -- boolean, if true it means the field cannot be explicitely
  modified (exemple: the modification time).
- *required* -- boolean, if true it means this field is required.
- *indexed* -- boolean indicating whether the field is indexed or not (used
  by the Xapian search engine library).
- *stored* -- boolean indicating whether the field is stored or not (used by
  the Xapian search engine library).
- *choices* -- available only in select-fields, a list with the possible
  values of the field.


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

Binaray content, like images, is returned in Base64 encoding (see RFC 3548).


Update
==============

The POST request method is used to update a resource. Such a request looks
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
  created (similar to the data sent in update requests)

On success a *201 Created* response is returned, with the URI of the
created resource in the ``Location`` header field.


Delete
==============

The POST request method is used to delete a resource::

  POST /page/;rest_delete HTTP/1.1
  Content-Length: 0

In the example above we delete the resource ``/page``.
