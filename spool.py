# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2008 Henry Obein <henry@itaapy.com>
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
from datetime import datetime
from email.parser import HeaderParser
from os import fstat
from smtplib import SMTP, SMTPRecipientsRefused, SMTPResponseException
from socket import gaierror
from traceback import print_exc

# Import from pygobject
from gobject import timeout_add

# Import from itools
from itools.uri import get_reference
from itools.fs import lfs

# Import from ikaaro
from config import get_config



class Spool(object):

    def __init__(self, target):
        target = lfs.get_absolute_path(target)
        target = get_reference(target)
        self.target = target
        # spool
        spool = target.resolve_name('spool')
        self.spool = lfs.open(str(spool))
        # spool/failed
        spool_failed = spool.resolve_name('failed')
        spool_failed = str(spool_failed)
        if not lfs.exists(spool_failed):
            lfs.make_folder(spool_failed)

        # The SMTP host
        get_value = get_config(target).get_value
        self.smtp_host = get_value('smtp-host')
        self.smtp_login = get_value('smtp-login', default='').strip()
        self.smtp_password = get_value('smtp-password', default='').strip()

        # The logs
        self.activity_log_path = '%s/log/spool' % target.path
        self.activity_log = open(self.activity_log_path, 'a+')
        self.error_log_path = '%s/log/spool_error' % target.path
        self.error_log = open(self.error_log_path, 'a+')

        # Set up the callback function, every 10s
        timeout_add(10000, self.send_emails)


    def send_emails(self):
        # Find out emails to send
        locks = set()
        names = set()
        for name in self.spool.get_names():
            if name == 'failed':
                # Skip "failed" special directory
                continue
            if name[-5:] == '.lock':
                locks.add(name[:-5])
            else:
                names.add(name)
        names.difference_update(locks)
        # Is there something to send?
        if len(names) == 0:
            return True

        # Send emails
        for name in names:
            # 1. Open connection
            try:
                smtp = SMTP(self.smtp_host)
            except gaierror, excp:
                self.log_activity('%s: "%s"' % (excp[1], self.smtp_host))
                break
            except Exception:
                self.log_error()
                break
            self.log_activity('CONNECTED to %s' % self.smtp_host)

            # 2. Login
            if self.smtp_login and self.smtp_password:
                smtp.login(self.smtp_login, self.smtp_password)

            # 3. Send message
            try:
                message = self.spool.open(name).read()
                headers = HeaderParser().parsestr(message)
                subject = headers['subject']
                from_addr = headers['from']
                to_addr = headers['to']
                smtp.sendmail(from_addr, to_addr, message)
                # Remove
                self.spool.remove(name)
                # Log
                self.log_activity(
                    'SENT "%s" from "%s" to "%s"'
                    % (subject, from_addr, to_addr))
            except SMTPRecipientsRefused:
                # The recipient addresses has been refused
                self.log_error()
                self.spool.move(name, 'failed/%s' % name)
            except SMTPResponseException, excp:
                # The SMTP server returns an error code
                self.log_error()
                error_name = '%s_%s' % (excp.smtp_code, name)
                self.spool.move(name, 'failed/%s' % error_name)
            except Exception:
                self.log_error()

            # 4. Close connection
            smtp.quit()

        return True


    def log_activity(self, msg):
        # The data to write
        data = '%s - %s\n' % (datetime.now(), msg)

        # Check the file has not been removed
        log = self.activity_log
        if fstat(log.fileno())[3] == 0:
            log = open(self.activity_log_path, 'a+')
            self.activity_log = log

        # Write
        log.write(data)
        log.flush()


    def log_error(self):
        # The data to write
        lines = [
            '\n',
            '%s\n' % ('*' * 78),
            'DATE: %s\n' % datetime.now(),
            '\n']
        data = ''.join(lines)

        # Check the file has not been removed
        log = self.error_log
        if fstat(log.fileno())[3] == 0:
            log = open(self.error_log_path, 'a+')
            self.error_log = log

        # Write
        log.write(data)
        print_exc(file=log) # FIXME Should be done before to reduce the risk
                            # of the log file being removed.
        log.flush()


