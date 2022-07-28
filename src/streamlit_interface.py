from streamlit import cache as st_cache
from streamlit import experimental_singleton as st_singleton

@st_singleton
def SpotifyHandler(*args, **kwargs):
    from src.SpotifyHandler import SpotifyHandler
    
    return SpotifyHandler(*args, **kwargs)

@st_singleton
def YoutubeHandler(*args, **kwargs):
    from src.YoutubeHandler import YoutubeHandler
    
    return YoutubeHandler(*args, **kwargs)    

@st_singleton
def MedleyGenerator(*args, **kwargs):
    from src.MedleyGenerator import MedleyGenerator
    
    return MedleyGenerator(*args, **kwargs)

@st_singleton
def AsyncHandler(*args, **kwargs):
    from src.AsyncHandler import AsyncHandler
    
    return AsyncHandler(*args, **kwargs)