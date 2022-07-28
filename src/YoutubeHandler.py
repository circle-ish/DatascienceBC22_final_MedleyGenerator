# https://yt.lemnoslife.com/

class YoutubeHandler():
    import requests
    import json
    from src.utils import PrintLogger
    
    def __init__(self, _async_handler, dump_info = PrintLogger.register()):
        self.virt_browser = None
        self.browser_user_agent = None
        self.proxy_server = None
        self.ash = _async_handler        
        self.dump_info = dump_info
            
    async def setup(self, **kwargs):        
        proxy_file_path = kwargs.get('proxy_file', None)
        
        with self.dump_info('YoutubeHandler: Starting Proxy Server'):
            from src.ProxyServer import ProxyServer
            self.proxy_handler = ProxyServer(self.ash, proxy_file_path)
            await_proxies = self.proxy_handler.find_proxies()
            await await_proxies
                   
            options = self.set_proxy_options(await self.ash.yielder(self.proxy_handler.get_random_proxy))
        self.init_virt_browser(options = options, wait_in_sec = kwargs.get('wait', None))
        
    def init_virt_browser(self, options = None, wait_in_sec = 15):
        from selenium import webdriver 
        from selenium.webdriver.support.ui import WebDriverWait 
        #from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        import os

        driver_path = r'geckodriver\geckodriver.exe'
        driver_path = os.path.join(os.getcwd(), driver_path)

        if not options:
            options = Options()
        #options.headless = True
        
        if not wait_in_sec:
            wait_in_sec = 15
        
        
        with self.dump_info('YoutubeHandler: Initialising Selenium Webdriver'):
            try:
                self.ff_webdriver = webdriver.Firefox(options=options, service = Service(driver_path))
            except WebDriverException as wd_exc:
                raise wd_exc
        
        with self.dump_info('YoutubeHandler: Initialising Selenium WaitWebdriver'):
            self.virt_browser = WebDriverWait(self.ff_webdriver, wait_in_sec)

    def set_proxy_options(self, proxy_str = None):
        from selenium.webdriver.firefox.options import Options    

        if not proxy_str:
            pass
        
        # i.e. proxy_str = 'https://163.116.131.129:8080'
        [ip, port] = proxy_str.lstrip('https://').split(':') 
        port = int(port)
        
        options = Options()
        options.set_preference("network.proxy.type", 1)
        options.set_preference("network.proxy.http", ip)    
        options.set_preference("network.proxy.http_port", port)
        options.set_preference("network.proxy.ssl", ip)    
        options.set_preference("network.proxy.ssl_port", port)

        if not self.browser_user_agent:
            from src.utils import install_pip_pkg
            install_pip_pkg({'fake_useragent'})
            
            from fake_useragent import UserAgent
            self.browser_user_agent = UserAgent()
            
        userAgent = self.browser_user_agent.random
        options.add_argument(f'user-agent={userAgent}')  
        
        return options

    def quit(self):
        self.ff_webdriver.quit()
        
    def get_browsers(self):
        return self.ff_webdriver, self.virt_browser
    
    def get(self, url):
        self.ff_webdriver.get(url)
        
    def locate_by_css(self, css_string):
        from selenium.webdriver.common.by import By 
        from selenium.webdriver.support import expected_conditions as EC
        try:
            result = (
                self.virt_browser.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, css_string)
                    )
                )
            )
        except (TimeoutException, Exception) as ex:
            print(ex, ex.args)
        
        return result
        
    def get_most_replayed(self, vid_id, total_duration_in_sec):  
        chapter_times, heatmaps = self.get_heatmaps_from_yt(vid_id)
        graph = self.build_graph(chapter_times, heatmaps, total_duration_in_sec)
        return graph 
    
    def get_heatmaps_from_yt(self, vid_id):
        if not self.virt_browser:
            self.virt_browser = init_virt_browser()
            
        #
        video_path = f'https://www.youtube.com/watch?v={vid_id}'
        self.get(video_path)
        
        heatmaps = self.locate_by_css('.ytp-heat-map-path')
        
        result_len = len(heatmaps)
        if result_len > 1:
            chapter_times = self.locate_by_css('.ytp-heat-map-chapter')    
            chapter_times = [time.get_attribute('style') for time in chapter_times]
        else:
            chapter_times = [0, duration]
        heatmaps = [d.get_attribute('d') for d in heatmaps]
    
        return chapter_times, heatmaps

    def build_graph(self, chapter_times, heatmaps, total_duration_in_sec):
        from re import findall as re_findall
        from re import match as re_match
        
        graph = {'x': [], 'y': []}
        for i, time in enumerate(chapter_times):
            # do not represent actual ms times but px factors inside of youtube's progress bar
            duration_factor, offset_factor = re_match(r'width: (\d+)px; left: (\d+)px;', time).group(1, 2)  

            # regex for x,y pairs; first pair is always 0.0,100.0 
            # the last pair is something weird; seems out of bounds
            coords = re_findall(r'\s([\d.]+,[\d.]+)\s', heatmaps[i])[1:]

            # split into x and y list
            coords = list(zip(*[coord.split(',') for coord in coords]))

            #print(duration_factor, offset_factor,coords[0][2], coords[0][-2])
            tmp = [(float(i) * float(duration_factor) / 1000.0) + float(offset_factor) for i in coords[0]]
            graph['x'].extend(tmp)
            graph['y'].extend([100.0 - float(i) for i in coords[1]])

        assert graph['x'][-1] == max(graph['x'])
        graph['x'] = [i * total_duration_in_sec / graph['x'][-1] for i in graph['x']]
        return graph 
    
    def search(self, query):
        query = query.replace(' ', '+')
        
        # order = {date, rating, relevance, title, videoCount, viewCount) see above link
        lemnos_yt_url = f'https://yt.lemnoslife.com/search?part=id,snippet&q={query}&type=video&order=viewCount'

        response = requests.get(lemnos_yt_url)
        if response.status_code != 200:
            raise Exception(f'Returned code {response.status_code} for url = {lemnos_yt_url}')

        yt_search = response.json()['items']
        
        video_number = 0  #                                        <<<<--- not productive
        vid_id = yt_search[video_number]['id']['videoId']
        vid_name = yt_search[video_number]['snippet']['title']

        # TODO Priorise results with keywords
        keywords = ['official', 'lyrics']
        
        return vid_id, vid_name
    
    
    