class SpotifyHandler():
    
    def __init__(self, _async_handler, env_file_path, playable = False):
        self.sp = self.setup_spotify_connection(env_file_path, playable)
        self.token = None
        self.token_timestamp = None
        self.ash = _async_handler
        
    def setup_spotify_connection(self, env_file_path, playable):
        from src.utils import install_pip_pkg
        install_pip_pkg({'spotipy'})

        # import libraries
        import spotipy
        from src.utils import ConfigHandler

        #Initialize SpotiPy with user credentias
        config_handler = ConfigHandler(env_file_path)
        client_keys = config_handler.load_config('spotify')
        self.client_id = client_keys['client_id']
        self.redirect_url = client_keys['redirect_url']
        
        sp = None
        if playable:
            from spotipy.oauth2 import SpotifyOAuth
            
            # scope explanation 
            # https://developer.spotify.com/documentation/general/guides/authorization/scopes/
            # user-modify-playback-state -> start playing, seeking in a track, next track
            # user-read-playback-state -> get devices
            scope = 'streaming,user-library-read,user-modify-playback-state,user-read-playback-state,user-read-email,user-read-private'
                #,playlist-read-private,playlist-read-collaborative'
                
            self.client_credentials = SpotifyOAuth(
                            client_id=self.client_id,
                            client_secret=client_keys['client_secret'],
                            redirect_uri=self.redirect_url,
                            scope=scope,
                            #show_dialog = True,
                            open_browser = True)
            
            sp = spotipy.Spotify(auth_manager=self.client_credentials)
            
        else:
            from spotipy.oauth2 import SpotifyClientCredentials
            self.client_credentials = SpotifyClientCredentials(
                            client_id = self.client_id, 
                            client_secret = client_keys['client_secret'])
            sp = spotipy.Spotify(client_credentials_manager=self.client_credentials,
                             backoff_factor = 3, 
                             retries=3 )
        
        return sp
    
    def get_connection(self):
        return self.sp
    
    def get_token(self, *args, **kwargs):
        from datetime import datetime as dt 
        from datetime import timedelta
        
        if not self.token:
            response = self.client_credentials.get_access_token(*args, **kwargs)
            self.token = response['access_token']
            self.token_expires = dt.now() + timedelta(seconds = response['expires_in'])
            self.refresh_token = response['refresh_token']
        
        if self.token_expires <= dt.now():
            response = self.client_credentials.refresh_access_token(self.refresh_token)
            self.token = response['access_token']
            self.token_expires = dt.fromtimestamp(response['expires_at'])
            self.refresh_token = response['refresh_token']
            
        return self.token
    
    def get_device_id(self, for_name, wait = False):
        devices_dict = self.sp.devices()['devices']
        device_id = next((item['id'] for item in devices_dict if item['name'] == for_name), None)
        if wait and (not device_id):
            from time import sleep
            
            while (wait and (not device_id)):
                sleep(1)
                devices_dict = self.sp.devices()['devices']
                device_id = next((item['id'] for item in devices_dict if item['name'] == for_name), None)
        
        return device_id
    
    from enum import Enum
    class PlaybackStatus(Enum):
        PLAYING = 0
        PAUSED = 1
        STOPPED = 2
        DIFFERENT_DEVICE = 3
        OTHER = -1
            
    def is_playing(self, device_id):
        status = self.sp.current_playback()
        if status['device']['id'] != device_id :
            return self.PlaybackStatus.DIFFERENT_DEVICE
        elif status['is_playing']:
            return self.PlaybackStatus.PLAYING
        elif not status['device']['is_active']:
            return self.PlaybackStatus.STOPPED
        else:
            return self.PlaybackStatus.PAUSED
    
    def play(self, *args, **kwargs):
        self.sp.start_playback(*args, **kwargs)
            
    def toggle_play(self, device_id):
        res = self.is_playing(device_id)
        if (res == self.PlaybackStatus.PLAYING) or (res == self.PlaybackStatus.PAUSED):
            if res == self.PlaybackStatus.PLAYING:
                self.sp.pause_playback(device_id = device_id)
                return self.PlaybackStatus.PAUSED
            elif res == self.PlaybackStatus.PAUSED:
                self.sp.start_playback(device_id = device_id)
                return self.PlaybackStatus.PLAYING
            elif res == self.PlaybackStatus.STOPPED:
                return self.PlaybackStatus.STOPPED
        return self.PlaybackStatus.OTHER
        
    def search_playlist(self, query, **kwargs):
        kwargs.update({'q' : query, 'limit' : 10, 'type' : 'playlist'})
        res = self.retrieve('search', **kwargs)

        pl_uri = []
        pl_names = []
        pl_image_url = []
        pl_track_total = []
        res = res['playlists']['items']
        for pl_number in range(min(kwargs['limit'], len(res))):
            pl_uri.append(res[pl_number]['uri'])
            pl_names.append(res[pl_number]['name'])
            pl_track_total.append(res[pl_number]['tracks']['total'])
            pl_image_url.append(res[pl_number]['images'][-1]['url'])
        
        return pl_uri, pl_names, pl_image_url, pl_track_total      
    
    def get_playlist_tracks(self, pl_uri):
        res = self.retrieve('playlist', pl_uri)
        track_uri = []
        track_names = []
        track_popularity = []
        track_artists = []
        track_duration = []
        for track_number in range(len(res)):
            track = res['tracks']['items'][track_number]['track']
            track_uri.append(track['uri'])
            track_names.append(track['name'])
            track_popularity.append(track['popularity'])
            track_duration.append(track['duration_ms'])

            artist_len = len(track['artists'])
            artists = []
            for artist_number in range(artist_len):
                artists.append(track['artists'][artist_number]['name'])
            track_artists.append(', '.join(artists))
        # possibly track->album->{id (to get genre), name, release_date, images}
        
        return track_uri, track_names, track_artists, track_duration, track_popularity
        
    def retrieve_tracks(self, cluster_song_id_list):   
        # regarding ids : a list of spotify URIs, URLs or IDs. Maximum: 50 IDs.
        # install flatdict
        from src.utils import install_pip_pkg
        install_pip_pkg({'flatdict'})
        
        from flatdict import FlatterDict as flatten
        from pandas import json_normalize as pd_json_normalize
        song_list = self.retrieve_bits_for_tracks(cluster_song_id_list, 'tracks', market=None)
        df_songs = pd_json_normalize([dict(flatten(i)) for i in song_list[0]['tracks']])
        return df_songs
    
    def retrieve_artists_from_songs(self, cluster_song_id_list, return_all = 'no'):  
        # regarding ids : a list of spotify URIs, URLs or IDs. Maximum: 50 IDs.
        df_songs = self.retrieve_tracks(cluster_song_id_list)
        srs_artist_ids = df_songs['album:artists:0:id']
        
        response = self.retrieve(self.sp.artists, srs_artist_ids)            
        df_artists = pd.json_normalize(response['artists'])
        
        if return_all == 'no':
            return df_artists
        else:
            return df_songs, df_artists
    
    def retrieve_genre_from_songs(self, cluster_song_id_list, return_all = 'no'):
        df_songs, df_artists = self.retrieve_artists_from_songs(cluster_song_id_list, return_all = 'yes')
        df_songs['artist_genres'] = df_artists['genres']
        
        if return_all == 'no':
            return df_songs
        else:
            return df_songs, df_artists
        
    def retrieve_bits_for_tracks(self, cluster_song_id_list, func, **kwargs):    
        from spotipy.client import SpotifyException
        # retrieving tracks
        # regarding ids : a list of spotify URIs, URLs or IDs. Maximum: 50 IDs.
        song_list = []
        id_list_len = len(cluster_song_id_list)
        step = 50
        step_list =list(range(0, id_list_len, step)) 
        remainder = id_list_len % step
        if remainder != 0:
            step_list += [remainder]
            
        for lower in step_list:
            upper = min(id_list_len - lower, 50)
            response = self.retrieve(func, cluster_song_id_list[lower:lower+upper], **kwargs) 
            song_list.append(response)
        return song_list
    
    def retrieve(self, func, *args, **kwargs):
        from spotipy.client import SpotifyException
        
        if isinstance(func, str):
            func = eval('self.sp.' + func)
            
        response = None
        try:
            response = func(*args, **kwargs)
        except SpotifyException as error: # just to show how to handle it in times of need
                raise SpotifyException(
                    error.http_status, 
                    error.code,
                    error.msg,
                    reason = error.reason,         
                    headers = error.headers)
        return response
           