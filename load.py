import base64
import sqlite3
import json
import os
from dotenv import load_dotenv
from requests import post

# Load environment variables
load_dotenv()

# Get Spotify API credentials
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")


#PART 1 LOAD THE DATA 

def get_token():
    auth_string = client_id + ":" + client_secret
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": "Basic " + auth_base64,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}
    
    result = post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result["access_token"]
    return token

def get_spotify_features(song_name, artist_name):
    token = get_token()
    
    # Prepare headers for authorization
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Search for the song on Spotify
    search_url = f"https://api.spotify.com/v1/search?q={song_name} {artist_name}&type=track&limit=1"
    search_result = post(search_url, headers=headers).json()
    
    if search_result['tracks']['items']:
        song = search_result['tracks']['items'][0]
        track_id = song['id']
        
        # Fetch audio features for the track
        features_url = f"https://api.spotify.com/v1/audio-features/{track_id}"
        features = post(features_url, headers=headers).json()

        # Extract relevant features
        return {
            'song_name': song_name,
            'artist_name': artist_name,
            'energy': features['energy'],
            'danceability': features['danceability'],
            'valence': features['valence'],
            'acousticness': features['acousticness'],
            'tempo': features['tempo'],
            'loudness': features['loudness'],
            'key': features['key'],
            'mode': features['mode']
        }
    else:
        return None

import requests
from bs4 import BeautifulSoup

# URL to scrape Billboard Hot 100 chart
billboard_url = "https://www.billboard.com/charts/hot-100/#"

def scrape_billboard_hot_100():
    response = requests.get(billboard_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all <li> tags with the class 'o-chart-results-list__item'
    songs = []
    
    # Scrape each <li> and find the <h3> inside it for the song name and <span> for artist name
    for li_tag in soup.find_all('li', class_='o-chart-results-list__item'):
        # Find the <h3> inside each <li> tag for song title
        h3_tag = li_tag.find('h3', class_='c-title')
        # Find the <span> for artist name
        span_tag = li_tag.find('span', class_='c-label')
        
        if h3_tag and span_tag:
            song_title = h3_tag.get_text(strip=True)
            artist_name = span_tag.get_text(strip=True)
            
            # Add song title and artist name to the list as a tuple
            if song_title and artist_name:
                songs.append((song_title, artist_name))

    return songs

# PART 2 STORE THE DATA 

import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect("music_trends.db")
conn.execute("PRAGMA foreign_keys = ON")  # Ensure foreign keys are enforced
cursor = conn.cursor()

# Insert Billboard data
def insert_billboard_data(songs):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS BillboardSongs (
            song_id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_name TEXT NOT NULL COLLATE NOCASE,
            artist_name TEXT NOT NULL COLLATE NOCASE,
            UNIQUE(song_name, artist_name)
        )
    """)
    for song_name, artist_name in songs:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO BillboardSongs (song_name, artist_name) 
                VALUES (?, ?)
            """, (song_name.strip().lower(), artist_name.strip().lower()))
        except sqlite3.IntegrityError:
            print(f"Duplicate entry: {song_name} by {artist_name}")
    conn.commit()

# Insert Spotify features data
def insert_spotify_data(song_features):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SpotifyFeatures (
            feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            danceability REAL,
            tempo REAL,
            energy REAL,
            FOREIGN KEY(song_id) REFERENCES BillboardSongs(song_id) ON DELETE CASCADE
        )
    """)
    for song in song_features:
        cursor.execute("""
            INSERT INTO SpotifyFeatures (song_id, danceability, tempo, energy)
            SELECT song_id, ?, ?, ? 
            FROM BillboardSongs 
            WHERE song_name = ?
        """, (song['danceability'], song['tempo'], song['energy'], song['song_name'].strip().lower()))
    conn.commit()

