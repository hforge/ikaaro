# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from standard library
from datetime import datetime, timedelta
from operator import itemgetter
from traceback import print_exc

# Import from itools
from itools.database import AndQuery, PhraseQuery, RangeQuery
from itools.gettext import MSG
from itools.web import STLView, ERROR


def class_version_to_date(version):
    return datetime.strptime(version[:8], '%Y%m%d').date()


def find_versions_to_update(context, force=False):
    database = context.database
    cls_errors = []
    cls_to_update = []
    # Find classes
    for cls in database.get_resource_classes():
        # Class version
        class_version = class_version_to_date(cls.class_version)
        class_version_tomorrow = class_version + timedelta(days=1)
        # Search for code older than the instance
        query = AndQuery(
            PhraseQuery('format', cls.class_id),
            RangeQuery('class_version', class_version_tomorrow, None))
        search = database.search(query)
        if search:
            resource = search.get_resources().next()
            kw = {'class_id': resource.class_id,
                  'class_title': resource.class_title,
                  'abspath': str(resource.abspath),
                  'resource_version': resource.metadata.version,
                  'cls_version': resource.class_version}
            cls_errors.append(kw)
            if force is False:
                break
        # Find out the versions to upgrade
        classes_and_versions = []
        for sub_cls in cls.mro():
            for name in sub_cls.__dict__.keys():
                if not name.startswith('update_'):
                    continue
                kk, version = name.split('_', 1)
                if len(version) != 8:
                    continue
                if not version.isdigit():
                    continue
                class_version = class_version_to_date(version)
                if class_version > class_version_to_date(cls.class_version):
                    raise ValueError('{0} class_version is bad'.format(sub_cls.class_id))
                class_version_yesterday = class_version - timedelta(days=1)
                query = AndQuery(
                    PhraseQuery('format', cls.class_id),
                    RangeQuery('class_version', None, class_version_yesterday))
                search = database.search(query)
                if not search:
                    continue
                class_and_version = (cls.class_id, version)
                if class_and_version in classes_and_versions:
                    # Overriden update method in sub classes
                    # So update method should be done one time
                    continue
                classes_and_versions.append(class_and_version)
                update_title_name = 'update_{0}_title'.format(version)
                update_title = getattr(cls, update_title_name, MSG(u'Unknow'))
                kw = {'class_id': cls.class_id,
                      'class_title': cls.class_title,
                      'class_version': version,
                      'class_version_date': class_version,
                      'class_version_pretty': context.format_date(class_version),
                      'update_title': update_title.gettext(),
                      'nb_resources': len(search)}
                cls_to_update.append(kw)
    # Sort
    cls_to_update.sort(key=itemgetter('class_version_date'))
    # Ok
    return {'cls_to_update': cls_to_update, 'cls_errors': cls_errors}



def run_next_update_method(context, force=False):
    """Update the database to the given versions.
    """
    database = context.database
    log = open('%s/log/update' % database.path, 'w')
    messages = []

    versions = find_versions_to_update(context, force)
    if not versions['cls_to_update']:
        return
    # Update
    version = versions['cls_to_update'][0]
    class_version = version['class_version_date']
    class_version_yesterday = class_version - timedelta(days=1)
    query = AndQuery(
        PhraseQuery('format', version['class_id']),
        RangeQuery('class_version', None, class_version_yesterday))
    search = context.database.search(query)
    # Update
    resources_old2new = database.resources_old2new
    for resource in search.get_resources():
        path = str(resource.abspath)
        abspath = resources_old2new.get(path, path)
        if abspath is None:
            # resource deleted
            continue
        # Reindex on errors
        obj_version = resource.metadata.version
        cls_version = resource.class_version
        next_versions = resource.get_next_versions()
        if (obj_version == cls_version or not next_versions or
            next_versions[0] != version['class_version']):
            values = resource.get_catalog_values()
            database.catalog.index_document(values)
            continue

        try:
            if resource is not None:
                # If resource has not been removed
                resource.update(version['class_version'])
        except Exception:
            line = 'ERROR: "{0}" - class_id: "{1}"\n'.format(
                resource.abspath, resource.__class__.class_id)
            log.write(line)
            print_exc(file=log)
            log.write('\n')
            # Add message
            messages.append(line)
            if force is False:
                return messages
    # Commit
    if not database.has_changed:
        # We reindex so the class_version is reindexed
        database.catalog.save_changes()
    else:
        # Commit (Do not override the mtime/author)
        git_message = u'Upgrade to version {0}'.format(version['class_version'])
        context.git_message = git_message
        context.set_mtime = False
        database.save_changes()
    # Ok
    return messages



class UpdateInstanceView(STLView):

    access = 'is_admin'
    title = MSG(u'Update instance')
    template = '/ui/ikaaro/update_instance.xml'

    def get_namespace(self, resource, context):
        return find_versions_to_update(context, force=True)


    def run_next_update_method(self, context, force=False):
        versions = find_versions_to_update(context, force)
        while versions['cls_to_update']:
            messages = run_next_update_method(context, force)
            if messages:
                error = ERROR(u'Error during update method. See logs.')
                messages.insert(0, error)
                context.message = messages
                return
            versions = find_versions_to_update(context, force)
        # Ok
        context.message = MSG(u'Updated method has been launched')


    def action_do_next_update(self, resource, context, form):
        return self.run_next_update_method(context)


    def action_force_next_update(self, resource, context, form):
        return self.run_next_update_method(context, force=True)
