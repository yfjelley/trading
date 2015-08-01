import time
from tornado import gen
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.websocket import websocket_connect

exchange_api_cls_registry = {}

@gen.coroutine
def ws_connect(url):
    ws = yield websocket_connect(url)
    ws.request.path = '_'
    raise gen.Return(ws)

class ExchangeAPIManager(object):
    registry = {}

    def market_depth(self, exchange):
        if exchange in self.registry:
            return self.registry[exchange].market_depth 

    @gen.coroutine
    def connect(self, exchange, *args, **kwargs):
        global exchange_api_cls_registry

        if exchange not in self.registry:
            exchange_api_class = exchange_api_cls_registry[exchange]
            self.registry[exchange] = exchange_api_class(*args, **kwargs)

        yield self.registry[exchange].connect()

        raise gen.Return(None)
        
    @gen.coroutine
    def sell(self, exchange, amount):
        if exchange in self.registry:
            yield self.registry[exchange].sell(amount)
            raise gen.Return(True)

        raise gen.Return(False)

class ExchangeAPIMetaClass(type):

    def __new__(cls, name, bases, attrs):
        if name == 'ExchangeAPI':
            return super(ExchangeAPIMetaClass, cls).__new__(cls, name, bases, attrs)

        new_class = type.__new__(cls, name, bases, attrs)
        global exchange_api_cls_registry

        exchange_api_cls_registry[new_class.__exchange_name__] = new_class
        return new_class

class ORDER_STATUS:
    OPENING = 0
    PART_TARDE = 1
    TRADE_COMPLETE = 2
    CANCELED = -1

class SELL_TYPE:
    SELL = 1
    BUY = 2

class ExchangeAPI(object):
    __metaclass__       = ExchangeAPIMetaClass
    __exchange_name__   = ''

    def __init__(self, url=None, access_key=None, secret_key=None, ioloop=None):
        self.url = url
        self.ws = None
        self.access_key = access_key
        self.secret_key = secret_key
        self.ioloop = ioloop or IOLoop.instance()
        self.last_received = None
        PeriodicCallback(self._on_time_elsaped, 1 * 1000).start()

    @gen.coroutine
    def _on_time_elsaped(self):
        yield self._keepalive()
        raise gen.Return(None)

    def _on_message(self, message): pass

    def _on_connected(self): pass

    def _order_notify(self, exchange, order_id, status, price, amount, sell_type, created):
        if self.on_order_notify:
            self.on_order_notify(exchange, order_id, status, price, amount, sell_type, created)

    @property
    def on_order_notify(self):
        if hasattr(self, '_on_order_notify'):
            return self._on_order_notify

        return None

    @on_order_notify.setter
    def on_order_notify(self, new_value):
        self._on_order_notify = new_value

    @gen.coroutine
    def _keepalive(self):
        if self.last_received:
            if time.time() - self.last_received > 5 * 60:
                yield self.reconnect()

            elif time.time() - self.last_received > 30 and self.ws:
                self.ws.write_message("{'event': 'ping'}")

        raise gen.Return(None)

    @gen.coroutine
    def connect(self): 
        self.ws = yield ws_connect(self.url)
        self.ws.on_message = self._on_message
        self._on_connected()
        raise gen.Return(self.ws)

    @gen.coroutine
    def reconnect(self):
        self.close()
        raise gen.Return((yield self.connect()))

    def close(self):
        if self.ws:
            self.ws.close()
            self.ws = None

import okcoin
import huobi
