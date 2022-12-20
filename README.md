# PixivCrawler
Crawler for Pixiv.net, has auto-generated docs, fast API response, and highly configurable functionalities
# Instruction
This project was developed under Python 3.10.4, yet no other Python version was tested

Use `pip install -r requirements.txt` to install all required libraries

Use `python run.py` to run the script

# Note
This crawler needs a valid Pixiv account to work, please enter your username and password in command prompt when running for the first time

When captcha resolving is needed, if using a CLI system, please use `python pixiv_auth_selenium.py login` in a system with GUI and record and paste `referesh_token` in config.ini under [Auth] section as `refresh_token=YourRefreshToken`, and run the crawler again
