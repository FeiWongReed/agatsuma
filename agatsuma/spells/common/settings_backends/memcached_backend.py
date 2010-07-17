# -*- coding: utf-8 -*-
import re

try:
    import cPickle as pickle
except ImportError:
    import pickle

from agatsuma import log
from agatsuma import Spell
from agatsuma.interfaces import (AbstractSpell,
                                 InternalSpell,
                                 SettingsBackendSpell,
                                 SettingsBackend)

class MemcachedSettingsBackend(SettingsBackend):
    def __init__(self, uri):
        SettingsBackend.__init__(self)
        self.uri = uri
        self.initConnection()

    def initConnection(self):
        log.settings.info("Initializing Memcached settings backend "\
                          "using URI '%s'" % self.uri)
        self.keyprefix = self._parseMemcachedPrefixUri(self.uri)
        memcachedSpell = Spell("agatsuma_memcached")
        self.pool = memcachedSpell.getConnectionPool()

    @property
    def connection(self):
        with self.pool.reserve() as mc:
            return mc

    def _getPrefixedKey(self, sessionId):
        if self.keyprefix:
            return str("%s_%s" % (self.keyprefix, sessionId))
        return sessionId

    @staticmethod
    def _parseMemcachedPrefixUri(details):
        # memprefix://prefixname
        match = re.match('^memprefix://(\w+)$', details)
        return match.group(1) if match else ''

    def get(self, name, currentValue):
        data = self.connection.get(self._getPrefixedKey(name))
        if data:
          return pickle.loads(data)
        return currentValue

    def save(self, name, value):
        if not self.connection.set(self._getPrefixedKey(name),
                                   pickle.dumps(value)):
            log.settings.critical("Saving setting '%s' failed" % name)

class MemcachedSettingsSpell(AbstractSpell, InternalSpell, SettingsBackendSpell):
    def __init__(self):
        config = {'info' : 'Memcached settings storage',
                  'deps' : ('agatsuma_memcached', ),
                  'provides' : ('settings_backend', )
                 }
        AbstractSpell.__init__(self, 'agatsuma_settings_backend_memcached',
                               config)

    def instantiateBackend(self, uri):
        self.managerInstance = MemcachedSettingsBackend(uri)
        return self.managerInstance
