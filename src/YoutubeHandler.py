# https://yt.lemnoslife.com/

class YoutubeHandler():
    from src.utils import PrintLogger
    
    def __init__(self, _async_handler, dump_info = PrintLogger.register('YoutubeHandler')):
        self.proxy_handler = None
        self.browser_user_agent = None
        self.ff_webdriver = None
        self.virt_browser = None
        self.ash = _async_handler        
        self.dump_info = dump_info
            
    def __exit__(self, exc_type, exc_value, exc_traceback):
        
        with self.dump_info('Exiting ProxyServer'):
            del self.ff_webdriver
            del self.virt_browser
            del self.browser_user_agent
            del self.ash        
            del self.proxy_handler
            del self.dump_info

            self.proxy_handler = None
            self.browser_user_agent = None
            self.ff_webdriver = None
            self.virt_browser = None
            self.ash = None        
            self.dump_info = None
        
        if exc_type:
            print(exc_type, exc_value, exc_traceback)
                 
    async def setup(self, **kwargs):        
        proxy_file_path = kwargs.get('proxy_file', None)
        
        with self.dump_info('Starting Proxy Server'):
            from src.ProxyServer import ProxyServer
            self.proxy_handler = ProxyServer(_async_handler = self.ash)
            await self.proxy_handler.find_proxies()
             
        await self.setup_browser(**kwargs)
        
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
        
        # following https://newbedev.com/how-can-i-make-a-selenium-script-undetectable-using-geckodriver-and-firefox-through-python
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference('useAutomationExtension', False)
        #options.update_preferences()
        
        with self.dump_info('Initialising Selenium Webdriver'):
            try:
                self.ff_webdriver = webdriver.Firefox(options=options, service = Service(driver_path))
            except WebDriverException as wd_exc:
                raise wd_exc
        
        with self.dump_info('Initialising Selenium WaitWebdriver'):
            self.virt_browser = WebDriverWait(self.ff_webdriver, wait_in_sec)

    # following https://stackoverflow.com/a/54713821/19347187
    async def set_proxy_for_running(self):            
        proxy_ip, proxy_port = await self.get_proxy()
        self.ff_webdriver.execute("SET_CONTEXT", {"context": "chrome"})

        try:
            self.ff_webdriver.execute_script("""
              Services.prefs.setIntPref('network.proxy.type', 1);
              Services.prefs.setCharPref("network.proxy.http", arguments[0]);
              Services.prefs.setIntPref("network.proxy.http_port", arguments[1]);
              Services.prefs.setCharPref("network.proxy.ssl", arguments[0]);
              Services.prefs.setIntPref("network.proxy.ssl_port", arguments[1]);
              """, proxy_ip, proxy_port)
            
            self.dump_info().log(f'Using proxy = https://{proxy_ip}:{proxy_port}.')  

        finally:
            self.ff_webdriver.execute("SET_CONTEXT", {"context": "content"})
            
      
    def set_user_agent_for_running(self):
        if not self.browser_user_agent:
            from src.utils import install_pip_pkg
            install_pip_pkg({'fake_useragent'})
            
            from fake_useragent import UserAgent
            self.browser_user_agent = UserAgent()
            
        userAgent = self.browser_user_agent.random
        
        self.ff_webdriver.execute("SET_CONTEXT", {"context": "chrome"})

        try:
            self.ff_webdriver.execute_script("""
              Services.prefs.setIntPref('general.useragent.override', arguments[0]);
              """, userAgent)
            

        finally:
            self.ff_webdriver.execute("SET_CONTEXT", {"context": "content"})  
            
        new_agent = self.ff_webdriver.execute_script("return navigator.userAgent")
        if new_agent == userAgent:
            self.dump_info().log(f'Using new user agent = {userAgent}.') 
        else:
            self.dump_info().log(f'Setting new user agent failed.') 
            
        
    async def get_proxy(self):
        proxy_string = await self.ash.yielder(self.proxy_handler.get_random_proxy)
        if not proxy_string:
            self.dump_info().log('Requesting new proxies.')
            await self.proxy_handler.find_proxies()
            proxy_string = await self.ash.yielder(self.proxy_handler.get_random_proxy)
         
        return self.read_proxy_string(proxy_string)
    
    def read_proxy_string(self, proxy_str):
        # i.e. proxy_str = 'https://163.116.131.129:8080'
        [ip, port] = proxy_str.lstrip('https://').split(':') 
        port = int(port)
        return ip, port
    
    def quit_browser(self):
        from selenium.common.exceptions import WebDriverException
        
        with self.dump_info('Closing browser.'):
            try:
                self.ff_webdriver.quit()
            except WebDriverException as wd_exc:
                pass

            #try:
            #    self.ff_webdriver.close()
            #except WebDriverException as wd_exc:
            #    pass

            del self.ff_webdriver
            del self.virt_browser
        
    async def setup_browser(self, **kwargs):
        if self.ff_webdriver or self.virt_browser:
            self.quit_browser()
        
        #ip, port = await self.get_proxy()
        #options = await self.set_proxy_options(ip, port)
        self.init_virt_browser() #options = options,
        await self.set_proxy_for_running()
        self.set_user_agent_for_running()
    
    async def get(self, url, retries = 0):
        from selenium.common.exceptions import WebDriverException, InvalidSessionIdException
        
        try:
            self.ff_webdriver.get(url)
        except InvalidSessionIdException as is_exc:
            self.dump_info().log('Re-opening browser.')
            setup_browser()
            
        except WebDriverException as wd_exc:
            self.dump_info().log(f'Reloading: {retries + 1}. retry.')
            if retries >=3:  
                raise wd_exc
            else:
                retries += 1
                await self.set_proxy_for_running()
                await self.get(url, retries = retries)
        
    async def locate_by_css(self, css_string):
        from selenium.webdriver.common.by import By 
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, InvalidSessionIdException
        
        result = None
        while not result:
            
            try:
                result = (
                    self.virt_browser.until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, css_string)
                        )
                    )
                )
            except TimeoutException:
                current_url = self.virt_browser._driver.current_url
                if current_url.find('/sorry/') != -1: 
                    self.dump_info().log('Ran into captcha police. New proxy, user agent and reloading.')
                    await self.set_proxy_for_running()
                    self.set_user_agent_for_running()
                result = None
                
            except InvalidSessionIdException as is_exc:
                self.dump_info().log('Re-opening browser.')
                setup_browser()
                result = None
            
            except (NoSuchElementException, Exception) as ex:
                self.dump_info().log('TimeoutException. Reloading.')
                result = None
            finally:
                if not result:
                    await self.get(self.virt_browser._driver.current_url)
                    
        return result
        
    async def get_most_replayed(self, vid_id, total_duration_in_sec):  
        chapter_times, heatmaps = await self.get_heatmaps_from_yt(vid_id)
        graph = self.build_graph(chapter_times, heatmaps, total_duration_in_sec)
        return graph 
    
    async def get_heatmaps_from_yt(self, vid_id):
        if not self.virt_browser:
            self.virt_browser = init_virt_browser()
            
        #
        video_path = f'https://www.youtube.com/watch?v={vid_id}'
        
        self.dump_info().log(f'Opening URL')
        await self.get(video_path)

        with self.dump_info(f'Attempting to scrape heat map.'):
            heatmaps = await self.locate_by_css('.ytp-heat-map-path')
        heatmaps = [d.get_attribute('d') for d in heatmaps]

        with self.dump_info(f'Attempting to scrape chapter sizes.'):
            chapter_times = await self.locate_by_css('.ytp-heat-map-chapter')    
        chapter_times = [time.get_attribute('style') for time in chapter_times]
    
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
            self.dump_info().log(f'Assembling popularity graph. Last tuple for chapter: {coords[0][-1]},{coords[1][-1]}')
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
    
    
    # deprecated
    async def set_proxy_options(self, ip, port):
        from selenium.webdriver.firefox.options import Options    
        
        options = Options()
        options.set_preference("network.proxy.type", 1)
        options.set_preference("network.proxy.http", ip)    
        options.set_preference("network.proxy.http_port", port)
        options.set_preference("network.proxy.ssl", ip)    
        options.set_preference("network.proxy.ssl_port", port)


            
        userAgent = self.browser_user_agent.random
        options.add_argument(f'user-agent={userAgent}')  
        
        return options
