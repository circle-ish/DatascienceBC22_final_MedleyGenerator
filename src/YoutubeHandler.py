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
            del self.net_connection

            self.proxy_handler = None
            self.user_agent = None
            self.ash = None        
            self.dump_info = None
            self.net_connection = None
        
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
        proxy_ip, proxy_port = await self.ash.get_proxy()
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
        
    async def get_most_replayed(self, vid_id, total_duration_in_sec):  
        video_path = f'https://www.youtube.com/watch?v={vid_id}'
        
        self.dump_info().log(f'Opening URL {video_path}')
        await self.get(video_path)
        
        graph = await self.get_heatmaps_from_yt(total_duration_in_sec)
        return graph 
    
    def search(self, query):
        query = query.replace(' ', '+')
        
        # order = {date, rating, relevance, title, videoCount, viewCount) see above link
        lemnos_yt_url = f'https://yt.lemnoslife.com/search?part=id,snippet&q={query}&type=video&order=viewCount'

        import requests
        response = requests.get(lemnos_yt_url)
        if response.status_code != 200:
            raise Exception(f'Returned code {response.status_code} for url = {lemnos_yt_url}')

        import json
        yt_search = response.json()['items']
        
        video_number = 0  #                                        <<<<--- not productive
        vid_id = yt_search[video_number]['id']['videoId']
        vid_name = yt_search[video_number]['snippet']['title']

        # TODO Priorise results with keywords
        keywords = ['official', 'lyrics']
        
        return vid_id, vid_name
