import logging, json, requests, time

# Set up logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s]: %(message)s', 
    level=logging.INFO, 
    handlers=[logging.StreamHandler()]
)

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

SONARR_API_URL = config['SONARR_API_URL'] + "/api/v3"
SONARR_API_KEY = config['SONARR_API_KEY']
RADARR_API_URL = config['RADARR_API_URL'] + "/api/v3"
RADARR_API_KEY = config['RADARR_API_KEY']
API_TIMEOUT = config['API_TIMEOUT']
STRIKE_COUNT = config['STRIKE_COUNT']
QBITTORRENT_USERNAME = config['QBITTORRENT_USERNAME']
QBITTORRENT_PASSWORD = config['QBITTORRENT_PASSWORD']
QBITTORRENT_URL = config['QBITTORRENT_URL'] + "/api/v2"
QBITTORRENT_METADATA_TIMEOUT = config['QBITTORRENT_METADATA_TIMEOUT']

# Initialize the sonarr strike count dictionary
strike_counts_sonarr = {}

# Initialize the radarr strike count dictionary
strike_counts_radarr = {}

# Initialize the radarr_metadata_stuck dictionary
radarr_metadata_stuck = {}

# Initialize the sonarr_metadata_stuck dictionary
sonarr_metadata_stuck = {}

# Initialize the qBittorrent cookies variable
qbittorrent_cookies = None

# Function to make API requests
def make_api_request(url:str, api_key:str, params=None) -> dict | None:
    headers = {
        'X-Api-Key': api_key
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f'Error making API request to {url}: {e}')
        return None

# Function to make API delete requests
def make_api_delete(url:str, api_key:str, params=None) -> bool:
    headers = {
        'X-Api-Key': api_key
    }
    try:
        response = requests.delete(url, headers=headers, params=params)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logging.error(f'Error making API delete request to {url}: {e}')
        return False

# Function to count records
def count_records(api_url:str, api_key:str) -> int:
    the_url = f'{api_url}/queue'
    the_queue = make_api_request(the_url, api_key)
    if the_queue is not None and 'records' in the_queue:
        return the_queue['totalRecords']
    else:
        logging.warning(f'Could not count records for {api_url}. Defaulting to 0.')
        return 0

# Function to log in to qBittorrent and store cookies
def login_to_qbittorrent() -> bool:
    global qbittorrent_cookies
    try:
        response = requests.post(QBITTORRENT_URL + "/auth/login", data={'username': QBITTORRENT_USERNAME, 'password': QBITTORRENT_PASSWORD})
        response.raise_for_status()
        logging.info("Successfully logged in to qBittorrent.")
        qbittorrent_cookies = response.cookies
        return True
    except requests.RequestException as e:
        logging.error(f"Failed to log in to qBittorrent: {e}")
        qbittorrent_cookies = None
        return False

# Function to get qBittorrent version to ensure we are logged in and the API is responsive
def get_version() -> bool:
    try:
        response = requests.get(QBITTORRENT_URL + "/app/version", cookies=qbittorrent_cookies)
        response.raise_for_status()
        version = response.text.strip('"')
        logging.debug(f"qBittorrent version retrieved: {version}")
        return True
    except requests.RequestException as e:
        logging.error(f"Failed to retrieve qBittorrent version: {e}")
        return False

# Function to get the status of torrents in qBittorrent and check if they are downloading metadata for too long
def get_torrents_status() -> bool:
    sonarr_metadata_stuck.clear()
    radarr_metadata_stuck.clear()
    
    if not qbittorrent_cookies or not get_version():
        
        logging.warning("Not logged in to qBittorrent. Logging in now.")
        login_to_qbittorrent()

        if not qbittorrent_cookies:
            logging.error("Failed to log in to qBittorrent, cannot retrieve torrents.")
            return False
        
    try:
        response = requests.get(QBITTORRENT_URL + "/torrents/info", cookies=qbittorrent_cookies)
        response.raise_for_status()
        torrents = response.json()
        logging.info(f"Retrieved {len(torrents)} torrents from qBittorrent.")

        time_now = time.time()

        for torrent in torrents:
            if torrent['state'] == 'metaDL' and torrent['last_activity'] < time_now - QBITTORRENT_METADATA_TIMEOUT:
                logging.info(f"Torrent '{torrent['name']}' has been downloading metadata for too long (last activity {time.ctime(torrent['last_activity'])}).")

                category = torrent.get('category', '').lower()

                if 'sonarr' in category:
                    sonarr_metadata_stuck[torrent['hash'].upper()] = torrent['name']
                elif 'radarr' in category:
                    radarr_metadata_stuck[torrent['hash'].upper()] = torrent['name']
        return True
    except requests.RequestException as e:
        logging.error(f"Failed to retrieve torrents from qBittorrent: {e}")
        return False
    
# Function to remove stalled Sonarr downloads
def remove_stalled_sonarr_downloads() -> None:
    logging.info('Checking Sonarr queue...')
    sonarr_url = f'{SONARR_API_URL}/queue'
    page_size = count_records(SONARR_API_URL, SONARR_API_KEY)
    if page_size == 0:
        logging.info('No records found in Sonarr queue. Skipping processing.')
        return
    sonarr_queue = make_api_request(sonarr_url, SONARR_API_KEY, {'page': '1', 'pageSize': page_size})

    if sonarr_queue is None or 'records' not in sonarr_queue:
        logging.info('Sonarr queue is None or missing "records" key')
        return 

    active_ids = {item['id'] for item in sonarr_queue['records']}
    for stale_id in list(strike_counts_sonarr.keys()):
        if stale_id not in active_ids:
            del strike_counts_sonarr[stale_id]
    
    logging.info('Processing Sonarr queue...')
    for item in sonarr_queue['records']:
        if ('title' not in item) or ('status' not in item) or ('downloadId' not in item):
            logging.warning(f'Skipping item in Sonarr queue due to missing or invalid keys: {item}')
            continue
        download_id = item.get('downloadId')
        logging.info(f'Checking the status of {item["title"]}')
        if (item['status'] == 'warning' and item.get('errorMessage') == 'The download is stalled with no connections') or (item['status'] == 'queued' and download_id in sonarr_metadata_stuck):
            item_id = item['id']
            if item_id not in strike_counts_sonarr:
                strike_counts_sonarr[item_id] = 0
            strike_counts_sonarr[item_id] += 1
            logging.info(f'Item {item["title"]} has {strike_counts_sonarr[item_id]} strikes')
            if strike_counts_sonarr[item_id] >= STRIKE_COUNT or download_id in sonarr_metadata_stuck:
                logging.info(f'Removing stalled Sonarr download: {item["title"]}')
                make_api_delete(f'{SONARR_API_URL}/queue/{item_id}', SONARR_API_KEY, {'removeFromClient': 'true', 'blocklist': 'true'})
                del strike_counts_sonarr[item_id]
                if download_id in sonarr_metadata_stuck:
                    del sonarr_metadata_stuck[download_id]

# Function to remove stalled Radarr downloads
def remove_stalled_radarr_downloads() -> None:
    logging.info('Checking Radarr queue...')
    radarr_url = f'{RADARR_API_URL}/queue'
    page_size = count_records(RADARR_API_URL, RADARR_API_KEY)
    if page_size == 0:
        logging.info('No records found in Radarr queue. Skipping processing.')
        return
    radarr_queue = make_api_request(radarr_url, RADARR_API_KEY, {'page': '1', 'pageSize': page_size})

    if radarr_queue is None or 'records' not in radarr_queue:
        logging.info('Radarr queue is None or missing "records" key')
        return
    
    active_ids = {item['id'] for item in radarr_queue['records']}
    for stale_id in list(strike_counts_radarr.keys()):
        if stale_id not in active_ids:
            del strike_counts_radarr[stale_id]
        
    logging.info('Processing Radarr queue...')
    for item in radarr_queue['records']:
        if ('title' not in item) or ('status' not in item) or ('downloadId' not in item):
            logging.warning('Skipping item in Radarr queue due to missing or invalid keys')
            continue
        download_id = item.get('downloadId')
        logging.info(f'Checking the status of {item["title"]}')
        if (item['status'] == 'warning' and item.get('errorMessage') == 'The download is stalled with no connections') or (item['status'] == 'queued' and download_id in radarr_metadata_stuck):
            item_id = item['id']
            if item_id not in strike_counts_radarr:
                strike_counts_radarr[item_id] = 0
            strike_counts_radarr[item_id] += 1
            logging.info(f'Item {item["title"]} has {strike_counts_radarr[item_id]} strikes')
            if strike_counts_radarr[item_id] >= STRIKE_COUNT or download_id in radarr_metadata_stuck:
                logging.info(f'Removing stalled Radarr download: {item["title"]}')
                make_api_delete(f'{RADARR_API_URL}/queue/{item_id}', RADARR_API_KEY, {'removeFromClient': 'true', 'blocklist': 'true'})
                del strike_counts_radarr[item_id]
                if download_id in radarr_metadata_stuck:
                    del radarr_metadata_stuck[download_id]

# Main function
def main() -> None:
    while True:
        logging.info('Running media-tools script')

        get_torrents_status()
        remove_stalled_sonarr_downloads()
        remove_stalled_radarr_downloads()

        logging.info(f'Finished running media-tools script. Sleeping for {API_TIMEOUT / 60} minutes.')
        time.sleep(API_TIMEOUT)

if __name__ == '__main__':
    main()
