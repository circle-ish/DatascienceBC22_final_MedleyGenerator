# https://proxybroker.readthedocs.io

class ProxyServer():
    
    def __init__(self, async_handler, proxy_file_path, no_of_proxies = 5):
        if not proxy_file_path:
            proxy_file_path = 'PROXY_LIST.txt'
            
        self.path = proxy_file_path
        self.no_of_proxies = 5
        self.ash = async_handler
        
        self.proxy_queue = self.ash.add_queue('proxies')

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

    async def find_proxies(self):
        
        # needs to be here before importing the broker; see open issue (Jul '22):
        # https://github.com/streamlit/streamlit/issues/744#issuecomment-686712930
        #loop = asyncio.new_event_loop()
        #asyncio.set_event_loop(loop)
        
        from src.utils import install_pip_pkg
        install_pip_pkg({'proxybroker'})
        
        from proxybroker import Broker

        european_country_codes = ['DE', 'AT', 'FR', 'UK', 'IT', 'HU', 'IE', 'GR', 'LV', 'LT', 'NL', 'PL', 'RO', 'SK', 'SI', 'ES', 'SE', 'BE', 'BG', 'HR', 'DK', 'EE', 'FI']
        broker = Broker(self.proxy_queue)
        producer = self.ash.create_task(broker.find(
                                                    types=['HTTPS'], 
                                                    limit= self.no_of_proxies, 
                                                    countries = european_country_codes))
        #consumer = self.ash.create_task(self.get_random_proxy(proxies))
        
        #await self.ash.gather(producer)
        #await proxies.join()
        #consumer.cancel()
        
        #tasks = asyncio.gather(broker.find(
        #                            types=['HTTPS'], 
        #                            limit= self.no_of_proxies, 
        #                            countries = european_country_codes),
        #                       self.save(proxies, filename= self.path))
        #self.loop = asyncio.get_event_loop()
        #try:
        #    asyncio.run(tasks)
        #    self.loop.run_until_complete(tasks)
        #except RuntimeError as rte:
        #    print(rte)
        #finally:
        #    self.loop.stop()
        #    pass

        # following this example
        # https://github.com/LonamiWebs/Telethon/issues/825#issuecomment-395008836
        def __exit__(self, exc_type, exc_value, exc_traceback):
            '''if exc_type and self.loop:
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()
                self.loop.run_until_complete(asyncio.gather(*pending, loop=self.loop))
                self.loop.close()'''