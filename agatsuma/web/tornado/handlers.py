# -*- coding: utf-8 -*-

from agatsuma.core import Core
if Core.internalState.get("mode", None) == "normal":
    import tornado.web
    HandlerBaseClass = tornado.web.RequestHandler
else:
    HandlerBaseClass = object

from tornado_core import TornadoCore
from agatsuma.web.tornado.interfaces import RequestSpell
from agatsuma.errors import EAbstractFunctionCall
from url import UrlFor

class AgatsumaHandler(HandlerBaseClass):
    def __init__(self, application, request, transforms=None):
        tornado.web.RequestHandler.__init__(self, application, request, transforms)

    def prepare(self):
        spells = self.application.implementationsOf(RequestSpell)
        for spell in spells:
            spell.beforeRequestCallback(self)

    def async(self, method, args, callback):
        self.application.pool.apply_async(method,
                                          (id(self), ) + args,
                                          callback=self.async_callback(callback))

    def render(self, *args, **kwargs):
        nkwargs = {'UrlFor' : UrlFor}
        nkwargs.update(kwargs)
        return tornado.web.RequestHandler.render(self, *args, **nkwargs)

class MsgPumpHandler(AgatsumaHandler):
    def __init__(self, application, request):
        AgatsumaHandler.__init__(self, application, request)
        application.handlerInitiated(self)

    @staticmethod
    def sendMessage(id, message):
        TornadoCore.mqueue.put((id, message))

    def processMessage(self, message):
        raise EAbstractFunctionCall()

    def waitForQueue(self, callback):
        self.application.waitingCallbacks.append(callback)