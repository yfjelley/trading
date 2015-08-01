#!/usr/bin/env python
# -*- coding:utf-8 -*-
import time, json
from urllib import urlencode
from hashlib import md5
from collections import OrderedDict
from tornado import gen
from exchange_api import ws_connect
from exchange_api import ExchangeAPI, ORDER_STATUS, SELL_TYPE

class OKCoinAPI(ExchangeAPI):

    __exchange_name__ = 'okcoin'

    def __init__(self, url=None, access_key=None, secret_key=None, ioloop=None):
        super(OKCoinAPI, self).__init__(url, access_key, secret_key, ioloop)

    def _on_connected(self):
        self._subscribe_market_depth()
        self._subscribe_realtrades()
  
    def _on_message(self, message):
        if message:
            print message
            message = json.loads(message)
            if message:
                self.last_received = time.time()
                if "ok_btccny_depth" in message:
                    self._market_depth = json.loads(message)
                
                elif "ok_spotcny_trade" in message: pass
                    
                elif "ok_cny_realtrades" in message:
                    order_info = message[0].get('data', None)
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

    def _subscribe_market_depth(self):
        self.ws.write_message("{'event': 'addChannel', 'channel': 'ok_btccny_depth60'}")

    def _subscribe_realtrades(self):
        self.ws.write_message(json.dumps({
                    'event':        'addChannel',
                    'channel':      'ok_cny_realtrades',
                    'parameters':   {
                            'api_key':  self.access_key,
                            'sign' :    md5(urlencode(OrderedDict(sorted({'api_key':self.access_key}.items()))) + '&secret_key=' + self.secret_key).hexdigest().upper(),
                }}))

    @property
    def market_depth(self):
        if not hasattr(self, "_market_depth"):
            self._market_depth = {}

        return self._market_depth

    def sell(self, amount):
        #实时按市价单，挂单
        self.ws.write_message(json.dumps({
                'event': 'addChannel',
                'channel': 'ok_spotcny_trade',
                'parameters': {
                        'api_key':  self.access_key,
                        'sign' :    md5(urlencode(OrderedDict(sorted({'amount':amount, 'api_key':self.access_key, 'type':'sell_market', 'symbol':'btc_cny'}.items()))) + '&secret_key=' + self.secret_key).hexdigest().upper(),
                        'symbol':   'btc_cny',
                        'type':     'sell_market',
                        'amount':   amount
            }}))
    