import os
import re
import unicodedata
import configparser

from pixivpy3 import *
from pixiv_auth_selenium import get_refresh_token


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode(
            'ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


# read config file for download folder and ranking mode
config = configparser.ConfigParser()
config.read('config.ini')
if not config.has_section("Crawler"):
    config.add_section("Crawler")
# get download folder
if config.has_option("Crawler", "download_folder") and config["Crawler"]["download_folder"] != "":
    download_folder = config["Crawler"]["download_folder"]
else:
    download_folder = "downloads"
    print("download folder invalid, using default: " + download_folder)
config["Crawler"]["download_folder"] = download_folder
# check if download folder exists
if not os.path.exists(download_folder):
    os.makedirs(download_folder)
# get ranking mode
if config.has_option("Crawler", "ranking_mode"):
    ranking_mode = config["Crawler"]["ranking_mode"]
else:
    ranking_mode = ""
# check if ranking mode is valid
if ranking_mode == "" or ranking_mode not in ["day", "week", "month", "day_male", "day_female", "week_original", "week_rookie", "day_manga"]:
    ranking_mode = "day"
    print("ranking mode invalid, using default: " + ranking_mode)
config["Crawler"]["ranking_mode"] = ranking_mode
# get get_all_pages flag (default: False)
if config.has_option("Crawler", "get_all_pages"):
    get_all_pages = bool(
        config["Crawler"]["get_all_pages"].capitalize() == "True")
else:
    get_all_pages = False
    print("get_all_pages not set, using default: " + str(get_all_pages))
config["Crawler"]["get_all_pages"] = str(get_all_pages)
# save config file
with open('config.ini', 'w') as configfile:
    config.write(configfile)


api = AppPixivAPI()
refreshtoken = get_refresh_token()
api.auth(refresh_token=refreshtoken)

# json_result = api.illust_detail(103633322)
# illust = json_result.illust
# print(illust)
# exit()

if (not get_all_pages):
    # get first page (1-30)
    # mode: [day, week, month, day_male, day_female, week_original, week_rookie, day_manga]
    json_result = api.illust_ranking(ranking_mode)
    # check if page folder exists
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
    for illust in json_result.illusts:
        if (illust.type == "manga"):
            continue
        prefix = str(illust.id) + "_" + illust.user.name + "_"
        title = illust.title
        url = illust.image_urls.large
        extension = "." + url.split(".")[-1]
        print("[%s] %s" %
              (title, url.replace("i.pximg.net", "i.pixiv.re")))
        api.download(url, path=download_folder, prefix=slugify(prefix, True),
                     name=slugify(title, True) + extension)
else:
    # get all pages:
    next_qs = {"mode": ranking_mode}
    while next_qs:
        json_result = api.illust_ranking(**next_qs)
        for illust in json_result.illusts:
            if (illust.type == "manga"):
                continue
            prefix = str(illust.id) + "_" + illust.user.name + "_"
            title = illust.title
            url = illust.image_urls.large
            extension = "." + url.split(".")[-1]
            print("[%s] %s" % (title, url.replace("i.pximg.net", "i.pixiv.re")))
            api.download(url, path=download_folder, prefix=slugify(prefix, True),
                         name=slugify(title, True) + extension)
        next_qs = api.parse_qs(json_result.next_url)
