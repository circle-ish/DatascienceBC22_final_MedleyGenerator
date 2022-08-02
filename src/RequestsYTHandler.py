from src.YoutubeHandler import YoutubeHandler

class RequestsYTHandler(YoutubeHandler):
    from src.utils import PrintLogger
    
    def __init__(self, dump_info = PrintLogger.register('RequestsYTHandler'), *args, **kwargs):
        self.response = None
        self.session = None
        YoutubeHandler.__init__(self, dump_info = dump_info, *args, **kwargs)
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        
        self.quit_connection()
        del self.dump_info
        self.dump_info = None
        
        del self.response
        self.response = None
        
        YoutubeHandler.__exit__(self, exc_type, exc_value, exc_traceback)
   
    def quit_connection(self):
        del self.session
        self.session = None
            
    def init_session(self):
        import requests
        self.session = requests.Session()
        
    async def setup_connection(self):
        if self.session:
            self.quit_connection()
        
        self.init_session()
        YoutubeHandler.setup_connection(self)
        
    async def set_proxy_for_running(self, proxy_ip, proxy_port):
        # format "http://10.10.1.11:1080"
        # has to be 'http' even for https
        proxy_string = f'http://{proxy_ip}:{proxy_port}'
        proxy = {'https': proxy_string, 'http': proxy_string}

        self.session.proxies = proxies
        return True
            
    def set_user_agent_for_running(self, user_agent):        
        # user agent
        headers = {'user-agent': user_agent}
        self.session.headers.update(headers)
        
        return True
        
    async def get(self, url, retries = 0):
        from requests.exceptions import ProxyError
        from requests.exceptions import ConnectionError
        import requests 

        self.response = None
        while not self.response:
            try:
                self.response = requests.get(url, timeout=10)
            except ProxyError as pe:
                if retries < 3:
                    self.dump_info().log('Changing proxy.')
                    YoutubeHandler.set_proxy_for_running(self)
                self.response = None
            except ConnectionError as ce:
                self.dump_info().log('Connection Error.', important=True)

            if self.response and (retries < 3) and (self.response.url != url):     # redirected to captcha
                self.dump_info().log('Ran into captcha police. New proxy and user agent.')
                await YoutubeHandler.set_proxy_for_running(self)
                YoutubeHandler.set_user_agent_for_running(self)
                self.response = None
                
            # if an error occurs above, the flow enters here and increases retries counter
            if not self.response:
                if retries >=3:  
                    raise RuntimeError(f'Could not load {url=}')
                else:
                    self.dump_info().log(f'Reloading: {retries + 1}. retry.')
                    retries += 1
                    await self.get(url, retries = retries)
    
    async def get_heatmaps_from_yt(self, total_duration_in_sec):
        # cannot use json directly on full response; regex search first
        from re import findall as re_findall
        
        # following https://github.com/Benjamin-Loison/YouTube-operational-API/blob/13e620da9a64ea775fb655dbac2290f86aec4e05/tools/DisplayMostReplayedGraph.py
        pattern = r'{"heatMarkerRenderer":{"timeRangeStartMillis":(\d+),"markerDurationMillis":(\d+),"heatMarkerIntensityScoreNormalized":(\d+.\d+)}}'
        yt_string = self.response.text
        
        matches = re_findall(pattern, yt_string)
        (time_start_in_ms, duration_in_ms, score) = \
                            list(zip(*[(float(a), float(b), float(c)) for a,b,c in matches]))
        
        max_time = time_start_in_ms[-1]
        
        graph = {}
        graph['x'] = list(map(lambda x: x / max_time * total_duration_in_sec, time_start_in_ms))
        graph['y'] = score
        return graph
