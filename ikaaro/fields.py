# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from the Standard Library
from copy import deepcopy
from types import FunctionType

# Import from itools
from itools.core import freeze
from itools.database import MetadataProperty
from itools.database import magic_from_buffer
from itools.database import Field as BaseField
from itools.datatypes import Boolean, Decimal, Date, DateTime, Email
from itools.datatypes import Enumerate, Integer, String, Unicode, URI
from itools.gettext import MSG
from itools.handlers import get_handler_class_by_mimetype
from itools.i18n import format_time
from itools.html import XHTMLFile, xhtml_uri
from itools.stl import rewrite_uris
from itools.uri import Reference, get_reference
from itools.web import get_context
from itools.web.context import select_language
from itools.xml import START_ELEMENT

# Import from ikaaro
from .datatypes import Boolean3, BirthDate, HexadecimalColor, HTMLBody
from .datatypes import Password_Datatype, ChoosePassword_Datatype
from .datatypes import DaysOfWeek
from .links import get_abspath_links, update_abspath_links
from .utils import split_reference, get_secure_hash
from .widgets import Widget, FileWidget, MultilineWidget, TextWidget
from .widgets import CheckboxWidget, RadioWidget, SelectWidget
from .widgets import BirthDateWidget, DateWidget, DatetimeWidget
from .widgets import PasswordWidget, ChoosePassword_Widget
from .widgets import ColorPickerWidget, ProgressBarWidget, RTEWidget


class Field(BaseField):

    rest_type = 'undefined' # Used by the rest interface

    default = None
    multilingual = False
    required = False
    title = None
    readonly = False  # Means the field should not be editable by the user
    datatype = None
    widget = None
    obsolete = False
    encrypted = False

    def get_value(self, resource, name, language=None):
        raise NotImplementedError


    def set_value(self, resource, name, value, language=None, **kw):
        """If value == old value then return False
           else make the change and return True
        """
        # Check the new value is different from the old value
        old_value = self.get_value(resource, name, language)
        if value == old_value:
            # Check the new parameters are different from the old one
            for p_key, p_value in kw.items():
                if self.get_value(resource, p_key, language) != p_value:
                    break
            else:
                return False

        # Set property
        self._set_value(resource, name, value, language, **kw)
        get_context().database.change_resource(resource)
        return True


    def get_value_title(self, resource, name, language=None, mode=None):
        return self.get_value(resource, name, language)


    # XXX For backwards compatibility
    datatype_keys = [
        'default',
        'multiple',
        'multilingual',
        'indexed',
        'stored',
        'is_valid',
        'encrypted',
    ]
    def get_datatype(self):
        kw = {}
        for key in self.datatype_keys:
            value = getattr(self, key, None)
            if value is not None:
                if type(value) is FunctionType:
                    value = staticmethod(value)
                kw[key] = value

        return self.datatype(mandatory=self.required, **kw)


    def get_default(self, language=None):
        if self.default is not None:
            return self.default
        return self.get_datatype().get_default()


    widget_keys = ['title', 'endline', 'size', 'tip', 'placeholder']
    def get_widget(self, name):
        kw = {}
        for key in self.widget_keys:
            value = getattr(self, key, None)
            if value is not None:
                kw[key] = value

        return self.widget(name, **kw)


    # Links
    def get_links(self, links, resource, field_name, languages):
        pass


    def update_links(self, resource, field_name, source, target, languages,
                     old_base, new_base):
        pass


    def update_incoming_links(self, resource, field_name, source, languages):
        pass


    # Rest representation
    def rest(self):
        rest = {'type': self.rest_type}
        # From the datatype
        datatype = self.get_datatype()
        for key in 'multiple', 'multilingual', 'indexed', 'stored':
            value = getattr(datatype, key)
            rest[key] = Boolean.encode(value)

        # Default value
        default = self.get_default()
        if default is not None:
            rest['default'] = datatype.encode(default)

        # Other
        for key in 'required', 'readonly':
            value = getattr(self, key)
            rest[key] = Boolean.encode(value)

        # Ok
        return rest


###########################################################################
# Metadata properties
###########################################################################
class Metadata_Field(Field):

    parameters_schema = freeze({})
    parameters_schema_default = None
    widget = Widget


    def get_value(self, resource, name, language=None):
        property = resource.metadata.get_property(name, language=language)
        if not property:
            return self.get_default(language=language)

        # Multiple
        if type(property) is list:
            return [ x.value for x in property ]

        # Simple
        return property.value


    def _set_value(self, resource, name, value, language=None, **kw):
        if language:
            kw['lang'] = language
        if kw:
            value = MetadataProperty(value, None, **kw)

        resource.metadata.set_property(name, value)


    def rest(self):
        rest = super(Metadata_Field, self).rest()
        rest['parameters'] = list(self.parameters_schema.keys())
        return rest



class Birthdate_Field(Metadata_Field):
    datatype = BirthDate()
    widget = BirthDateWidget()



class Boolean_Field(Metadata_Field):
    datatype = Boolean()
    widget = RadioWidget()
    widget_keys = Metadata_Field.widget_keys + ['label', 'oneline']



class Boolean3_Field(Metadata_Field):
    datatype = Boolean3()
    widget = SelectWidget()
    widget_keys = Metadata_Field.widget_keys + ['label']

    def get_value(self, resource, name, language=None):
        value = super(Boolean3_Field, self).get_value(resource, name, language)
        if value is True:
            return '1'
        elif value is False:
            return '0'
        return ''



class Char_Field(Metadata_Field):
    datatype = Unicode()
    widget = TextWidget()
    rest_type = 'bytes' # XXX


class Color_Field(Metadata_Field):
    datatype = HexadecimalColor()
    widget = ColorPickerWidget()


class Date_Field(Metadata_Field):
    datatype = Date()
    widget = DateWidget()



class Datetime_Field(Metadata_Field):

    datatype = DateTime()
    widget = DatetimeWidget
    rest_type = 'datetime'

    def get_value_title(self, resource, name, language=None, mode=None):
        value = resource.get_value(name)
        if not value:
            return None
        context = get_context()
        # Time
        if mode == 'time':
            value = context.fix_tzinfo(value)
            return format_time(value, language=language)
        # Datetime
        return context.format_datetime(value)



class Email_Field(Metadata_Field):
    datatype = Email()
    size = 40
    encrypted = True



class Integer_Field(Metadata_Field):
    datatype = Integer()


class Decimal_Field(Metadata_Field):
    datatype = Decimal()



class Password_Field(Metadata_Field):

    datatype = Password_Datatype()
    parameters_schema = {'algo': String(), 'salt': String(), 'date': DateTime()}
    widget = PasswordWidget


    def access(self, mode, resource):
        return mode == 'write'


    def set_value(self, resource, name, value, language=None, **kw):
        if value is not None:
            algo = 'sha256'
            value, salt = get_secure_hash(value, algo)
            kw['algo'] = algo
            kw['salt'] = salt
            kw['date'] = get_context().timestamp

        # super
        proxy = super(Password_Field, self)
        return proxy.set_value(resource, name, value, language, **kw)


class ChoosePassword_Field(Password_Field):
    datatype = ChoosePassword_Datatype()
    widget = ChoosePassword_Widget()
    widget_keys = Password_Field.widget_keys + ['userid']



class ProgressBar_Field(Metadata_Field):
    datatype = String
    widget = ProgressBarWidget


class Select_Field(Metadata_Field):
    rest_type = 'select'
    datatype = Enumerate()
    widget = SelectWidget()
    options = None # Must be overriden by subclasses: [{}, ...]

    datatype_keys = Metadata_Field.datatype_keys + ['options']
    widget_keys = Metadata_Field.widget_keys + ['has_empty_option', 'oneline']


    def get_value_title(self, resource, name, language=None, mode=None):
        value = self.get_value(resource, name, language)
        datatype = self.get_datatype()
        if self.multiple:
            return [datatype.get_value(x) for x in value]
        return datatype.get_value(value)


    def rest(self):
        rest = super(Select_Field, self).rest()
        datatype = self.get_datatype()
        rest['choices'] = [ x['name'] for x in datatype.get_options() ]
        return rest


class SelectAbspath_Field(Select_Field):
    """
    Select_Field with values linking to resources abspath
    """

    def get_links(self, links, resource, field_name, languages):
        return get_abspath_links(self, links, resource, field_name, languages)


    def update_links(self, resource, field_name, source, target, languages,
                     old_base, new_base):
        update_abspath_links(self, resource, field_name, source, target,
                         languages, old_base, new_base)


    def update_incoming_links(self, resource, field_name, source, languages):
        pass


    def get_value_title(self, resource, name, language=None, mode=None):
        abspath = self.get_value(resource, name, language=language)
        if not abspath:
            return None
        if self.multiple is False:
            return resource.get_resource(abspath).get_title()
        titles = []
        for x in abspath:
            r = resource.get_resource(x)
            titles.append(r.get_title())
        return ', '.join(titles)



class Text_Field(Metadata_Field):

    rest_type = 'text'
    datatype = Unicode()
    multilingual = True
    parameters_schema = {'lang': String} # useful only when multilingual
    widget = TextWidget()


    def set_value(self, resource, name, value, language=None, **kw):
        # If value is a MSG, save value in all languages
        if isinstance(value, MSG):
            root = resource.get_resource('/')
            languages = root.get_available_languages()
            for lang in languages:
                lang_value = value.gettext(language=lang)
                self.set_value(resource, name, lang_value, language=lang, **kw)
            return True
        # Ok
        proxy = super(Text_Field, self)
        return proxy.set_value(resource, name, value, language, **kw)


    def get_default(self, language=None):
        if self.default is not None:
            if self.multilingual:
                # Default value is multilingual too
                if isinstance(self.default, MSG):
                    return self.default.gettext(language=language)
                return self.default
            return self.default
        return self.get_datatype().get_default()



class Textarea_Field(Text_Field):

    widget = MultilineWidget()
    rest_type = 'textarea'
    widget_keys = Text_Field.widget_keys + ['rows', 'cols']



class URI_Field(Metadata_Field):
    datatype = URI()

    def get_links(self, links, resource, field_name, languages):
        base = resource.abspath
        if not self.multilingual:
            languages = [None]

        for lang in languages:
            value = resource.get_value(field_name, lang)
            if not value:
                continue
            if self.multiple:
                # Multiple
                for x in value:
                    if not x:
                        continue
                    # Get the reference, path and view
                    ref, path, view = split_reference(x)
                    if ref.scheme:
                        continue
                    link = base.resolve2(path)
                    links.add(str(link))
            else:
                # Get the reference, path and view
                ref, path, view = split_reference(value)
                if ref.scheme:
                    continue
                # Singleton
                link = base.resolve2(path)
                links.add(str(link))

        return links


    def update_links(self, resource, field_name, source, target, languages,
                     old_base, new_base):
        if not self.multilingual:
            languages = [None]

        for lang in languages:
            value = resource.get_value(field_name, lang)
            if not value:
                continue
            if self.multiple:
                # Multiple
                new_values = []
                for x in value:
                    if not x:
                        continue
                    # Get the reference, path and view
                    ref, path, view = split_reference(x)
                    if ref.scheme:
                        continue
                    path = old_base.resolve2(path)
                    if path == source:
                        # Explicitly call str because URI.encode does
                        # nothing
                        new_value = str(new_base.get_pathto(target)) + view
                        new_values.append(new_value)
                    else:
                        new_values.append(x)
                self._set_value(resource, field_name, new_values, lang)
            else:
                # Singleton
                # Get the reference, path and view
                ref, path, view = split_reference(value)
                if ref.scheme:
                    continue
                path = old_base.resolve2(path)
                if path == source:
                    # Hit the old name
                    # Build the new reference with the right path
                    # Explicitly call str because URI.encode does nothing
                    new_value = str(new_base.get_pathto(target)) + view
                    self._set_value(resource, field_name, new_value, lang)


    def update_incoming_links(self, resource, field_name, source, languages):
        target = resource.abspath
        resources_old2new = resource.database.resources_old2new
        if not self.multilingual:
            languages = [None]

        for lang in languages:
            value = resource.get_value(field_name, lang)
            if not value:
                continue
            if self.multiple:
                # Multiple
                new_values = []
                for x in value:
                    if not x:
                        continue
                    # Get the reference, path and view
                    ref, path, view = split_reference(x)
                    if ref.scheme:
                        continue
                    # Calculate the old absolute path
                    old_abs_path = source.resolve2(path)
                    # Check if the target path has not been moved
                    new_abs_path = resources_old2new.get(old_abs_path,
                                                         old_abs_path)
                    new_value = str(target.get_pathto(new_abs_path)) + view
                    new_values.append(new_value)
                self._set_value(resource, field_name, new_values, lang)
            else:
                # Singleton
                # Get the reference, path and view
                ref, path, view = split_reference(value)
                if ref.scheme:
                    continue
                # Calculate the old absolute path
                old_abs_path = source.resolve2(path)
                # Check if the target path has not been moved
                new_abs_path = resources_old2new.get(old_abs_path,
                                                     old_abs_path)

                # Explicitly call str because URI.encode does nothing
                new_value = str(target.get_pathto(new_abs_path)) + view
                self._set_value(resource, field_name, new_value, lang)


########################################
# Abspath_Field
########################################

class Abspath_Field(URI_Field):
    """
    Same that URI_Field but when we update links we use abspath
    """

    def get_links(self, links, resource, field_name, languages):
        return get_abspath_links(self, links, resource, field_name, languages)


    def update_links(self, resource, field_name, source, target, languages,
                     old_base, new_base):
        update_abspath_links(self, resource, field_name, source, target,
                         languages, old_base, new_base)


    def update_incoming_links(self, resource, field_name, source, languages):
        pass



class Owner_Field(Abspath_Field):

    readonly = True
    indexed = True
    stored = True



###########################################################################
# File handlers
###########################################################################
class File_Field(Field):

    rest_type = 'file'
    class_handler = None
    datatype = String()
    widget = FileWidget()


    def _get_key(self, resource, name, language):
        base = resource.metadata.key[:-9]
        if language:
            return f'{base}.{name}.{language}'

        return f'{base}.{name}'


    def get_value(self, resource, name, language=None):
        cls = self.class_handler
        get_handler = resource.metadata.database.get_handler
        has_handler = resource.metadata.database.has_handler

        # Language negotiation
        if self.multilingual and language is None:
            root = resource.get_root()
            languages = []
            for lang in root.get_value('website_languages'):
                key = self._get_key(resource, name, lang)
                if has_handler(key):
                    languages.append(lang)

            language = select_language(languages)
            if language is None:
                if not languages:
                    return None
                language = languages[0]

        # Ok
        key = self._get_key(resource, name, language)
        return get_handler(key, cls=cls, soft=True)


    def _set_value(self, resource, name, value, language=None, **kw):
        """
        value may be:

        - None (XXX remove handler?)
        - a handler
        - a byte string
        - a tuple
        - something else
        """
        if self.multilingual and not language:
            raise ValueError('expected "language" param not found')
        elif not self.multilingual and language:
            raise ValueError('"language" param should be empty')
        if kw:
            raise NotImplementedError('keyword arguments not supported')

        # FIXME This should remove the handler, the FileWidget should include
        # a checkbox to remove the handler
        if value is None:
            return

        # Set handler
        handler = self._get_handler_from_value(value)
        key = self._get_key(resource, name, language)
        database = resource.metadata.database
        if database.has_handler(key):
            database.del_handler(key)
        database.set_handler(key, handler)


    def _get_handler_from_value(self, value):
        if type(value) is tuple:
            filename, mimetype, value = value

        if type(value) in [bytes, str]:
            cls = self.class_handler
            if cls is None:
                mimetype = magic_from_buffer(value)
                cls = get_handler_class_by_mimetype(mimetype)
            return cls(string=value)

        return value



class TextFile_Field(File_Field):

    widget = MultilineWidget


map = {'a': 'href', 'img': 'src', 'iframe': 'src',
       # Map
       'area': 'href',
       # Object (FIXME param tag can have both src and data attributes)
       'object': 'data',
       'param': 'src'}


class HTMLFile_Field(File_Field):

    rest_type = 'file-html'
    class_handler = XHTMLFile
    datatype = HTMLBody()
    multilingual = True
    widget = RTEWidget()


    def _get_handler_from_value(self, value):
        if type(value) is list:
            handler = self.class_handler()
            handler.set_body(value)
            return handler

        return super(HTMLFile_Field, self)._get_handler_from_value(value)


    def get_links(self, links, resource, field_name, languages):
        base = resource.abspath
        for language in languages:
            handler = self.get_value(resource, field_name, language)
            if not handler:
                continue
            for event, value, line in handler.events:
                if event != START_ELEMENT:
                    continue
                tag_uri, tag_name, attributes = value
                if tag_uri != xhtml_uri:
                    continue

                # Get the attribute name and value
                attr_name = map.get(tag_name)
                if attr_name is None:
                    continue

                attr_name = (None, attr_name)
                value = attributes.get(attr_name)
                if value is None:
                    continue

                reference = get_reference(value)

                # Skip empty links, external links and links to '/ui/'
                if reference.scheme or reference.authority:
                    continue
                path = reference.path
                if not path or path.is_absolute() and path[0] == 'ui':
                    continue

                # Strip the view
                name = path.get_name()
                if name and name[0] == ';':
                    path = path[:-1]

                uri = base.resolve2(path)
                uri = str(uri)
                links.add(uri)


    def update_links(self, resource, field_name, source, target, languages,
                     old_base, new_base):
        for language in languages:
            handler = self.get_value(resource, field_name, language)
            if not handler:
                continue
            events = []
            for event in handler.events:
                # Process only elements of the XHTML namespace
                type, value, line = event
                if type != START_ELEMENT:
                    events.append(event)
                    continue
                tag_uri, tag_name, attributes = value
                if tag_uri != xhtml_uri:
                    events.append(event)
                    continue

                # Get the attribute name and value
                attr_name = map.get(tag_name)
                if attr_name is None:
                    events.append(event)
                    continue

                attr_name = (None, attr_name)
                value = attributes.get(attr_name)
                if value is None:
                    events.append(event)
                    continue

                reference = get_reference(value)

                # Skip empty links, external links and links to '/ui/'
                if reference.scheme or reference.authority:
                    events.append(event)
                    continue
                path = reference.path
                if not path or path.is_absolute() and path[0] == 'ui':
                    events.append(event)
                    continue

                # Strip the view
                name = path.get_name()
                if name and name[0] == ';':
                    view = '/' + name
                    path = path[:-1]
                else:
                    view = ''

                # Check the link points to the resource that is moving
                path = old_base.resolve2(path)
                if path != source:
                    events.append(event)
                    continue

                # Update the link
                # Build the new reference with the right path
                new_reference = deepcopy(reference)
                new_reference.path = str(new_base.get_pathto(target)) + view

                attributes[attr_name] = str(new_reference)
                event = (START_ELEMENT, (tag_uri, tag_name, attributes), line)
                events.append(event)

            handler.set_changed()
            handler.events = events
        resource.database.change_resource(resource)


    def update_incoming_links(self, resource, field_name, source, languages):
        target = resource.abspath
        resources_old2new = resource.database.resources_old2new

        def my_func(value):
            # Skip empty links, external links and links to '/ui/'
            uri = get_reference(value)
            if uri.scheme or uri.authority or uri.path.is_absolute():
                return value
            path = uri.path
            if not path or path.is_absolute() and path[0] == 'ui':
                return value

            # Strip the view
            name = path.get_name()
            if name and name[0] == ';':
                view = '/' + name
                path = path[:-1]
            else:
                view = ''

            # Resolve Path
            # Calcul the old absolute path
            old_abs_path = source.resolve2(path)
            # Get the 'new' absolute parth
            new_abs_path = resources_old2new.get(old_abs_path, old_abs_path)

            path = str(target.get_pathto(new_abs_path)) + view
            value = Reference('', '', path, uri.query.copy(), uri.fragment)
            return str(value)

        for language in languages:
            handler = self.get_value(resource, field_name, language)
            if not handler:
                continue
            events = rewrite_uris(handler.events, my_func)
            events = list(events)
            handler.set_changed()
            handler.events = events



class SelectDays_Field(Select_Field):
    datatype = DaysOfWeek()
    widget = CheckboxWidget()
    widget_keys = Select_Field.widget_keys + ['oneline']
    oneline = True



class UUID_Field(Char_Field):

    title = MSG('UUID')
    indexed = True
    stored = True
    readonly = True



class CTime_Field(Datetime_Field):

    title = MSG('Creation date')
    indexed = True
    stored = True
    readonly = True



class MTime_Field(Datetime_Field):

    title = MSG('Modification date')
    indexed = True
    stored = True
    readonly = True



class LastAuthor_Field(Char_Field):

    title = MSG('Last author')
    indexed = False
    stored = True
    readonly = True



class Title_Field(Text_Field):

    title = MSG('Title')
    indexed = True
    stored = True



class Description_Field(Textarea_Field):

    title = MSG('Description')
    indexed = True



class Subject_Field(Text_Field):

    title = MSG('Keywords')
    indexde = True
