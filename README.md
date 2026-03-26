# sonarr-radarr-queue-cleaner
This is a fork of PaeyMoopy's project (https://github.com/PaeyMoopy/sonarr-radarr-queue-cleaner), which is a fork of MattDGTL's project with some added functionality. Credit to the overall idea can go here: https://github.com/MattDGTL/sonarr-radarr-queue-cleaner

I have refactored PaeyMoopy's fork to clean it up a little, removed unused modules and added functionality to use qBittorrent's API to check for torrents stuck in the 'Downloading metadata' state.

A simple Sonarr and Radarr script to clean out stalled downloads.

A "strike" system to ensure the stalled downloads have been stalled for a while.

The number of strikes and the amount of time between checks can be changed in the config file.

To use with Docker:
  1. ```
     git clone https://github.com/xXDEF4LTXx/sonarr-radarr-queue-cleaner.git

     cd sonarr-radarr-queue-cleaner
     ```
2. Edit the config file and input your server information.
   API_TIMEOUT = how often to check for stalled downloads in seconds.
   STRIKE_COUNT = how many strikes before looking for a new download.
   QBITTORRENT_METADATA_TIMEOUT = how many seconds an item/release/download has been stuck in the status 'Downloading metadata' before it is removed and blocked.

   For example, if API_TIMEOUT = 600, and STRIKE_COUNT = 5, the system will check for stalled downloads every 10 minutes. If any item is stalled, it gets a strike. Once an item receives 5 strikes, it gets removed and searched.
   So in this example, any item that has been stalled for 1 hour will get removed and searched.
   ```
   nano config.json
   ```
4. Once you've saved the config:
   ```
   docker build -t media-cleaner .
   ```
5. Then start the container.
   ```
   docker run -d --name media-cleaner media-cleaner
   ```
   Or if you want it to start automatically on boot:
   ```
   docker run -d --name media-cleaner --restart unless-stopped media-cleaner
   ```


To use without Docker:  
  1. ```
     git clone https://github.com/xXDEF4LTXx/sonarr-radarr-queue-cleaner.git

     cd sonarr-radarr-queue-cleaner
     ```
2. Edit the config file and input your server information.
   API_TIMEOUT = how often to check for stalled downloads in seconds.
   STRIKE_COUNT = how many strikes before looking for a new download.
   QBITTORRENT_METADATA_TIMEOUT = how many seconds an item/release/download has been stuck in the status 'Downloading metadata' before it is removed and blocked.

   For example, if API_TIMEOUT = 600, and STRIKE_COUNT = 5, the system will check for stalled downloads every 10 minutes. If any item is stalled, it gets a strike. Once an item receives 5 strikes, it gets removed and searched.
   So in this example, any item that has been stalled for 1 hour will get removed and searched.
   ```
   nano config.json
   ```
3. ```
   pip install -r requirements.txt
   ```
4. ```
   python3 cleaner.py
   ```
