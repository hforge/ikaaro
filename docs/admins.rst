Administrators Guide
####################

.. contents::

.. highlight:: sh


Install
=======

.. _admins-requirements:

System requirements
-------------------

Only Unix-like systems (e.g. GNU/Linux and Mac OS X) are supported, ikaaro
does not work on Windows.

The table below shows the software that must be installed, if possible
install this in the system using standard packages from your distribution.
The version in the second column is the minimum version supported, it may
work or not with older versions:

  ==========  =======  ========================================
  Python        2.6.4  http://www.python.org/
  ----------  -------  ----------------------------------------
  pkg-config     0.23  http://pkg-config.freedesktop.org/
  ----------  -------  ----------------------------------------
  glib           2.20  http://www.gtk.org/
  ----------  -------  ----------------------------------------
  pygobject      2.20  http://www.pygtk.org/
  ----------  -------  ----------------------------------------
  Git             1.7  http://git-scm.com/
  ----------  -------  ----------------------------------------
  libsoup        2.28  http://live.gnome.org/LibSoup
  ----------  -------  ----------------------------------------
  pytz                 http://pytz.sourceforge.net/
  ----------  -------  ----------------------------------------
  xapian        1.0.8  http://www.xapian.org/
  ----------  -------  ----------------------------------------
  gettext        0.17  http://www.gnu.org/software/gettext/
  ----------  -------  ----------------------------------------
  virtualenv      1.1  http://pypi.python.org/pypi/virtualenv
  ==========  =======  ========================================

And this table shows the recommended software:

  ==========  =======  ========================================
  PIL           1.1.6  http://www.pythonware.com/products/pil/
  ----------  -------  ----------------------------------------
  rsvg           2.30  http://www.pygtk.org/
  ----------  -------  ----------------------------------------
  xlrd          0.6.1  http://www.lexicon.net/sjmachin/xlrd.htm
  ----------  -------  ----------------------------------------
  poppler      0.10.4  http://poppler.freedesktop.org/
  ----------  -------  ----------------------------------------
  wv2           0.2.3  https://sourceforge.net/projects/wvware
  ==========  =======  ========================================


Virtualenv
----------

We advice to install ikaaro within a virtual environment, this is the
procedure::

  $ virtualenv --unzip-setuptools 0.62
  $ ./0.62/bin/pip install itools
  $ ./0.62/bin/pip install ikaaro


The command line interface
==========================

The :mod:`ikaaro` package includes a collection of command line tools to
create and manage instances:

  ============================== ===============================================
  :file:`icms-init.py`           creates a new :mod:`ikaaro` instance
  ------------------------------ -----------------------------------------------
  :file:`icms-start.py`          starts the web and the mail spool servers
  ------------------------------ -----------------------------------------------
  :file:`icms-stop.py`           stops the both servers
  ------------------------------ -----------------------------------------------
  :file:`icms-update.py`         updates the instance (after a software upgrade)
  ------------------------------ -----------------------------------------------
  :file:`icms-update-catalog.py` rebuilds the catalog
  ============================== ===============================================



All the scripts are self-documented, just run any of them with the ``--help``
option.  This is an excerpt for the :file:`icms-init.py` script::

    $ icms-init.py --help
    Usage: icms-init.py [OPTIONS] TARGET

    Creates a new instance of ikaaro with the name TARGET.

    Options:
      --version             show program's version number and exit
      -h, --help            show this help message and exit
      -e EMAIL, --email=EMAIL
                            e-mail address of the admin user
      -p PORT, --port=PORT  listen to PORT number
      -r ROOT, --root=ROOT  create an instance of the ROOT application
      -s SMTP_HOST, --smtp-host=SMTP_HOST
                            use the given SMTP_HOST to send emails
      -w PASSWORD, --password=PASSWORD
                            use the given PASSWORD for the admin user
      -m MODULES, --modules=MODULES
                            add the given MODULES to load at start
      --profile=PROFILE     print profile information to the given file


Make a new instance
===================

To create a new instance we use the :file:`icms-init.py` script. Example::

    $ icms-init.py --email=jdavid@itaapy.com my_instance
    *
    * Welcome to ikaaro
    * A user with administration rights has been created for you:
    *   username: jdavid@itaapy.com
    *   password: 7WEBJr
    *
    * To start the new instance type:
    *   icms-start.py my_instance
    *

(Take note of the automatically generated password, you will need it to enter
the application through the web interface.)

The :file:`icms-init.py` script creates a folder (named :file:`my_instance` in
the example) that keeps, among other things, the database and a configuration
file::

    $ tree -F -L 1 --noreport my_instance
    my_instance
    |-- catalog/
    |-- config.conf
    |-- database/
    |-- log/
    `-- spool/


.. _admins-configuration-file:

The configuration file
----------------------

Once the instance is created, it is a good idea to read the self-documented
configuration file, :file:`config.conf`, to learn about the available options,
and to finish the configuration process.

The different options can be split in four groups:

* The ``modules`` option allows to load (import) the specified Python packages
  when the server starts. This is the way we can extend the :mod:`ikaaro` CMS
  with third party packages.
* The ``listen-address`` and ``listen-port`` options define the internet
  address and the port number the Web server will listen to.

  By default connections are accepted from any internet address. In a
  production environment it is wise to restrict the connections to only those
  coming from the localhost. Section :ref:`admins-production` explains the
  details.
* The ``smtp-host``, ``smtp-from``, ``smtp-login`` and ``smtp-password`` are
  used to define the SMTP relay server that is to be used to send emails; and
  to provide the credentials for servers that require authentication.

  The ``contact-from`` option must be a valid email address, it will be used
  for the ``From`` field in outgoing messages.

  It is very important to set these options to proper values, since the
  :mod:`ikaaro` CMS sends emails for several important purposes.
* The ``log-level`` allows you to set the level of verbosity saved in the
  events log ``log/events`` file.


Start/Stop the server
=====================

The :mod:`ikaaro` CMS can be started simply by the use of the
:file:`icms-start.py` script::

    $ icms-start.py my_instance
    [my_instance] Web Server listens *:8080

By default the process remain attached to the console, to stop it just
type ``Ctrl+C``.  It is stopped ``gracefully``, what means that pending
requests will be handled and the proper responses sent to the clients.

To detach from the console use the ``--detach`` option. Then, to stop the
servers started this way use the :file:`icms-stop.py` script::

    $ icms-start.py --detach my_instance
    ...
    $ icms-stop.py my_instance
    [my_instance] Web Server shutting down (gracefully)...

With the Web server running, we can open our favourite browser and go to the
``http://localhost:8080`` URL, to reach the user interface (see figure).

.. figure:: figures/back-office.*
   :align: center

   The :mod:`ikaaro` Web interface.


A look inside
=============

The content of an :mod:`ikaaro` instance is:

* The configuration file (see section :ref:`admins-configuration-file`).
* The logs folder (see below).
* The database (see below).
* The catalog keeps the indexes needed to quickly search in the database.
* The mail spool keeps the emails to be sent by the spool server.


The logs
--------

There are four log files:

* The access log uses the *Common Log Format* [#admins-logs]_, useful for
  example to build statistics about the usage of the web site.
* By default the events log keeps record of the database transactions. In
  debug mode (see section :ref:`admins-configuration-file`), more low-level
  information is recorded. This log file contains also information about every
  *internal server* error, specifically the request headers and the Python
  tracebacks.
* The spool log keeps track of the emails sent by the spool server.
* The spool error log keeps information about every error coming from the
  spool server.


The database
------------

The data is stored directly in the file system. This is what a new instance
looks like::

    $ tree --noreport -F my_instance/database
    my_instance/database
    |-- .metadata
    |-- users/
    |   `-- 0.metadata
    `-- users.metadata

The database is made up of regular files and folders. For instance, a Web Page
will be stored in the database as an XHTML file, an image or an office
document will be stored as it is.

This is extremely useful for introspection and manipulation purposes, since we
can use the old good Unix tools: ``grep``, ``vi``, etc. But of course, *don't
make any changes unless you know what you are doing!*


Metadata
^^^^^^^^

Every :mod:`ikaaro` object is defined by a metadata file. As the example shows,
a new instance has three objects: the root (defined by the :file:`.metadata`
file), the users folder and the theme folder.

A metadata file looks like this:

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8"?>
    <metadata format="user" version="20071215">
      <password>FNp6/Vb9cFeAMTlQNcFylixbToQ%3D%0A</password>
      <email>jdavid@itaapy.com</email>
    </metadata>


.. _admins-production:

Deployment in a production environment
======================================

By default the server listens to all the network interfaces. For security
reasons it is recommended to change the configuration so it only listens
to the local interface:

    ``listen-address = 127.0.0.1``

Then you can configure Apache [#admins-apache]_ as a proxy server:

.. code-block:: apache

  <VirtualHost *:80>
    ServerName example.com
    ServerAlias vhost1.example.com
    ServerAlias vhost2.example.com
    ProxyPass / http://localhost:8080/
    ProxyPreserveHost On
  </VirtualHost>

Or Nginx [#admins-nginx]_:

.. code-block:: nginx

    server {
        server_name example.com;
        location / {
                proxy_pass http://localhost:8080;
                proxy_set_header        Host            $host;
                proxy_set_header        X-Real-IP       $remote_addr;
                proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;

        }
    }

As you can appreciate in the Apache example, there is not much to do to
support virtual hosting, since most of the work is done in the :mod:`ikaaro`
side.



Upgrading to a new software version
===================================

Generally major versions of :mod:`ikaaro` include changes to the layout or to
the format of the information stored in the database that require an upgrade.

The update process has two steps::

    # 1. Update the database
    $ icms-update.py --yes my_instance
    ...
    # 2. Rebuild the catalog
    $ icms-update-catalog.py --yes my_instance
    ...

Anyway, any major version of :mod:`ikaaro` includes upgrade notes that detail
any particular procedure.  Start a version upgrade by reading these notes.


Recovering from a crash
=======================

Though unlikely, it may happen that the server crashes leaving a transaction
in the middle, for example, if there is a power failure at the bad time. If
this happens, the server will refuse to start again, but it must provide some
instructions to restore the database (``git`` commands).


.. rubric:: Footnotes

.. [#admins-itools] http://www.hforge.org/itools

.. [#admins-guppy] http://guppy-pe.sourceforge.net/

.. [#admins-pil] http://www.pythonware.com/products/pil/

.. [#admins-docutils] http://docutils.sourceforge.net

.. [#admins-logs] http://www.w3.org/Daemon/User/Config/Logging.html\#common-logfile-format

.. [#admins-apache] http://http.apache.org

.. [#admins-nginx] http://nginx.org

