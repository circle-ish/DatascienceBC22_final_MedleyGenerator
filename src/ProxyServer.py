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
            
    async def get_random_proxy(self):
        """
        Get random proxy from proxy queue
        """
        from random import choice as random_choice
        
        while True:
            proxy = await self.proxy_queue.get()
            self.proxy_queue.task_done()
            
            if proxy is None:
                break

            # Check accurately if the proxy is working.
            if proxy.is_working:
                protocol = 'https'
                line = f'{protocol}://{proxy.host}:{proxy.port}\n'
                yield line

            
    async def get_proxy(self):
        from src.AsyncHandler import AsyncHandler as ash

        proxy_string = await ash.yielder(self.get_random_proxy)
        if not proxy_string:
            self.dump_info().log('Requesting new proxies.')
            await self.find_proxies()
            proxy_string = await ash.yielder(self.get_random_proxy)
         
        return self.read_proxy_string(proxy_string)
    
    def read_proxy_string(self, proxy_str):
        # i.e. proxy_str = 'https://163.116.131.129:8080'
        [ip, port] = proxy_str.lstrip('https://').split(':') 
        port = int(port)
        return ip, port
    
    async def find_proxies(self):
        european_country_codes = ['DE', 'AT', 'FR', 'UK', 'IT', 'HU', 'IE', 'GR', 'LV', 'LT', 'NL', 'PL', 'RO', 'SK', 'SI', 'ES', 'SE', 'BE', 'BG', 'HR', 'DK', 'EE', 'FI']
        producer = self.ash.create_task(self.broker.find(
                                                    types=['HTTPS'], 
                                                    limit= self.no_of_proxies, 
                                                    countries = european_country_codes))
        
    # following this example
    # https://github.com/LonamiWebs/Telethon/issues/825#issuecomment-395008836
    #def __exit__(self, exc_type, exc_value, exc_traceback):
        '''if exc_type and self.loop:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            self.loop.run_until_complete(asyncio.gather(*pending, loop=self.loop))
            self.loop.close()'''