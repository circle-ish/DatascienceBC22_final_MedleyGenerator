# https://yt.lemnoslife.com/

class YoutubeHandler():
    from src.utils import PrintLogger
    
    def __init__(self, _async_handler, dump_info):
        self.proxy_handler = None
        self.user_agent = None
        self.ash = _async_handler        
        self.dump_info = dump_info
            
    def __exit__(self, exc_type, exc_value, exc_traceback):
        
        with self.dump_info('Exiting YoutubeHandler'):
            del self.user_agent
            del self.ash        
            del self.proxy_handler
            del self.dump_info

            self.proxy_handler = None
            self.user_agent = None
            self.ash = None        
            self.dump_info = None
        
        if exc_type:
            print(exc_type, exc_value, exc_traceback)        
            
    async def setup(self):
        with self.dump_info('Starting Proxy Server'):
            from src.ProxyServer import ProxyServer
            self.proxy_handler = ProxyServer(_async_handler = self.ash)
            await self.proxy_handler.find_proxies()
             
        await self.setup_connection()
        
    async def setup_connection(self):
        await YoutubeHandler.set_proxy_for_running(self)
        YoutubeHandler.set_user_agent_for_running(self)
        
    # following https://stackoverflow.com/a/54713821/19347187
    async def set_proxy_for_running(self):      
        self.dump_info().log('Waiting for Proxy Server')
        proxy_ip, proxy_port = await self.proxy_handler.get_proxy()
        self.dump_info().log('Got a Proxy')
        was_success = self.set_proxy_for_running(proxy_ip, proxy_port)
        if was_success:
            self.dump_info().log(f'Using proxy = https://{proxy_ip}:{proxy_port}.') 
        else:
            self.dump_info().log(f'Setting proxy FAILED.') 
      
    def set_user_agent_for_running(self):
        if not self.user_agent:
            from src.utils import install_pip_pkg
            install_pip_pkg({'fake_useragent'})
            
            from fake_useragent import UserAgent
            self.user_agent = UserAgent()
            
        user_agent = self.user_agent.random
        was_success = self.set_user_agent_for_running(user_agent)
        
        if was_success:
            self.dump_info().log(f'Using user-agent {user_agent}.') 
        else:
            self.dump_info().log(f'Setting proxy FAILED.') 

    async def get(self, url, retries = 0):
        pass
        
    async def get_most_replayed(self, vid_id, total_duration_in_ms):  
        video_path = f'https://www.youtube.com/watch?v={vid_id}'
        
        self.dump_info().log(f'Opening URL {video_path}')
        await self.get(video_path)
        
        graph = await self.get_heatmaps_from_yt(total_duration_in_ms)
        return graph 
    
    def search(self, query, return_amount = 3, skip_ids = []):
        from src.utils import PrintLogger
        
        if len(skip_ids) > 0:
            self.dump_info().log(f'Searching again for {query=}.')
            
        query = query.replace(' ', '+')
        return_amount += len(skip_ids)
        
        # order = {date, rating, relevance, title, videoCount, viewCount) see above link
        lemnos_yt_url = f'https://yt.lemnoslife.com/search?part=id,snippet&q={query}&type=video&order=viewCount'

        import requests
        response = requests.get(lemnos_yt_url)
        if response.status_code != 200:
            raise Exception(f'Returned code {response.status_code} for url = {lemnos_yt_url}')

        import json
        yt_search = response.json()['items']
        
        vid_ids, vid_names = [], []
        i = 0 
        while (len(vid_ids) != return_amount) and (i < len(yt_search)):
            vid_id = yt_search[i]['id']['videoId']
            
            if vid_id not in skip_ids:
                vid_ids.append(vid_id)
                vid_names.append(yt_search[i]['snippet']['title'])
                
            i += 1
            
        if not vid_ids:
            return None, None
        if None in vid_names:
            self.dump_info().log(f'{PrintLogger.BOLD}Found a None {vid_names}.')
            

        # Priorise results with keywords or good matches
        keywords = ['official', 'lyrics']
        has_keywords = [any([True for key in keywords if key in vid]) for vid in vid_names if vid]
        
        from src.utils import install_pip_pkg
        install_pip_pkg({'jellyfish'})
        from jellyfish import levenshtein_distance as jf_levenshtein_distance
        match_distances = [jf_levenshtein_distance(query, result) for result in vid_names]
        
        candidates = [(i, match_distances[i]) for i, booly in enumerate(has_keywords) if booly]
        candidates = sorted(candidates, key = lambda x: x[1])
        
        best = None
        if candidates:
            best = candidates[0][0]
        else:
            min_distance = min(match_distances)
            best = [i for i, dist in enumerate(match_distances) if dist == min_distance][0]

        self.dump_info().log(f'For {query=} choosing YT video {PrintLogger.BOLD}{vid_names[best]}.')
        return vid_ids[best], vid_names[best]
