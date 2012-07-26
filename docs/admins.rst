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
  pytz                 http://pytz.sourceforge.net/
  ----------  -------  ----------------------------------------
  glib           2.20  http://www.gtk.org/
  ----------  -------  ----------------------------------------
  pygobject      2.20  http://www.pygtk.org/
  ----------  -------  ----------------------------------------
  pygit2       0.16.1  https://github.com/libgit2/pygit2
  ----------  -------  ----------------------------------------
  Git             1.7  http://git-scm.com/
  ----------  -------  ----------------------------------------
  libsoup        2.28  http://live.gnome.org/LibSoup
  ----------  -------  ----------------------------------------
  libmagic        5.0  http://www.darwinsys.com/file/
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

  $ virtualenv --unzip-setuptools 075
  $ ./075/bin/pip install itools
  $ ./075/bin/pip install ikaaro


The command line tools
======================

The :mod:`ikaaro` package includes a collection of command line tools to
create and manage instances:

============================== ===============================================
:file:`icms-init.py`           Creates a new :mod:`ikaaro` instance
------------------------------ -----------------------------------------------
:file:`icms-start.py`          Starts the web server
------------------------------ -----------------------------------------------
:file:`icms-stop.py`           Stops the web server
------------------------------ -----------------------------------------------
:file:`icms-update.py`         Updates the instance (after a software upgrade)
------------------------------ -----------------------------------------------
:file:`icms-update-catalog.py` Rebuilds the catalog
------------------------------ -----------------------------------------------
:file:`icms-forget.py`         Forgets transactions (rarely used)
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
  ├── catalog/
  ├── config.conf
  ├── database/
  ├── log/
  └── spool/


.. _admins-configuration-file:

Now you should edit the configuration file, and at least set the ``smtp-host``
option so sending emails works, and the ``smtp-from`` option to have a valid
email address.


The configuration file
======================

The configuration file :file:`config.conf` is self-documented, and the default
settings are likely to work on most cases, except for the ``smtp-host`` and
``smtp-from`` parameters.

This is the list of available options:

*modules*
  Space separated list of Python packages to load. Allows to extend
  :mod:`ikaaro` with more features.

*listen-address*, *listen-port*
  Defines the address and port the web server will listen to (localhost:8080
  by default).

*smtp-host*, *smtp-login*, *smtp-password*, *smpt-from*
  Defines the SMTP host used to send emails, with the credentials used to
  connect to the server, and the default value for the ``From`` field.

*log-level*
  May be ``critical``, ``error``, ``warning`` (default), ``info`` or
  ``debug``. See section :ref:`admins-logging` for further details.

*database-size*
  Defines the lower and upper limits of the cache system.

*profile-time*, *profile-space*
  Used by developers to profile time or space.

*index-text*
  Allows to de-activate full-text indexing.


Start/Stop the server
=====================

The :mod:`ikaaro` CMS can be started simply by the use of the
:file:`icms-start.py` script::

  $ icms-start.py my_instance
  [my_instance] Web Server listens *:8080

By default the process remains attached to the console, to stop it just
type ``Ctrl+C``.  It is stopped ``gracefully``, what means that pending
requests will be handled and the proper responses sent to the clients.

To detach from the console use the ``--detach`` option. Then, to stop the
server started this way use the :file:`icms-stop.py` script::

  $ icms-start.py --detach my_instance
  ...
  $ icms-stop.py my_instance
  [my_instance] Web Server shutting down (gracefully)...

With the Web server running, we can open our favourite browser and go to the
``http://localhost:8080`` URL, to reach the user interface (see figure).

.. figure:: figures/back-office.*
   :width: 740px

   The :mod:`ikaaro` login form.


Logging
=======

.. _admins-logging:

There are two log files. Both of them are automatically rotated every three
weeks.

``log/access``
  The access log records every request/response, it uses the *Common Log
  Format* [#admins-logs]_

``log/events``
  The events log is where errors, warnings, info and debug messages are
  written to.

What is written to the events log is defined by the ``log-level`` configuration
variable. There are five possible levels:

*critical*
  Log only critical errors (this kind of errors immediately stop the server).

*error*
  Log all errors, for instance application errors that produce a 500 response,
  they include often a Python traceback.

*warning*
  Log errors and warning messages (this is the default value).

*info*
  Log errors, warning and informational messages. For instance, this will
  include an informational message for every email successfully sent.

*debug*
  Log everything, including detailed data only useful for debugging.


The database
============

The data is stored directly in the file system. This is what a new instance
looks like::

  $ tree --noreport -F -L 1 -a my_instance/database
  my_instance/database
  ├── .git/
  ├── .metadata
  ├── theme/
  ├── theme.metadata
  ├── users/
  └── users.metadata

The database is made up of regular files and folders. For instance, a web page
will be stored in the database as an XHTML file, an image or an office
document will be stored as it is.

This is extremely useful for introspection and manipulation purposes, since we
can use the old good Unix tools: ``grep``, ``vi``, etc. But of course, *don't
make any changes unless you know what you are doing!*

Metadata
--------

Every :mod:`ikaaro` object is defined by a metadata file. As the example shows,
a new instance has three objects at the top level: the root (defined by the
:file:`.metadata` file), the users folder and the theme folder.

A metadata file looks like this::

  format;version=20081217:user
  email:jdavid@itaapy.com
  mtime:2011-01-07T17:42:41Z
  password:eSE%2BkSBKIP9xL6PEKsIcR75QyeU%3D%0A

Git
---

In the listing above, however, there is one special folder: ``.git``

Ikaaro uses Git to archive old versions of the data, and to implement the
transaction system. You can for instance run ``git log`` to see all the
transactions::

  $ cd my_instance/database
  $ git log
  commit 214029f8d12329b1464cd4401e18f609c2fc2c6d
  Author: nobody <>
  Date:   Fri Jan 7 13:57:10 2011 +0000

      GET http://localhost/

One can easily imagine what a powerful feature Git is for a system admin. For
instance to see what exactly happened when things go wrong, or to revert some
faulty commit.


The catalog
-----------

TODO


The mail spool
==============

TODO


.. _admins-production:

Deployment in a production environment
======================================

We recommend to run production ikaaro instances using an specific user, create
it this way::

  # useradd -b /var -m ikaaro
  # su - ikaaro

Then you can create one or more virtual environments, this is useful to have
different software installed in different environments::

  ikaaro $ virtualenv --unzip-setuptools 075
  ikaaro $ ./075/bin/pip install itools
  ikaaro $ ./075/bin/pip install ikaaro
  ikaaro $ cd 075

Now you can make one or more ikaaro instances::

  ikaaro $ ./bin/icms-init.py -e test@example.com mysite.com
  ikaaro $ vi mysite.com/config.conf
  ikaaro $ ./bin/icms-start.py -d mysite.com

It is recommended to deploy ikaaro instances behind a proxy server, for example
using Apache or NGinx.

Apache [#admins-apache]_:

.. code-block:: apache

  <VirtualHost *:80>
    ServerName example.com
    ServerAlias vhost1.example.com
    ServerAlias vhost2.example.com
    ProxyPass / http://localhost:8080/
    ProxyPreserveHost On
  </VirtualHost>


As you can appreciate in the Apache example, there is not much to do to
support virtual hosting, since most of the work is done in the :mod:`ikaaro`
side.

Nginx [#admins-nginx]_:

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


Mirroring
=========

Making a mirror of an ikaaro instance in a another server for failover is
easy, thanks to Git.

Say we have two servers, the production server named *prod*, and the failover
server named *back*.

We have this layout in the production server::

  /var/ikaaro/      # The ikaaro's user home
    075/            # The Python virtual environment
      example.com/  # The ikaaro instance

We are going to use a fetch strategy. This is to say, the failover server
will trigger the synchronization process and fetch from the production server
through the SSH protocol.  So the first step is to allow the failover server
to SSH into the production server, to do so we need an SSH key::

  # Make an SSH key in the failover server for the ikaaro user (do not set a
  # passphrase)
  ikaaro@back ~ $ ssh-keygen -t dsa

  # Copy the public key into the production server
  ikaaro@back ~ $ scp .ssh/id_dsa.pub joe@prod:/tmp

  # In the production server, make the ikaaro user to accept the key
  ikaaro@prod ~ $ cat /tmp/id_dsa.pub >> ~/.ssh/authorized_keys

Now, for every ikaaro instance we want to mirror, we need to reproduce the
layout in the failover server::

  ikaaro@back ~ $ virtualenv --unzip-setuptools 075
  ikaaro@back ~ $ cd 075
  ikaaro@back ~/075 $ ./bin/pip install itools
  ikaaro@back ~/075 $ ./bin/pip install ikaaro
  ikaaro@back ~/075 $ ./bin/icms-init.py -e toto example.com

We will throw away the database created this way, and make a clone of the
database in the production server::

  ikaaro@back ~/075 $ cd example.com
  ikaaro@back ~/075/example.com $ rm -rf database
  ikaaro@back ~/075/example.com $ git clone ssh://prod/~ikaaro/075/example.com/database/.git database

The script that will make the synchronization may look like this::

  #!/bin/bash

  PATHS=(
      "/var/ikaaro/075/example.com/database"
      "/var/ikaaro/075/another-example.com/database"
      )

  n=${#PATHS[@]}
  for (( i=0; i<${n}; i++ ));
  do
      cd ${PATHS[$i]} && git pull -q --rebase origin master
  done

And it will be called by a cron job in the failover server, for instance once
every ten minutes::

  /etc/cron.d/mirror-ikaaro
  00/10 * * * * ikaaro /usr/local/bin/ikaaro_mirror.sh



.. rubric:: Footnotes

.. [#admins-itools] http://www.hforge.org/itools

.. [#admins-guppy] http://guppy-pe.sourceforge.net/

.. [#admins-pil] http://www.pythonware.com/products/pil/

.. [#admins-docutils] http://docutils.sourceforge.net

.. [#admins-logs] http://www.w3.org/Daemon/User/Config/Logging.html\#common-logfile-format

.. [#admins-apache] http://http.apache.org

.. [#admins-nginx] http://nginx.org
