# -*- coding : utf-8 -*-
import exchange_api, json, pymongo
from exchange_api import ExchangeAPIManager
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen


class StrategyTrading(object):

    def __init__(self, config):
        self.api = ExchangeAPIManager()
        self.configuration = config
        self.exchange_depth = {}
   
        PeriodicCallback(self._detect_keepalive, 1000).start()

    def _detect_keepalive(self):
        self.api.sell('okcoin', 0.01)
        self.api.sell('huobi', 0.01)    

    def _update_exchange_depth(self):
        for exchange in self.configuration['exchanges'].keys():
            if exchange is 'okcoin' or 'huobi':
                try:    
                    self.exchange_depth[exchange] = self.api.market_depth(exchange)['data']['bids'] if type(self.api.market_depth(exchange)) is dict else self.api.market_depth(exchange)[0]['data']['bids']
                except :
                    pass

    def _get_asks_for_iceberg_sell(self, exchange_depth, btc_vol):
        bids = sorted([(exchange, bid[0], bid[1]) for exchange, bids in exchange_depth.iteritems() for bid in bids], key=lambda v: v[1], reverse=True)

        results = {}
        for exchange, price, vol in bids:
            if btc_vol <= 0:
                break

            if vol > btc_vol:
                vol = btc_vol

            if exchange not in results:
                results[exchange] = vol

            else:
                results[exchange] += vol

            btc_vol -= vol

        return {exchange: round(vol, 4) for exchange, vol in results.iteritems()}

   
    @gen.coroutine
    def initialize_exchange_api(self, exchanges=None):
        for exchange in exchanges if exchanges else self.configuration['exchanges'].keys():
            try:
                yield self.api.connect(exchange, 
                            url=self.configuration['exchanges'][exchange]['url'], 
                            access_key=self.configuration['exchanges'][exchange]['access_key'], 
                            secret_key=self.configuration['exchanges'][exchange]['secret_key'],
                        )
            except Exception as e:
                print "error : %s " % e
                pass

        raise gen.Return(None)

    def get_btc_vol(self, cny_vol):
        self._update_exchange_depth()
        results = {}
        for exchange, bids in self.exchange_depth.iteritems():
            remainder_cny_vol = cny_vol
            for bid in bids :
                if exchange not in results: 
                    results[exchange] = bid[0]*bid[1]
                
                else:
                    results[exchange] += bid[0]*bid[1]
                
                remainder_cny_vol -= bid[0]*bid[1]
                if remainder_cny_vol <= 0:                
                    results[exchange] = [round((float(cny_vol)/bid[0])*(1+self.configuration['risk_fund_proportion']),4),bid[0]]
                    break

            if remainder_cny_vol >0 :
                results[exchange] =[]

        return max(results.itervalues())

    def iceberg_sell_btc(self, btc_vol):
        self._update_exchange_depth()
        for exchange, sell_btc_vol in self._get_asks_for_iceberg_sell(self.exchange_depth, btc_vol).iteritems():
            self.api.sell(exchange, sell_btc_vol)

@gen.coroutine
def run():
    strategy_trade = StrategyTrading({
            'exchanges': {
                'okcoin': {
                    'access_key': 'abbb0998-1025-4d7f-a9d9-0782165b8e45',
                    'secret_key': '50B73F0D7FFB5FC44FF4CB5533940640',
                    'url': 'wss://real.okcoin.cn:10440/websocket/okcoinapi'
                          },
                 'huobi': {
                    'access_key': 'b8ac44db-7e0d8900-1054b696-017c5',
                    'secret_key':  '6eb1923d-d3cf48b2-08f85509-7c205',
                    'url': 'ws://106.38.234.75:9527/huobiws/huobiapi'
                          },
                          },
            'risk_fund_proportion': 0.1
                                 })
    yield strategy_trade.initialize_exchange_api()

    raise gen.Return(None)
    
if __name__ == "__main__":
    ioloop = IOLoop.instance()
    ioloop.add_callback(run)
    ioloop.start()
