from src.YoutubeHandler import YoutubeHandler

class SeleniumHandler(YoutubeHandler):
    from src.utils import PrintLogger
    
    def __init__(self, dump_info = PrintLogger.register('SeleniumYTHandler'), *args, **kwargs):
        self.ff_webdriver = None
        self.virt_browser = None
        
        YoutubeHandler.__init__(self, dump_info = dump_info, *args, **kwargs)
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.quit_net_connection()
        
        del self.dump_info
        self.dump_info = None
        
        YoutubeHandler.__exit__(self, exc_type, exc_value, exc_traceback)
   
    def quit_connection(self):
        from selenium.common.exceptions import WebDriverException
        
        with self.dump_info('Closing browser.'):
            try:
                self.ff_webdriver.quit()
            except WebDriverException as wd_exc:
                pass

            del self.ff_webdriver
            del self.virt_browser
            
            self.ff_webdriver = None
            self.virt_browser = None 
            
    async def setup_connection(self):
        if self.ff_webdriver:
            self.quit_connection()
        
        self.init_virt_browser()
        YoutubeHandler.setup_connection(self)
        
    def init_virt_browser(self, options = None, wait_in_sec = 15):
        from selenium import webdriver 
        from selenium.webdriver.support.ui import WebDriverWait 
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        import os

        driver_path = r'geckodriver\geckodriver.exe'
        driver_path = os.path.join(os.getcwd(), driver_path)

        if not options:
            options = Options()
        #options.headless = True
        
        #  -----------DEPRECATED-------------
        # following https://newbedev.com/how-can-i-make-a-selenium-script-undetectable-using-geckodriver-and-firefox-through-python
        #options.set_preference("dom.webdriver.enabled", False)
        #options.set_preference('useAutomationExtension', False)
        #options.update_preferences()
        
        with self.dump_info('Initialising Selenium Webdriver'):
            try:
                self.ff_webdriver = webdriver.Firefox(options=options, service = Service(driver_path))
            except WebDriverException as wd_exc:
                raise wd_exc
        
        with self.dump_info('Initialising Selenium WaitWebdriver'):
            self.virt_browser = WebDriverWait(self.ff_webdriver, wait_in_sec)

    # following https://stackoverflow.com/a/54713821/19347187
    async def set_proxy_for_running(self, proxy_ip, proxy_port):   
        self.ff_webdriver.execute("SET_CONTEXT", {"context": "chrome"})

        try:
            self.ff_webdriver.execute_script("""
              Services.prefs.setIntPref('network.proxy.type', 1);
              Services.prefs.setCharPref("network.proxy.http", arguments[0]);
              Services.prefs.setIntPref("network.proxy.http_port", arguments[1]);
              Services.prefs.setCharPref("network.proxy.ssl", arguments[0]);
              Services.prefs.setIntPref("network.proxy.ssl_port", arguments[1]);
              """, proxy_ip, proxy_port)
             
        except Exception as e:
            return False
        finally:
            self.ff_webdriver.execute("SET_CONTEXT", {"context": "content"})
            
        return True
            
    def set_user_agent_for_running(self, user_agent):        
        self.ff_webdriver.execute("SET_CONTEXT", {"context": "chrome"})

        try:
            self.ff_webdriver.execute_script("""
              Services.prefs.setIntPref('general.useragent.override', arguments[0]);
              """, user_agent)  
        except Exception as e:
            return False
        finally:
            self.ff_webdriver.execute("SET_CONTEXT", {"context": "content"})  
            
        new_agent = self.ff_webdriver.execute_script("return navigator.userAgent")
        if new_agent == user_agent:
            return True
        else:
            return True
        
    async def get(self, url, retries = 0):
        from selenium.common.exceptions import WebDriverException, InvalidSessionIdException
        
        try:
            self.ff_webdriver.get(url)
        except InvalidSessionIdException as is_exc:
            self.dump_info().log('Re-opening browser.')
            self.setup_connection()
            await self.get(url)
            
        except WebDriverException as wd_exc:
            self.dump_info().log(f'Reloading: {retries + 1}. retry.')
            if retries >=3:  
                raise wd_exc
            else:
                retries += 1
                await YoutubeHandler.set_proxy_for_running(self)
                await self.get(url, retries = retries)

    async def locate_by_css(self, css_string, attribute_string):
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
                    await YoutubeHandler.set_proxy_for_running(self)
                    YoutubeHandler.set_user_agent_for_running(self)
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
                    
        result = [i.get_attribute(attribute_string) for i in result]
        return result
        
    async def get_heatmaps_from_yt(self, total_duration_in_ms):            
        scrape_dict = {
            'heatmap' : ('.ytp-heat-map-path', 'd'),
            'chapters': ('.ytp-heat-map-chapter', 'style')
        }
        
        with self.dump_info(f'Attempting to scrape heat map.'):
            heatmaps = await self.locate_by_css((scrape_dict['heatmap'])

        with self.dump_info(f'Attempting to scrape chapter sizes.'):
            chapter_times = await self.locate_by_css((scrape_dict['chapters'])
        
        return self.build_graph(chapter_times, heatmaps, total_duration_in_ms)
        
    def build_graph(self, chapter_times, heatmaps, total_duration_in_ms):
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
        graph['x'] = [i * total_duration_in_ms / graph['x'][-1] for i in graph['x']]
        graph['is_regular'] = False
        return graph 
    
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