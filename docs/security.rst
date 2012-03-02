Security
##############

.. _security:

.. contents::

.. highlight:: sh


Register form
=============

Whether a user is able or not to register by himself to the application, is
controlled through the configuration panel, the *User registration* form.

.. figure:: figures/config-register.*
   :width: 740px

   Configuration: Register form.


Users
==============

As the administrator she will be able to manage the users of the application:
to add new users and to define their access roles (see figure).

.. figure:: figures/users.*
   :width: 740px

   Managing Users.

User groups
--------------

User groups are created, deleted and managed through the *User groups*
interface in the configuration panel.

.. figure:: figures/user-groups.*
   :width: 740px

   User groups.

There are two special groups not visible in the configuration panel:

- Authenticated. Any user authenticated in the system belongs to this group.
- Everybody. All users, including non-authenticated users, belong to this
  group.

Another special group is the *Admins* group, any user belonging to this group
has all rights over all resources in the application (kind of a god).

User groups are used to define the access rights a user has over a resource.
See next section.


Access Control
==============

The question we want to answer is:

- *What rights has this user over this resource?*

To answer this question several concepts are involved:

- Users & User groups
- Resources
- Ownership
- Permissions
- Access rules
- Share


Ownership
--------------

Some resources have the *owner* property. The owner of a such a resource is
the user that created it. The owner of a resource is allowed to view, edit
and remove the resource, regardless of any other consideration.

Permissions
--------------

There are four permissions:

- View.

- Remove and modify.

- Share.

  If the user has this permission he will be able to change the Share
  settings of the resource

- Add.

  This is a somewhat special permission since the resource does not yet
  exist.


Share and Access rules
----------------------

Every resource has a *Share* property, which can be set to zero or more user
groups.

.. figure:: figures/security-share.*
   :width: 740px

   The Share property.

Access rules are defined through the *Access Control* interface in the
configuration panel.

.. figure:: figures/security-access-rules.*
   :width: 740px

   Access rules.

Aside from the ownerhip property, and from the admins special group, the
access to a resource requires two conditions to be met:

1. The Share of the resource must be defined for at least one group the
   user belongs to.

2. There must be at least one access rule that matchs the resource, for
   a group the user belongs to, and for the required permission.
