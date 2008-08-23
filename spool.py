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
from os import fstat, getpid, remove as remove_file
from signal import signal, SIGINT
from smtplib import SMTP, SMTPRecipientsRefused, SMTPResponseException
from socket import gaierror
from time import sleep
from traceback import print_exc

# Import from itools
from itools.uri import get_absolute_reference2
from itools import vfs
from server import get_config
from utils import is_pid_running



class Spool(object):

    def __init__(self, target):
        target = get_absolute_reference2(target)
        self.target = target
        self.spool = target.resolve2('spool')
        self._stop = False

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


    def get_pid(self):
        try:
            pid = open('%s/spool_pid' % self.target.path).read()
        except IOError:
            return None

        pid = int(pid)
        if is_pid_running(pid):
            return pid
        return None


    def start(self):
        # Pid
        open('%s/spool_pid' % self.target.path, 'w').write(str(getpid()))

        # Graceful stop
        signal(SIGINT, self.stop)

        # Go
        spool = vfs.open(self.spool)
        smtp_host = self.smtp_host
        log = self.log_activity
        while self._stop is False:
            sleep(10)
            # Find out emails to send
            locks = set()
            names = set()
            for name in spool.get_names():
                if name[-5:] == '.lock':
                    locks.add(name[:-5])
                else:
                    names.add(name)
            names.difference_update(locks)
            # Is there something to send?
            if len(names) == 0:
                continue

            # Open connection
            try:
                smtp = SMTP(smtp_host)
                if self.smtp_login and self.smtp_password:
                    smtp.login(self.smtp_login, self.smtp_password)
            except gaierror, excp:
                log('%s: "%s"' % (excp[1], smtp_host))
                continue
            except:
                self.log_error()
                continue
            # Send emails
            for name in names:
                try:
                    # Send message
                    message = spool.open(name).read()
                    headers = HeaderParser().parsestr(message)
                    subject = headers['subject']
                    from_addr = headers['from']
                    to_addr = headers['to']
                    # Send message
                    smtp.sendmail(from_addr, to_addr, message)
                    # Remove
                    spool.remove(name)
                    # Log
                    log('SENT "%s" from "%s" to "%s"' % (subject, from_addr,
                        to_addr))
                except (SMTPRecipientsRefused, SMTPResponseException):
                        # the SMTP server returns an error code
                        # or the recipient addresses has been refused
                        # Log
                        self.log_error()
                        # Remove
                        spool.remove(name)
                    # Other error ...
                except:
                    self.log_error()
            # Close connection
            smtp.quit()

        # Close files
        self.activity_log.close()
        self.error_log.close()
        # Remove pid file
        remove_file('%s/spool_pid' % self.target.path)


    def stop(self, n, frame):
        self._stop = True
        print 'Shutting down the mail spool (gracefully)...'


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


