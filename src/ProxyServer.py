# https://proxybroker.readthedocs.io

class ProxyServer():
    from src.utils import PrintLogger
    
    def __init__(
                    self,
                    _async_handler, 
                    proxy_file_path = None, 
                    no_of_proxies = 5, 
                    dump_info = PrintLogger.register('ProxyServer')):
        
        if not proxy_file_path:
            proxy_file_path = 'PROXY_LIST.txt'
            
        self.path = proxy_file_path
        self.no_of_proxies = 5
        self.ash = _async_handler
        self.dump_info = dump_info
        
        self.proxy_queue = self.ash.add_queue('proxies')
        
        from src.utils import install_pip_pkg
        install_pip_pkg({'proxybroker'})
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=DeprecationWarning)
            from proxybroker import Broker
        
        self.broker = Broker(self.proxy_queue)
            
    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.dump_info().log('Exiting ProxyServer')     
        if exc_type:
            print(exc_type, exc_value, exc_traceback)
            
    async def get_a_proxy(self):
        """
        Get proxies from proxy queue until queue is empty.
        """
        self.dump_info().log(f'Proxy queue has currently {self.proxy_queue.qsize()} items.')
        
        while True: #not self.proxy_queue.empty():         
            self.dump_info().log('Waiting to receive proxies.')
            proxy = await self.proxy_queue.get()
            self.proxy_queue.task_done()
            
            if proxy and proxy.is_working:
                protocol = 'https'
                line = f'{protocol}://{proxy.host}:{proxy.port}'
                yield line
            else:
                self.dump_info().log(f'Disregarding invalid proxy {proxy} .')

    async def get_proxy(self):
        from src.AsyncHandler import AsyncHandler as ash

        proxy_string = await ash.yielder(self.get_a_proxy)
        while not proxy_string:
            await self.find_proxies()
            proxy_string = await ash.yielder(self.get_a_proxy)
         
        return self.read_proxy_string(proxy_string)
    
    def read_proxy_string(self, proxy_str):
        # i.e. proxy_str = 'https://163.116.131.129:8080'
        [ip, port] = proxy_str.lstrip('https://').split(':') 
        port = int(port)
        return ip, port
    
    async def find_proxies(self):
        european_country_codes = ['DE', 'AT', 'FR', 'UK', 'IT', 'HU', 'IE', 'GR', 'LV', 'LT', 'NL', 'PL', 'RO', 'SK', 'SI', 'ES', 'SE', 'BE', 'BG', 'HR', 'DK', 'EE', 'FI']
        with self.dump_info('Searching for new proxies.'):
            producer = self.ash.create_task(self.broker.find(
                                    types=['HTTPS'], 
                                    limit= self.no_of_proxies, 
                                    countries = european_country_codes))
            #await producer