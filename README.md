# Searcharr
## Sonarr & Radarr Telegram Bot
### By Todd Roberts
https://github.com/toddrob99/searcharr

This bot allows users to add movies to Radarr and series to Sonarr via Telegram messaging app.

## Setup & Run

### Configure

Rename `settings-sample.py` to `settings.py`, and edit the settings within the file as necessary.

You are required to update the following settings, at minimum:

* Searcharr Bot > Password
* Telegram Bot > Token
* Sonarr > URL, API Key, Quality Profile ID
* Radarr > URL, API Key, Quality Profile ID

### Docker & Docker-Compose

Docker is the suggested method to run Searcharr. Be sure to map the following in your Docker container:

* Settings file to /app/settings.py
* Database folder to /app/data
* Log folder to /app/logs

A docker-compose.yml file is provided for your convenience. Update the volume mappings listed above, and then run `docker-compose up -d` to start Searcharr.

### Run from Source

If running from source, use Python 3.8.3+, install requirements using `python -m pip install -r requirements.txt`, and then run `searcharr.py`.

## Use

### Authenticate

Send a private message to your bot saying `/start <password>`.

**Caution**: This command will work in a group chat, but then everyone else in the group will see the password. If not all group members should be allowed to use the bot, then be sure to authenticate in a private message.

### Search & Add a Series to Sonarr

Send the bot a (private or group) message saying `/series <title>`. The bot will reply with information about the first result, along with buttons to move forward and back within the search results, pop out to tvdb or IMDb, add the current series to Sonarr, or cancel the search. When you click the button to add the series to Sonarr, the bot will ask what root folder to put the series in--unless you only have one root folder configured in Sonarr, in which case it will add it straight away.

### Search & Add a Movie to Radarr

Send the bot a (private or group) message saying `/movie <title>`. The bot will reply with information about the first result, along with buttons to move forward and back within the search results, pop out to IMDb, add the current movie to Radarr, or cancel the search. When you click the button to add the movie to Radarr, the bot will ask what root folder to put the movie in--unless you only have one root folder configured in Radarr, in which case it will add it straight away.
