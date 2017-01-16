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

# Import from itools
from itools.gettext import MSG

# Import from ikaaro
from ikaaro.emails import Email, register_email


class Event_Reminder_Email(Email):

    class_id = 'event-reminder'
    subject = MSG(u'Event reminder')
    text = MSG(
        u'We remind you the event "{title}" is scheduled at {date}, {time}.')


    event = None
    date = None
    def get_text_namespace(self, context):
        proxy = super(Event_Reminder_Email, self)
        namespace = proxy.get_text_namespace(context)
        namespace['title'] = self.event.get_title()
        namespace['date'] = context.format_date(self.date)
        namespace['time'] = context.format_time(self.date)
        return namespace


# Register
register_email(Event_Reminder_Email)
