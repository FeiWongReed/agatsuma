# -*- coding: utf-8 -*-
"""
.. module:: base_core
   :synopsis: Basic core
"""
import os
import re
import signal

from agatsuma import Enumerator
from agatsuma import log
from agatsuma import Settings

majorVersion = 0
minorVersion = 1
try:
    from agatsuma.version import commitsCount, branchId, commitId
except:
    commitsCount = 0
    branchId = "branch"
    commitId = "commit"

def up(p):
    return os.path.split(p)[0]

class Core(object):
    """Base core which provides basic services, such as settings
and also able to enumerate spells.

:param app_directorys: list of paths to directories containing application spells.

.. note:: All the paths in ``app_directorys`` list must define importable namespaces. So if we replace all '/' with '.'  in such path we should get importable namespace

.. note:: app_directorys also may contain tuples with two values (``dir``, ``ns``) where ``ns`` is namespace corresponding to directory ``dir`` but it's not recommended to use this feature.

:param appConfig: path to JSON file with application settings

The following kwargs parameters are supported:

    #. `app_name` : Application name
    #. `appSpells` : names of namespaces to search spells inside
    #. `spellsDirs` : additional (to `app_directory`) directories to search spells inside

.. attribute:: instance

   The core instance. Only one core may be instantiated during application
   lifetime.

.. attribute:: version_string

   Full Agatsuma version including commit identifier and branch.
   May be extracted from GIT repository with `getversion` script.

.. attribute:: internalState

   Dict. For now contains only the key ``mode`` with value ``setup`` when core
   was started from setup.py and ``normal`` otherwise.

.. attribute:: agatsumaBaseDir

   Path to directory which contains Agatsuma. This directory makes Agatsuma's
   namespaces available when added into ``PYTHONPATH``.
    """
    instance = None
    version_string = "%d.%d.%d.%s.%s" % (majorVersion, minorVersion, commitsCount, branchId, commitId)
    internalState = {"mode":"normal"}
    agatsumaBaseDir = up(up(os.path.realpath(os.path.dirname(__file__))))

    @staticmethod
    def _internalSpellSpace(*fragments):
        basePath = os.path.join(Core.agatsumaBaseDir, *fragments)
        baseNS = '.'.join(fragments)
        return (basePath, baseNS)

    def __init__(self, app_directorys, appConfig, **kwargs):
        assert Core.instance is None
        Core.instance = self

        self.logger = log()
        self.logger.initiate_loggers()
        log.new_logger("core")
        log.new_logger("storage")
        log.core.info("Initializing Agatsuma")
        log.core.info("Version: %s" % self.version_string)
        log.core.info("Agatsuma's base directory: %s" % self.agatsumaBaseDir)

        self.extensions = []
        coreExtensions = kwargs.get("core_extensions", [])
        for extensionClass in coreExtensions:
            log.core.info("Instantiating core extension '%s'..." % extensionClass.name())
            extension = extensionClass()
            (app_directorys, appConfig, kwargs) = extension.init(self, app_directorys, appConfig, kwargs)
            methods = extension.additional_methods()
            for method_name, method in methods:
                setattr(self, method_name, method)
                log.core.debug("Extension method '%s' added to core's interface" % method_name)
            self.extensions.append(extension)

        self.app_name = kwargs.get("app_name", None)
        self.appSpells = kwargs.get("appSpells", [])
        self.spellsDirs = kwargs.get("spellsDirs", [])
        Core.internalState["mode"] = kwargs.get("appMode", "normal")

        self.spells = []
        self.spells_dict = {}
        self.registeredSettings = {}
        self.entry_points = {}

        #self.globalFilterStack = [] #TODO: templating and this
        forbidden_spells = kwargs.get("forbidden_spells", [])
        enumerator = Enumerator(self, app_directorys, forbidden_spells)

        self.spellsDirs.append(self._internalSpellSpace('agatsuma', 'spells', 'common'))
        enumerator.enumerateSpells(self.appSpells, self.spellsDirs)

        if appConfig:
            from agatsuma.interfaces.abstract_spell import AbstractSpell
            log.core.info("Initializing spells...")
            for spell in self.implementationsOf(AbstractSpell):
                spell.preConfigure(self)
            self.settings = Settings(appConfig, self.registeredSettings)
            self.logger.update_levels()
            log.core.info("Calling post-configure routines...")
            for spell in self.implementationsOf(AbstractSpell):
                spell.postConfigure(self)
            log.core.info("Spells initialization completed")
            self._postConfigure()
            enumerator.eagerUnload()
        else:
            log.core.critical("Config path is None")

        log.core.info("Initialization completed")
        signal.signal(signal.SIGTERM, self._sigHandler)

    def _stop(self):
        """
        Empty virtual function intended to be overriden in subclasses.
        Runs before core shutdown.
        """
        for extension in self.extensions:
            extension.on_core_stop(self)

    def _postConfigure(self):
        for extension in self.extensions:
            extension.on_core_post_configure(self)

    def _sigHandler(self, signum, frame):
        log.core.debug("Received signal %d" % signum)
        self.stop()

    def stop(self):
        """
        This method is intended to stop core. Subclasses may override method
        :meth:`agatsuma.core.Core._stop` to perform some cleanup actions here.
        """
        log.core.info("Stopping Agatsuma...")
        self._stop()

    def implementationsOf(self, InterfaceClass):
        """ The most important function for Agatsuma-based application.
        It returns all the spells implementing interface `InterfaceClass`.
        """
        return filter(lambda spell: issubclass(type(spell), InterfaceClass), self.spells)

    def registerOption(self, settingName, settingType, settingComment):
        """ This function must be called from
:meth:`agatsuma.interfaces.AbstractSpell.preConfigure`

**TODO**

:param settingName: String contains of two *group name* and *option name* separated with dot (``group.option`` for example). Option will be threated as read-only if the string begins with exclamation mark.
:param settingType: type for option value. Allowed all types compatible with JSON.
:param settingComment: string with human-readable description for option

See also **TODO**
"""
        if not getattr(self, "settingRe", None):
            self.settingRe = re.compile(r"^(!{0,1})((\w+)\.{0,1}(\w+))$")
        match = self.settingRe.match(settingName)
        if match:
            settingDescr = (match.group(3),
                            match.group(4),
                            bool(match.group(1)),
                            settingType,
                            settingComment,
                           )
            fqn = match.group(2)
            if fqn in self.registeredSettings:
                raise Exception("Setting is already registered: '%s' (%s)" % (fqn, settingComment))
            self.registeredSettings[fqn] = settingDescr
        else:
            raise Exception("Bad setting name: '%s' (%s)" % (settingName, settingComment))

    def registerEntryPoint(self, entryPointId, epFn):
        """ This method is intended to register *entry points*.
        Entry point is arbitrary function which receives
        arbitrary argumets list. Entry point may be called via
        :meth:`agatsuma.core.Core.runEntryPoint`. Core and services are fully initialized when
        entry point became available, so it may be used to perform
        different tasks that requires fully initialized environment such
        as database cleanup or something else.
        """
        if not entryPointId in self.entry_points:
            self.entry_points[entryPointId] = epFn
        else:
            raise Exception("Entry point with name '%s' is already registered" % entryPointId)

    def runEntryPoint(self, name, *args, **kwargs):
        """ This method runs registered entry point with given `name`
        with arguments `*args` and `**kwargs`.

        You should manually call this method from your application code when
        you need to run entry point.

        Basic Agatsuma's services provides several usable
        :ref:`entry points<std-entry-points>`.
        """
        self.entry_points[name](*args, **kwargs)

