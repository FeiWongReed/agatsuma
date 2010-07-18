# -*- coding: utf-8 -*-

from agatsuma import Implementations
from agatsuma.interfaces import SetupSpell, InternalSpell

def runSetuptools(**kwargs):
    from setuptools import setup
    from distribute_setup import use_setuptools
    use_setuptools()
    setup(**kwargs)

######################################################################
## Entry points
def collectEntryPoints(spellsFilter):
    spells = Implementations(SetupSpell)
    spells = filter(spellsFilter, spells)
    sections = {}
    for spell in spells:
        pointsdict = spell.pyEntryPoints()
        for section in pointsdict:
            if not sections.get(section, None):
                sections[section] = []
            points = pointsdict[section]
            sections[section].extend(points)
    return sections

def formatEntryPoints(epoints):
    out = ""
    for section, points in epoints.items():
        out += "[%s]\n" % section
        for point in points:
            out += "%s = %s:%s\n" % (point[0], point[1], point[2])
    return out

def entryPointsInfo(spellsFilter):
    entryPointsDict = collectEntryPoints(spellsFilter)
    return formatEntryPoints(entryPointsDict)

######################################################################
## Dependencies
def __withoutInternalSpells(spell):
    return not issubclass(type(spell), InternalSpell)

def depinfo(groupChecker, spellsFilter):
    spells = Implementations(SetupSpell)
    spells = filter(spellsFilter, spells)
    depGroups = []
    dependencies = []
    depGroupsContent = {}
    for spell in spells:
        depdict = spell.requirements()
        for group in depdict:
            depGroups.append(group)
            if not depGroupsContent.get(group, None):
                depGroupsContent[group] = []
            deps = depdict[group]
            depGroupsContent[group].extend(deps)
            if groupChecker(group):
                dependencies.extend(deps)
    dependencies = list(set(dependencies))
    return dependencies, depGroups, depGroupsContent

######################################################################
## Debug printouts
def out(s):
    #log.setup.info
    print s

def nl():
    out("="*60)

def printDeps(dependencies, depGroups, depGroupsContent, depGroupEnabled):
    out("The following dependencies classes are present:")
    out("(Use --disable-all to disable all the dependencies)")
    for group in depGroups:
        formatString = "[ ] %s: %s "
        if depGroupEnabled(group):
            formatString = "[*] %s: %s"
        out(formatString % (group, str(depGroupsContent[group])))
        out("    Use --without-%s to disable" % group)
        out("    Use --with-%s to enable" % group)
    nl()
    out("The following dependencies list will be used:\n%s" % str(dependencies))

######################################################################
## Useful routines
def groupsPredicate(args):
    components = filter(lambda s: s.startswith('--with'), args)
    depsDisabled = "--disable-all" in args

    args = filter(lambda s: not s.startswith('--with'), args)
    args = filter(lambda s: s != "--disable-all", args)

    def depGroupEnabled(group):
        depEnabled =(not (depsDisabled or ('--without-%s' % group) in components)
                     or (depsDisabled and ('--with-%s' % group) in components))
        return depEnabled
    return depGroupEnabled

def getDeps(depGroupsFilter, spellsFilter = __withoutInternalSpells):
    dependencies, depGroups, depGroupsContent = depinfo(depGroupsFilter,
                                                        spellsFilter)
    printDeps(dependencies, depGroups, depGroupsContent, depGroupsFilter)
    return dependencies

def getEntryPoints(spellsFilter = __withoutInternalSpells):
    entryPoints = entryPointsInfo(spellsFilter)
    nl()
    out("The following entry points are provided: %s" % entryPoints)
    nl()
    return entryPoints
