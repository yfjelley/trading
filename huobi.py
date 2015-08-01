#!/usr/bin/env python
# -*- coding:utf-8 -*-
import time, json
from urllib import urlencode
from hashlib import md5
from collections import OrderedDict
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen
from exchange_api import ws_connect
from exchange_api import ExchangeAPI
from tornado.escape import utf8
from tornado.httpclient import AsyncHTTPClient

class HuobiAPI(ExchangeAPI):

    __exchange_name__ = 'huobi'

    def __init__(self, url=None, access_key=None, secret_key=None, ioloop=None):
        super(HuobiAPI, self).__init__(url, access_key, secret_key, ioloop)
        self.order_ids = {}
        self.created_time = 0
        
    def _on_connected(self):
        self._subscribe_market_depth()

    @gen.coroutine
    def _on_time_elsaped(self):
        result = yield super(HuobiAPI, self)._on_time_elsaped()

        #get order info
        for _id, in self.order_ids.keys():
            order_info = yield _get_order_info(_id)
            if order_info:
                if order_info['status'] == 2:
                    order_status = ORDER_STATUS.TRADE_COMPLETE

                else:
                    order_status = ORDER_STATUS.OPENING

                if order_info['type'] == 1:
                     sell_type = SELL_TYPE.SELL

                else:
                    sell_type = SELL_TYPE.BUY

                self._order_notify(self.__exchange_name__, 
                         order_info['orderId'], 
                         order_status,
                         order_info['averagePrice'], 
                         order_info['tradeAmount'], 
                         sell_type,
                         order_info['createdDate']
                     )
                
                del self.order_ids[_id]

        raise gen.Return(result)

    @gen.coroutine
    def _get_order_info(self, order_id=None):
        self.created_time = int(time.time())
        result = yield AsyncHTTPClient().fetch(
                    'https://api.huobi.com/apiv2.php', 
                    headers = {"Content-Type" : "application/x-www-form-urlencoded"},
                    method  = 'POST',
                    body    = urlencode({
                                  'access_key':     self.access_key, 
                                  'created':        self.created_time, 
                                  'coin_type':      1,
                                  'id':             order_id, 
                                  'method':         'order_info', 
                                  'sign':           md5(urlencode(OrderedDict([
                                                        ('access_key', self.access_key), 
                                                        ('coin_type', 1),
                                                        ('created', self.created_time),
                                                        ('id', order_id),
                                                        ('method', 'order_info'),
                                                        ('secret_key', self.secret_key)
                                                    ]))).hexdigest()
                                }))
        raise gen.Return(json.loads(result.body))
    
    def _on_message(self, message):
        if message:
            print utf8(message)
            message = json.loads(message)
            self.last_received = time.time()
            
            if message['action'] == 'btccny_depth':
                self._market_depth = message

            elif message['action'] == "spot_trade" and message['data'].get('order_id', None):
                order_id = message['data']['order_id']
                if order_id not in self.order_ids:
                    self.order_ids[order_id] = -1

    def _subscribe_market_depth(self):
        self.ws.write_message("{'event': 'subscribe', 'action': 'btccny_depth', 'client_uuid': '1000', 'parameters': {'initlength': 150}}")

    @property
    def market_depth(self):
        if not hasattr(self, "_market_depth"):
            self._market_depth = {}

        return self._market_depth
   
    @gen.coroutine
    def sell(self, amount):
        #实时按市价单，挂单
        self.created_time = int(time.time())
        yield self.ws.write_message(json.dumps({
                'event':        'request',
                'action':       'spot_trade',
                'client_uuid':  '100',
                'parameters':   {
                        'method':       'sell_market',
                        'access_key':   self.access_key,
                        'coin_type':    1,
                        'created':      self.created_time,
                        'sign' :        md5(urlencode(OrderedDict(sorted({'amount':amount, 'access_key':self.access_key, 'coin_type':1, 'method':'sell_market', 'created': self.created_time, 'secret_key': self.secret_key }.items())))).hexdigest().lower(),
                        'amount':       amount
                }}))

        raise gen.Return(None)
