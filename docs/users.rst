User Guide
##########

.. contents::


The URL interface
=================

Even if most users don't type the URL directly in the navigation bar, the URL
remains the first and most important user interface. An :mod:`ikaaro` URL
looks like this:

    http://localhost:8080/users/0/;profile

Lets highlight the path component:

    ``/users/0/;profile``

One thing that makes this URL look different is the use of the semicolon
character, which has an especial meaning [#users-rfc2396]_. Actually the path
is divided in two parts:

* **The path to the resource** The path from the root of the tree to the a
  resource we want to reach (in our example it is ``/users/0``).
* **The method** The method (a view or an action) that we want to call on the
  resource (in our example it is ``profile``).


The User's Profile Page
=======================

When the user *logs in* the application she is redirected to her *profile
page* (see figure). From the profile page the user will be able to:

* modify the account details (first name, last name, email address);
* choose the preferred language for the user interface (English by default);
* change the password;
* manage her personal content.

.. figure:: figures/profile.*
   :align: center

   User's Profile Page


Access Control
==============

.. _users-security:

Security Policy
---------------

If the user has the administrative role she will be able to modify the
application's settings. Most notably to choose the *security policy* between
two options (see figure):

* **Intranet** Authentication will be required for any level of access.  Only
  administrators will be able to register new users. (This is the default
  security policy.)
* **Extranet**  Non authenticated users will be able to access published
  content, and to register by themselves.

.. figure:: figures/settings.*
   :align: center

   Application's Settings

.. _users-users:

Users
-----

As the administrator she will be able to manage the users of the application:
to add new users and to define their access roles (see figure).


.. figure:: figures/members.*
   :align: center

   Managing Users


Multiple Web Sites
==================

It is possible to host several Web Sites with a single :mod:`ikaaro` instance,
each one with its own settings (see section :ref:`users-security`) and members
(see section :ref:`users-users`).  For this purpose the :class:`WebSite`
object exists.


Content & Document Management
=============================

The most basic feature of :mod:`ikaaro` is the management of content and
documents (see the following figures): Web Pages, images, PDF files, Open
Office documents, etc.

.. figure:: figures/content_thumbs.*
   :align: center

   Content & Document Management (thumbnails view)

.. figure:: figures/content_list.*
   :align: center

   Content & Document Management (list view)


Web Pages
---------

Web Pages (HTML files) can be modified with the *in-line* editor (see figure).

.. figure:: figures/epoz.*
   :align: center

   HTML in-line editor


Workflow
--------

Access to content is controlled through a three-state workflow system (see
figure), where every document or image is in one of these states: *private*,
*pending* or *public*. The exact meaning of these states depends on the chosen
security policy (see section :ref:`users-security`).

.. figure:: figures/workflow.*
   :align: center

   Workflow


Index & Search
--------------

:mod:`ikaaro` is able to index many different file formats, if the required
software has been installed (cf :ref:`admins-requirements`). Then it is
possible to search for this content from the *browse list* view (see figure)
or from the global search interface (see figure).

.. figure:: figures/search.*
   :align: center

   Search


Modules
=======

:mod:`ikaaro` comes with several high-level modules *out of the box*.


Tracker
-------

The issue tracker is an useful tool for project management (see figure).

.. figure:: figures/tracker.*
   :align: center

   The Issue Tracker


Wiki
----

The Wiki is very useful to work together with other people to build up
content. A simple language called *reStructuredText* is used to give format to
the text (see figure).

.. figure:: figures/wiki.*
   :align: center

   The Wiki


Forum
-----

The Forum, or blog, allows to keep a discussion on-line about whatever
topic. See figure for a philosophical discussion.

.. figure:: figures/forum.*
   :align: center

   The Forum


Calendar
--------

The Calendar is to keep control of your time, for instance (see the following
figures).

.. figure:: figures/calendar_month.*
   :align: center

   The Calendar (monthly view)

.. figure:: figures/calendar_event.*
   :align: center

   The Calendar (event)


.. rubric:: Footnotes

.. [#users-rfc2396]

    Note that the semicolon makes part of the URI standard (RFC 2396),
    specifically it separates the segment name from the segment parameters.

