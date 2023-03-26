# PixivCrawler
Crawler for Pixiv.net, has auto-generated docs, fast API response, and highly configurable functionalities
# Setup Instructions
**This project was developed under Python 3.10.4, yet no other Python version was tested**

Make sure you have a relatively recent version of Chrome browser installed, you may use `wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo apt install ./google-chrome-stable_current_amd64.deb` to install it on Ubuntu/Debian running on x64 architecture, for other systems please refer to [Google's help center](https://support.google.com/chrome/answer/95346?hl=en&co=GENIE.Platform%3DDesktop)

Use `pip install -r requirements.txt` to install all required libraries

Use `python run.py` to run the script and follow the instructions given in the console to log in with your Pixiv account, when script is showing `running on http://0.0.0.0:8000` in the console, you can access the API server at `http://localhost:8000` (replace `localhost` with your server's IP address if you are running the script on a remote server, also replace `8000` with the port you specified in config.ini)

If you are using this crawler for the first time, you might need to crawl images using `http://localhost:8000/crawl` (replace `localhost` with your server's IP address if you are running the script on a remote server, also replace `8000` with the port you specified in config.ini) first before you can use the API to search for images, please follow the instructions given in the loggings to crawl images

# Documents
You could find the API documents and try all the functionalities out at `http://localhost:8000/docs` (replace `localhost` with your server's IP address if you are running the script on a remote server, also replace `8000` with the port you specified in config.ini)

# Notes
If you encounter any network related errors, please try to set `http_proxy` in config.ini under [Auth] section to your proxy server's address (e.g. `http_proxy=http://127.0.0.1:7890`)

When captcha resolving is needed, if using a CLI system, please use `python pixiv_auth_selenium.py login` in a system with GUI and record and paste `referesh_token` in config.ini under [Auth] section as `refresh_token=YourRefreshToken`, and run the crawler again

If you wanted to crawl R18/R18-G images, please ensure your Pixiv account preference is allowing you to view R18/R18-G images

If you need to migrate your db.json (TinyDB) to latest db.sqlite3 (SQLite3, which is having much better performance), please use `python migrate.py` and follow the instructions in the console to migrate your db.json to db.sqlite3 (replace `db.json` with your db file name if you are using a different name), and you may also need to change the `db_path` in config.ini to `db_path=db.sqlite3` after migration is finished