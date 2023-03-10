# PixivCrawler
Crawler for Pixiv.net, has auto-generated docs, fast API response, and highly configurable functionalities
# Setup Instruction
**This project was developed under Python 3.10.4, yet no other Python version was tested**

Make sure you have a relatively recent version of Chrome browser installed, you may use `wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo apt install ./google-chrome-stable_current_amd64.deb` to install it on Ubuntu/Debian running on x64 architecture, for other systems please refer to [Google's help center](https://support.google.com/chrome/a/topic/9025817)

Use `pip install -r requirements.txt` to install all required libraries

Use `python run.py` to run the script, when script is showing `running on http://0.0.0.0:8000` in the console, you can access the API server at `http://localhost:8000` (replace `localhost` with your server's IP address if you are running the script on a remote server, also replace `8000` with the port you specified in config.ini)

# Documents
You could find the API documents and try all the functionalities out at `http://localhost:8000/docs` (replace `localhost` with your server's IP address if you are running the script on a remote server, also replace `8000` with the port you specified in config.ini)

# Note
This crawler needs a valid Pixiv account to work, please enter your username and password in command prompt when running for the first time

When captcha resolving is needed, if using a CLI system, please use `python pixiv_auth_selenium.py login` in a system with GUI and record and paste `referesh_token` in config.ini under [Auth] section as `refresh_token=YourRefreshToken`, and run the crawler again
