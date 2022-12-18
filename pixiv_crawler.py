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


config = configparser.ConfigParser(inline_comment_prefixes="#")
download_folder = ""
ranking_mode = ""
get_all_ranking_pages = True
allow_multiple_pages = False
get_all_multiple_pages = False


def read_config():
    global config, download_folder, ranking_mode, get_all_ranking_pages, allow_multiple_pages, get_all_multiple_pages
    # read config file
    config.read('config.ini')
    if not config.has_section("Crawler"):
        config.add_section("Crawler")
    # get download folder
    if config.has_option("Crawler", "download_folder") and config["Crawler"]["download_folder"] != "":
        download_folder = config["Crawler"]["download_folder"]
    else:
        download_folder = "downloads"
        print("download_folder invalid, using default: " + download_folder)
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
    # mode: [day, week, month, day_male, day_female, week_original, week_rookie, day_r18, day_male_r18, day_female_r18, week_r18, week_r18g]
    if ranking_mode == "" or ranking_mode not in ["day", "week", "month", "day_male", "day_female", "week_original", "week_rookie", "day_r18", "day_male_r18", "day_female_r18", "week_r18", "week_r18g"]:
        ranking_mode = "day_male"
        print("ranking_mode invalid, using default: " + ranking_mode)
    config["Crawler"]["ranking_mode"] = ranking_mode + \
        " # day, week, month, day_male, day_female, week_original, week_rookie, day_r18, day_male_r18, day_female_r18, week_r18, week_r18g"
    # get get_all_ranking_pages flag (default: True)
    if config.has_option("Crawler", "get_all_ranking_pages"):
        get_all_ranking_pages = bool(
            config["Crawler"]["get_all_ranking_pages"].capitalize() == "True")
    else:
        get_all_ranking_pages = True
        print("get_all_ranking_pages invalid, using default: " +
              str(get_all_ranking_pages))
    config["Crawler"]["get_all_ranking_pages"] = str(get_all_ranking_pages)
    # get allow_multiple_pages flag (default: False)
    if config.has_option("Crawler", "allow_multiple_pages"):
        allow_multiple_pages = bool(
            config["Crawler"]["allow_multiple_pages"].capitalize() == "True")
    else:
        allow_multiple_pages = False
        print("allow_multiple_pages invalid, using default: " +
              str(allow_multiple_pages))
    config["Crawler"]["allow_multiple_pages"] = str(allow_multiple_pages)
    # get get_all_multiple_pages flag (default: False, only get the first page)
    if config.has_option("Crawler", "get_all_multiple_pages"):
        get_all_multiple_pages = bool(
            config["Crawler"]["get_all_multiple_pages"].capitalize() == "True")
    else:
        get_all_multiple_pages = False
        print("get_all_multiple_pages invalid, using default: " +
              str(get_all_multiple_pages))
    config["Crawler"]["get_all_multiple_pages"] = str(get_all_multiple_pages)

    # save config file
    with open('config.ini', 'w') as configfile:
        config.write(configfile)


read_config()
api = AppPixivAPI()
refreshtoken = get_refresh_token()
api.auth(refresh_token=refreshtoken)

# json_result = api.illust_detail(103676655)
# illust = json_result.illust
# for images in illust.meta_pages:
#     print(images.image_urls.original)
# print(illust.meta_pages)
# exit()

# get images:
next_qs = {"mode": ranking_mode}
while next_qs:
    json_result = api.illust_ranking(**next_qs)
    for illust in json_result.illusts:
        if (illust.type == "manga"):
            continue
        if (not allow_multiple_pages and illust.page_count > 1):
            continue
        urls = []
        url = illust.meta_single_page.original_image_url
        if (url == None):
            for images in illust.meta_pages:
                url = images.image_urls.original
                urls.append(url)
                if (not get_all_multiple_pages):
                    break
        else:
            urls = [url]
        prefix = str(illust.id) + "_" + illust.user.name + "_"
        title = illust.title
        print("[%s] %s" % (illust.user.name, title))
        for i in range(len(urls)):
            api.download(urls[i], path=download_folder, prefix=slugify(prefix, True),
                         name=slugify(title + f"_p{str(i)}", True) + ".jpg")
    next_qs = api.parse_qs(json_result.next_url)
    if (not get_all_ranking_pages):
        break
