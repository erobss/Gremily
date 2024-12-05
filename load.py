import base64
import sqlite3
import json
import os
from dotenv import load_dotenv
from requests import get

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
    
    result = get(url, headers=headers, data=data)
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
    search_result = get(search_url, headers=headers).json()
    
    if search_result['tracks']['items']:
        song = search_result['tracks']['items'][0]
        track_id = song['id']
        
        # Fetch audio features for the track
        features_url = f"https://api.spotify.com/v1/audio-features/{track_id}"
        features = get(features_url, headers=headers).json()

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
        print(f"Spotify search failed for: {song_name} by {artist_name}")
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
    if not songs:
        print("Error: Unable to scrape Billboard Hot 100 data. Verify the HTML structure.")
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
            cursor.execute("""
                INSERT OR IGNORE INTO BillboardSongs (song_name, artist_name) 
                VALUES (?, ?)
            """, (song_name.lower(), artist_name.lower()))
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
            WHERE LOWER(song_name) = ? AND LOWER(artist_name) = ?
        """, (song['danceability'], song['tempo'], song['energy'], song['song_name'].strip().lower(), song['artist_name'].strip.lower()))
    conn.commit()

# STEP 3 CALCULATIONS 

# Calculate average tempo and danceability
def calculate_averages():
    cursor.execute("""
        SELECT AVG(sf.tempo) AS avg_tempo, AVG(sf.danceability) AS avg_danceability
        FROM SpotifyFeatures AS sf
    """)
    result = cursor.fetchone()
    with open("calculated_data.txt", "w") as file:
        file.write(f"Average Tempo: {result[0]:.2f}\n")
        file.write(f"Average Danceability: {result[1]:.2f}\n")
        print("Calculations saved to calculated_data.txt")

import matplotlib.pyplot as plt

# Visualization: Scatter plot for tempo vs danceability
def plot_tempo_vs_danceability():
    cursor.execute("""
        SELECT tempo, danceability
        FROM SpotifyFeatures
    """)
    data = cursor.fetchall()
    tempos = [row[0] for row in data]
    danceabilities = [row[1] for row in data]
    
    plt.scatter(tempos, danceabilities, color='blue', alpha=0.5)
    plt.xlabel("Tempo")
    plt.ylabel("Danceability")
    plt.title("Danceability vs Tempo")
    plt.show()

# Visualization: Bar chart of top 10 artists by number of songs
def plot_top_artists():
    cursor.execute("""
        SELECT artist_name, COUNT(*) AS song_count
        FROM BillboardSongs
        GROUP BY artist_name
        ORDER BY song_count DESC
        LIMIT 10
    """)
    data = cursor.fetchall()
    artists = [row[0] for row in data]
    counts = [row[1] for row in data]

    plt.bar(artists, counts, color='orange')
    plt.xticks(rotation=45, ha='right')
    plt.xlabel("Artists")
    plt.ylabel("Number of Songs")
    plt.title("Top 10 Artists by Number of Songs")
    plt.show()


def main():
    # Gather Billboard data
    billboard_songs = scrape_billboard_hot_100()
    
    # Limit to the first 50 songs
    limited_songs = billboard_songs[:50]
    
    # Insert limited Billboard data
    insert_billboard_data(limited_songs)

    # Fetch Spotify features for limited songs
    spotify_features = []
    for song_name, artist_name in limited_songs:
        feature = get_spotify_features(song_name, artist_name)
        if feature:
            spotify_features.append(feature)
    insert_spotify_data(spotify_features)

    # Perform calculations and visualize
    calculate_averages()
    plot_tempo_vs_danceability()
    plot_top_artists()

if __name__ == "__main__":
    main()

