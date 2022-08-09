class MedleyGenerator():
     
    from src.utils import PrintLogger
    
    def __init__(self, player_name, _async_handler = None, _dump_info = PrintLogger.register('MedleyGenerator')):
            
        self.run_asynch_manually = False
        self.song_dict = {}
        self.dump_info = _dump_info
        self.player_name = player_name
            
        self.sp_handler = None
        self.yt_handler = None
        
        if _async_handler:
            from src.streamlit_interface import AsyncHandler
            self.ash = AsyncHandler()
        else:
            self.ash = _async_handler
            
        import asyncio
        with self.dump_info('Setting up MG'):
            ran = self.ash.run(self.setup)
            self.run_asynch_manually = not ran
    
    async def setup(self):
        self.run_asynch_manually = False
        from src.streamlit_interface import SpotifyHandler, RequestsYTHandler
        import os
        
        with self.dump_info('Setting up Connection to Spotify'):
            self.sp_handler = SpotifyHandler(_async_handler = self.ash,
                                         env_file_path = os.path.join(os.getcwd(), '.env_spotify'), 
                                         playable = True)
        
        with self.dump_info('Creating YoutubeHandler'):
            self.yt_handler = RequestsYTHandler(_async_handler = self.ash)
        with self.dump_info('Setting up Connection to Youtube'):
            await self.yt_handler.setup()
        
    def get_token(self):
        return self.sp_handler.get_token()
    
    def search_playlist(self, query):
        return self.sp_handler.search_playlist(query)
    
    def sp_play(self):
        # lambda func as opposed to functools.partials use late bindings (keeping the reference
        # to the scope of device_id but fetching it not until execution) which makes it perfect
        # to avoid problems around changing device id
    
        with self.dump_info(f'Getting Spotify device_id for {self.player_name}'):
            device_id = self.sp_handler.get_device_id(self.player_name, wait=True)
        play_func = lambda x, **kwargs: self.sp_handler.play(
                                                device_id, # device_id = 
                                                context_uri = None,
                                                uris = [x], 
                                                **kwargs)
        return play_func
    
    def toggle_play(self):
        with self.dump_info(f'Getting Spotify device_id for {self.player_name}'):
            device_id = self.sp_handler.get_device_id(self.player_name, wait=True)
        return_code = self.sp_handler.toggle_play(device_id)
        return return_code
        
    def create_medley(self, pl_uri, snippet_duration_in_sec):
        import asyncio
        
        song_queue_name = 'songs'
        self.ash.add_queue(song_queue_name)
        
        with self.dump_info('Gathering Songs'):
            ran = self.ash.run(self.gather_songs, (
                                    pl_uri, 
                                    snippet_duration_in_sec, 
                                    self.ash.get_queue(song_queue_name)))
            
            self.run_asynch_manually = not ran
                
        return MedleyContextManager(self.ash.get_queue(song_queue_name))
                   
    async def gather_songs(self, pl_uri, snippet_duration_in_sec, song_queue):
        
        self.run_asynch_manually = False
        
        # get tracks for chosen playlist
        with self.dump_info('Retrieving Songs from Spotify'):
            sp_track_uri, sp_track_names, sp_track_artists, sp_track_duration, sp_track_popularity = \
                self.sp_handler.get_playlist_tracks(pl_uri)

        # search tracks on yt
        for counter in range(len(sp_track_names)):
            yt_vid_id, yt_vid_name = self.yt_handler.search(sp_track_names[counter])

            # choose popular moments
            
            with self.dump_info(f'Grab Popularity from Youtube for "{yt_vid_name}"'):
                popularity_graph = await self.yt_handler.get_most_replayed(yt_vid_id, sp_track_duration[counter])
                snippet_start_in_ms = self.sliding_window(popularity_graph, snippet_duration_in_sec)

            uri_as_key = sp_track_uri[counter]
            await song_queue.put(Song(
                                        uri_as_key,
                                        sp_track_names[counter],
                                        sp_track_artists[counter],
                                        sp_track_duration[counter],
                                        sp_track_popularity[counter],
                                        yt_vid_id,
                                        yt_vid_name,
                                        popularity_graph,
                                        snippet_start_in_ms)
                                )


            if counter == 1:
                break # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<------------------------ testing
    
    def sliding_window(self, graph, window_size_in_sec):
        from pandas import DataFrame as pd_DataFrame
        from pandas import offsets as pd_offsets
        from pandas import to_datetime as pd_to_datetime
        
        graph_x_is_regular = graph.pop('is_regular')
        df_graph = pd_DataFrame(data = graph)
        df_graph.rename(columns = {'x': 'time', 'y': 'popularity'}, inplace=True)

        self.dump_info().log(f'Choosing best moment from popularity graph.')

        # selenium based extracted heatmaps have variable timestamps
        # requests based heatmaps are perfectly spaced
        if not graph_x_is_regular:
            # weighting popularity based on assigned duration since timeseries is irregular
            df_graph['time_shift'] = (
                    df_graph[['time']]
                        .diff()                        # difference from one row to the next
                        .set_index(df_graph.index - 1) # having the last index nan instead of the first
            )
            df_graph.fillna(0, inplace=True)
            df_graph['scaled_popularity'] = df_graph['time_shift'] * df_graph['popularity'] # linear weighting
        else:
            df_graph['scaled_popularity'] = df_graph['popularity']
                                        
        df_windowed_popularity = (
                df_graph 
                    .set_index(pd_to_datetime(df_graph['time'].array, unit='ms'))['scaled_popularity']
                    .rolling(window=f'{window_size_in_sec}s')
                    .sum()
                 )
                    
        # end of snippet because default of pd.rolling above is to write a resulting value in its 
        # right-most df entry
        snippet_end = df_windowed_popularity.idxmax()
        window_dt = pd_offsets.Second(window_size_in_sec)
                     
        # automatically floor capped at 0
        snippet_start = snippet_end - window_dt
        self.dump_info().log(f'Found highest popularity at {snippet_start.minute}:{snippet_start.second}')
        return (snippet_start.minute*60 + snippet_start.second) * 1000 

class MedleyContextManager():
    from src.utils import PrintLogger

    def __init__(self, async_song_queue, _dump_info = PrintLogger.register('MedleyContextManager')):    
        from datetime import datetime as dt 
        
        # is a dict to be able to pass it by reference: change the value inside the class
        # and see the change reflected by the passed out reference
        self.status = {'has_next_song': False}
        self.current_song = None
        self.next_song = None

        self.medley_starting_time = dt.now()
        self.song_dict = {}
        self.dump_info = _dump_info
        self.song_queue = async_song_queue
        
    async def __aenter__(self):
        self.status['has_next_song'] = True
        return self.status, self.generator

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        if exc_type:
            print(exc_type, exc_value, exc_traceback)

    def choose_next_song(self):
        while not self.song_queue.empty():
            song = self.song_queue.get_nowait()
            self.song_dict[song.uri] = song
            self.song_queue.task_done()
            
        for song in self.song_dict.values():
            if (not song.last_played) or (song.last_played < self.medley_starting_time):
                #self.dump_info().log(f'Choosing {song.name} as next song.')
                self.next_song = song 
                break
                
        if not self.next_song:
            self.dump_info().log(f'No songs left.')
            self.status['has_next_song'] = False

    def generator(self):
        self.choose_next_song()
        
        while(self.status['has_next_song']):# do something if song is not chosen yet
            if not self.next_song:
                pass

            self.current_song = self.next_song
            self.next_song = None
            
            self.dump_info().log(f'Returning {self.current_song.name}')
            yield self.current_song.uri, self.current_song.snippet_start_in_ms
            
            from datetime import datetime as dt 
            self.current_song.last_played = dt.now()
            self.choose_next_song()
                
class Song():
    
    def __init__(self,
                uri_as_key,
                sp_track_name,
                sp_track_artists,
                sp_track_duration,
                sp_track_popularity,
                yt_vid_id,
                yt_vid_name,
                popularity_graph,
                snippet_start_in_ms):
        
        self.uri = uri_as_key
        self.name = sp_track_name
        self.artists = sp_track_artists
        self.duration = sp_track_duration
        self.popularity = sp_track_popularity
        self.yt_id = yt_vid_id
        self.yt_name = yt_vid_name
        self.graph = popularity_graph
        self.snippet_start_in_ms = snippet_start_in_ms
        self.last_played = None
        

        