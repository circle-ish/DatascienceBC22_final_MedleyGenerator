import streamlit as st
import streamlit.components.v1 as components

# ___________________ Load Player ___________________ 
# requires Spotify Premium
def embed_spotify():    
    st.session_state.token = st.session_state.mg_backend.get_token()
    
    # following https://developer.spotify.com/documentation/web-playback-sdk/quick-start/
    embed_spotify_string = f'''
        <script src="https://sdk.scdn.co/spotify-player.js" asynch></script>
        <script>
        console.log('-+-+ using token = {st.session_state.token}');
        window.onSpotifyWebPlaybackSDKReady = () => {{     
            // You can now initialize Spotify.Player and use the SDK
            player = new window.Spotify.Player({{
                name: '{SP_PLAYER_NAME}',
                getOAuthToken: cb => {{ cb('{st.session_state.token}'); }},
                volume: 0.5
            }});

            // Error handling
            player.on('initialization_error', e => console.error(e));
            player.on('authentication_error', e => console.error(e));
            player.on('account_error', e => console.error(e));
            player.on('playback_error', e => console.error(e));

            player.addListener('ready', ({{ device_id }}) => {{
                console.log('-+-+ deviceId set to', device_id);
            }});

            player.connect().then(connected => {{
                if (connected) {{
                    console.log('-+-+ Connected');
                }}
            }});             
        }};
        </script>
        '''
    
    return components.html(embed_spotify_string, height=0)    

def search_playlist(**kwargs):
    st.session_state.mg_pl_uri, \
        st.session_state.mg_pl_names, \
        _, \
        st.session_state.mg_pl_track_total = st.session_state.mg_backend.search_playlist(st.session_state.sp_pl_query)

    st.session_state.mg_pl_index = list(range(len(st.session_state.mg_pl_names)))

def toggle_play():
    return_code = mg_backend.toggle_play()
    
def play():
    play = st.session_state.mg_backend.sp_play()
    pl_uri = st.session_state.mg_pl_uri[st.session_state.sp_pl_selected]
    with st.session_state.mg_backend.create_medley(pl_uri, st.session_state.play_duration_in_sec) as mg:
        while(mg.keep_playing):
            st.session_state.play_uri, st.session_state.play_offset_in_ms = next(mg)
            play(st.session_state.play_uri, position_ms={'position': st.session_state.play_offset_in_ms})

def display_player():    
    st.button(label='TOGGLE PLAY', on_click=toggle_play, args=())

# following https://stackoverflow.com/a/28401296/19347187
from contextlib import contextmanager as contextlib_contextmanager 
@contextlib_contextmanager
def popup(text):
    with st.session_state.status.container() as c:
        with st.spinner(text) as s:
            try:
                yield [c]
                #yield [s]
            except Exception as exc:
                print(f'-+-+ FAILED: {text}')
            finally:
                pass
            print(f'-+-+ SUCCESSFUL: {text}')

def pass_popup():
    return lambda x: popup(text = x)

def main():
    st.title(SP_PLAYER_NAME)  
    
    st.session_state.status = st.empty()
        
    # ___________________ Load Player ___________________ 
    with popup('Connecting to Spotify'):
        embed_spotify()

    # ___________________ Choose Playlist ___________________         
    with st.expander(label='SEARCH', expanded=True):
        with st.container():
            st.text_input(
                label = 'Search for a playlist', 
                value = 'top 80s', 
                key = 'sp_pl_query',
                on_change = search_playlist)
            
            if 'sp_pl_names' not in st.session_state:
                search_playlist()   
                
            st.selectbox(
                label = 'Choose a playlist', 
                options = st.session_state.mg_pl_index, 
                key = 'sp_pl_selected',
                index = 0,
                format_func = lambda x: 
                f'"{st.session_state.mg_pl_names[x]}" with {st.session_state.mg_pl_track_total[x]} tracks')   
            
            play_btn = st.button(
                label='CREATE MEDLEY',
                on_click=play)
    
    # ___________________ Display Player ___________________              
    if play_btn:
        st.session_state.player_show = True
        
    if 'player_show' in st.session_state:
        with st.container():
            display_player()

    if play_btn:
        play()
        
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

            
if __name__ == "__main__":
    import os
    from src.streamlit_interface import MedleyGenerator
    
    # cached via interface
    SP_PLAYER_NAME = 'MEDLEY PLAYER'
    st.session_state.play_duration_in_sec = 15
    if 'mg_backend' not in st.session_state:
        st.session_state.mg_backend = MedleyGenerator(player_name = SP_PLAYER_NAME)#, _dump_info = pass_popup())
    
    local_css("src/style.css")
    main()
    