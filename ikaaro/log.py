from logging.config import dictConfig
import sys


def config_logging(logdir, loglevel, detach):
    if detach:
        access_handler = {
            'class': 'logging.FileHandler',
            'filename': logdir / 'access.log',
        }
        events_handler = {
            'class': 'logging.FileHandler',
            'filename': logdir / 'events.log',
            'formatter': 'default'
        }
    else:
        access_handler = {
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
        }
        events_handler = {
            'class': 'logging.StreamHandler',
            'stream': sys.stderr,
        }

    dictConfig({
        'version': 1,
        'formatters': {
            'default': {
                'format': '%(asctime)s [%(levelname)10s] %(name)s %(message)s',
            }
        },
        'handlers': {
            'access': access_handler,
            'events': events_handler,
        },
        'loggers': {
            '': {
                'handlers': ['events'],
                'level': loglevel,
            },
            'ikaaro.access': {
                'handlers': ['access'],
                'level': 'INFO',
                'propagate': False,
            },
            # XXX We need to define the block below for logging to work, because the
            # loggers were created earlier.
            'itools': {},
            'ikaaro': {},
        },
    })