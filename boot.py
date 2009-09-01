# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.datatypes import Boolean, Integer, String, Tokens
from itools.handlers import ConfigFile, ro_database
from itools.http import HTTPServer
from itools.log import Logger, register_logger
from itools.log import DEBUG, INFO, WARNING, ERROR, FATAL
from itools.mail import MailSpool
from itools.web import WebLogger

# Import from ikaaro
from app import CMSApplication
from context import CMSContext
from globals import ui
from ikaaro import globals


log_levels = {
    'debug': DEBUG,
    'info': INFO,
    'warning': WARNING,
    'error': ERROR,
    'fatal': FATAL}


class CMSConfig(ConfigFile):

    schema = {
        'modules': Tokens,
        'listen-address': String(default=''),
        'listen-port': Integer(default=8080),
        'smtp-host': String(default=''),
        'smtp-from': String(default=''),
        'smtp-login': String(default=''),
        'smtp-password': String(default=''),
        'log-level': String(default='warning'),
        'database-size': String(default='4800:5200'),
        'profile-time': Boolean(default=False),
        'profile-space': Boolean(default=False),
        'index-text': Boolean(default=True)}



def get_server(target, cache_size=None, read_only=False):
    # Load configuration file
    config = ro_database.get_handler('%s/config.conf' % target, CMSConfig)
    globals.config = config
    get_value = config.get_value

    # Logging
    log_file = '%s/log/events' % target
    log_level = config.get_value('log-level')
    if log_level not in log_levels:
        msg = 'configuraion error, unexpected "%s" value for log-level'
        raise ValueError, msg % log_level
    log_level = log_levels[log_level]
    logger = Logger(log_file, log_level)
    register_logger(logger, None)
    logger = WebLogger(log_file, log_level)
    register_logger(logger, 'itools.http', 'itools.web')

    # Import Python packages and modules
    for name in get_value('modules'):
        name = name.strip()
        exec('import %s' % name)

    # Space profiling
    if get_value('profile-space'):
        import guppy.heapy.RM

    # Make the server
    address = get_value('listen-address')
    port = get_value('listen-port')
    access = '%s/log/access' % target
    pid = '%s/pid' % target
    profile = '%s/log/profile' % target if get_value('profile-time') else None
    server = HTTPServer(address, port, access, pid, profile)

    # Attach CMS context class
    server.context_class = CMSContext

    # Mount /
    if cache_size is None:
        cache_size = get_value('database-size')
    if ':' in cache_size:
        size_min, size_max = cache_size.split(':')
    else:
        size_min = size_max = cache_size
    size_min, size_max = int(size_min), int(size_max)
    index_text =  get_value('index-text')
    root = CMSApplication(target, size_min, size_max, read_only, index_text)
    server.mount('/', root)

    # Mount /ui
    server.mount('/ui', ui)

    # The email system
    spool = '%s/spool' % target
    smtp_from = get_value('smtp-from')
    smtp_host = get_value('smtp-host')
    smtp_login = get_value('smtp-login').strip()
    smtp_password = get_value('smtp-password').strip()
    spool = MailSpool(spool, smtp_from, smtp_host, smtp_login, smtp_password)
    spool.connect_to_loop()
    globals.spool = spool

    # Ok
    return server

