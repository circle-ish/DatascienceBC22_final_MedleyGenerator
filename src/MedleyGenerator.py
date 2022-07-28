class MedleyGenerator():
     
    def __init__(self, player_name, _dump_info = None):
        from src.streamlit_interface import AsyncHandler
            
        self.song_dict = {}
        self.dump_info = _dump_info
        if not self.dump_info:
            from src.utils import PrintLogger
            self.dump_info = PrintLogger.register()
            
        self.ash = AsyncHandler()
        self.ash.run(self.setup(device_name))
    
    async def setup(self, device_name):
        from src.streamlit_interface import SpotifyHandler, YoutubeHandler
        import os
        
        self.yt_handler = YoutubeHandler(_async_handler = self.ash)
        self.sp_handler = SpotifyHandler(_async_handler = self.ash, 
                                         env_file_path = os.path.join(os.getcwd(), '.env_spotify'), 
                                         playable=True)
        
        with self.dump_info('Setting up Connection to Youtube'):
            self.yt_handler.setup()
        self.device_id = self.sp_handler.get_device_id(device_name, wait=True)
        
    def get_token(self):
        return self.sp_handler.get_token()
    
    def search_playlist(self, query):
        return self.sp_handler.search_playlist(query)
    
    def sp_play(self):
        # lambda func as opposed to functools.partials use late bindings (keeping the reference
        # to the scope of device_id but fetching it not until execution) which makes it perfect
        # to avoid problems around changing device id
        play_func = lambda x: self.sp_handler.play(uri = x, device_id = self.device_id)
        return play_func
    
    def toggle_play(self):
        return_code = self.sp_handler.toggle_play(self.device_id)
        return return_code
        
    def create_medley(self, pl_uri, snippet_duration_in_sec):
        self.gather_songs(pl_uri, snippet_duration_in_sec)
                
        return MedleyContextManager(self, self.song_dict)
                   
    def gather_songs(self, pl_uri, snippet_duration_in_sec):
        # get tracks for chosen playlist
        with self.dump_info('Retrieving Songs from Spotify'):
            sp_track_uri, sp_track_names, sp_track_artists, sp_track_duration, sp_track_popularity = \
                self.sp_handler.get_playlist_tracks(pl_uri)

        # search tracks on yt
        with self.dump_info('Grab Popularity from Youtube'):
            for counter in range(len(sp_track_names)):
                yt_vid_id, yt_vid_name = self.yt_handler.search(sp_track_names[counter])

                # choose popular moments
                popularity_graph = self.yt_handler.get_most_replayed(yt_vid_id, sp_track_duration[counter])
                snippet_start_in_ms = self.sliding_window(popularity_graph, snippet_duration_in_sec)

                uri_as_key = sp_track_uri[counter]
                self.song_dict[uri_as_key] = Song(
                                            uri_as_key,
                                            sp_track_names[counter],
                                            sp_track_artists[counter],
                                            sp_track_duration[counter],
                                            sp_track_popularity[counter],
                                            yt_vid_id,
                                            yt_vid_name,
                                            popularity_graph,
                                            snippet_start_in_ms)
    
    def sliding_window(self, graph, window_size_in_sec):
        from pandas import DataFrame as pd_DataFrame
        from pandas import offsets as pd_offsets
        
        df_graph = pd_DataFrame(data = graph)
        df_graph.rename(columns = {'x': 'time', 'y': 'popularity'}, inplace=True)

        # weighting popularity based on assigned duration since timeseries is irregular
        df_graph['time_shift'] = df_graph[['time']].diff().set_index(df_graph.index - 1)
        df_graph.fillna(0, inplace=True)
        df_graph['scaled_popularity'] = df_graph['time_shift'] * df_graph['popularity']

        window_dt = pd_offsets.Second(window_size_in_sec)
        df_windowed_popularity = (
                df_graph 
                    .set_index(pd.to_datetime(df_graph['time'].array, unit='s'))['scaled_popularity']
                    .rolling(window=f'{window_size_in_sec}s')
                    .sum()
                 )
                    
        snippet_end = df_windowed_popularity.idxmax()
        snippet_start = snippet_end - window_dt
        
        return (snippet_start.minute*60 + snippet_start.second) * 1000 

class MedleyContextManager():

    def __init__(self, songs):    
        from datetime import datetime as dt 
        
        self.keep_playing = False
        self.current_song = None
        self.next_song = None

        self.medley_started = dt.now()
        self.choose_next_song()
        self.songs = songs

    def __enter__(self):
        self.keep_playing = True

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if not exc_type:
            print(exc_type, exc_value, exc_traceback)

    def choose_next_song(self):
        for song in self.songs.values():
            if (not song.last_played) or (song.last_played < self.medley_starting_time):
                self.next_song = song 
                break
                
        if not self.next_song:
            self.keep_playing = False

    def __iter__(self):
        # do something if song is not chosen yet
        if not self.next_song:
            pass

        self.current_song = self.next_song
        self.next_song = None

        yield self.current_song.uri, self.current_song.snippet_start_in_ms
        self.current_song.last_played = dt.now()
        choose_next_song()
                
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
        

        