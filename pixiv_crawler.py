import hashlib
import time
import logging
import os
import re
import unicodedata
import configupdater

from tinydb import TinyDB
from tinydb.table import Document
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


def int_hash(obj):
    return int(hashlib.md5(obj.encode("utf-8")).hexdigest(), 16)


def insertDB(db, pk, data):
    try:
        if db.insert(Document(data, doc_id=int_hash(pk))):
            return True
        else:
            return False
    except Exception as e:
        # logger.debug(e)
        return False


def read_config():
    global api, config, db_path, store_mode, download_folder, ranking_mode, get_all_ranking_pages, allow_multiple_pages, get_all_multiple_pages, update_interval, crawler_status
    crawler_status = "reloading config"
    # read config file
    config = configupdater.ConfigUpdater()
    config.read('config.ini')
    if not os.path.exists('config.ini'):
        # Create config file
        with open('config.ini', 'w'):
            pass
    if not config.has_section("Crawler"):
        config.add_section("Crawler")
    # get db_path to determine where to store the database (default: db.json)
    if config.has_option("Crawler", "db_path") and config["Crawler"]["db_path"].value != "":
        db_path = config["Crawler"]["db_path"].value
    else:
        db_path = "db.json"
        logger.warning("db_path invalid, using default: " + db_path)
    config.set("Crawler", "db_path", db_path)
    # get store_mode to determine whether to store images as links or download them (default: light)
    comment = ""
    if config.has_option("Crawler", "store_mode") and (config["Crawler"]["store_mode"].value in ["light", "full"]):
        store_mode = config["Crawler"]["store_mode"].value
    else:
        if not config.has_option("Crawler", "store_mode"):
            comment = (
                "light(store image urls only), full(store images locally)")
        store_mode = "light"
        logger.warning("store_mode invalid, using default: " + store_mode)
    config.set("Crawler", "store_mode", store_mode)
    if comment != "":
        config["Crawler"]["store_mode"].add_before.comment(comment)
    # get download folder
    if config.has_option("Crawler", "download_folder") and config["Crawler"]["download_folder"].value != "":
        download_folder = config["Crawler"]["download_folder"].value
    else:
        download_folder = "downloads"
        logger.warning(
            "download_folder invalid, using default: " + download_folder)
    config.set("Crawler", "download_folder", download_folder)
    # check if download folder exists
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
    # get ranking mode
    comment = ""
    if config.has_option("Crawler", "ranking_mode") and (config["Crawler"]["ranking_mode"].value in ["day", "week", "month", "day_male", "day_female", "week_original", "week_rookie", "day_r18", "day_male_r18", "day_female_r18", "week_r18", "week_r18g"]):
        ranking_mode = config["Crawler"]["ranking_mode"].value
    else:
        if (not config.has_option("Crawler", "ranking_mode")):
            comment = (
                "day, week, month, day_male, day_female, week_original, week_rookie, day_r18, day_male_r18, day_female_r18, week_r18, week_r18g")
        ranking_mode = "day_male"
        logger.warning("ranking_mode invalid, using default: " + ranking_mode)
    config.set("Crawler", "ranking_mode", ranking_mode)
    if comment != "":
        config["Crawler"]["ranking_mode"].add_before.comment(comment)
    # get get_all_ranking_pages flag (default: False)
    if config.has_option("Crawler", "get_all_ranking_pages"):
        get_all_ranking_pages = bool(
            config["Crawler"]["get_all_ranking_pages"].value.capitalize() == "True")
        comment = ""
    else:
        comment = (
            "True(get all ranking images), False(get only 1-30 images in ranking)")
        get_all_ranking_pages = False
        logger.warning("get_all_ranking_pages invalid, using default: " +
                       str(get_all_ranking_pages))
    config.set("Crawler", "get_all_ranking_pages", str(get_all_ranking_pages))
    if comment != "":
        config["Crawler"]["get_all_ranking_pages"].add_before.comment(comment)
    # get allow_multiple_pages flag (default: False)
    if config.has_option("Crawler", "allow_multiple_pages"):
        allow_multiple_pages = bool(
            config["Crawler"]["allow_multiple_pages"].value.capitalize() == "True")
    else:
        allow_multiple_pages = False
        logger.warning("allow_multiple_pages invalid, using default: " +
                       str(allow_multiple_pages))
    config.set("Crawler", "allow_multiple_pages", allow_multiple_pages)
    # get get_all_multiple_pages flag (default: False, only get the first page)
    if config.has_option("Crawler", "get_all_multiple_pages"):
        get_all_multiple_pages = bool(
            config["Crawler"]["get_all_multiple_pages"].value.capitalize() == "True")
    else:
        get_all_multiple_pages = False
        logger.warning("get_all_multiple_pages invalid, using default: " +
                       str(get_all_multiple_pages))
    config.set("Crawler", "get_all_multiple_pages", get_all_multiple_pages)
    # get update_interval
    comment = ""
    if config.has_option("Crawler", "update_interval") and int(config["Crawler"]["update_interval"].value) > 0:
        update_interval = int(config["Crawler"]["update_interval"].value)
    else:
        if (not config.has_option("Crawler", "update_interval")):
            comment = (
                "seconds between each crawl")
        update_interval = 86400
        logger.warning(
            "update_interval invalid, using default: " + str(update_interval))
    config.set("Crawler", "update_interval", str(update_interval))
    if comment != "":
        config["Crawler"]["update_interval"].add_before.comment(comment)
    # save config file
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

    logger.info("Crawler config loaded")
    refreshtoken = get_refresh_token()
    api.auth(refresh_token=refreshtoken)
    logger.info("Pixiv logged in as " + api.user_detail(api.user_id).user.name)
    crawler_status = "idle"


# init api
api = AppPixivAPI()

# init logger
logger = logging.getLogger("uvicorn")

# crawler status
crawler_status = "idle"

# read config
read_config()
last_update_timestamp = -1

# init database
db = TinyDB(db_path, indent=4, separators=(',', ': '))
# db = TinyDB(db_path)

# json_result = api.illust_detail(103727904)
# illust = json_result.illust
# print(illust)
# exit()


def crawl_images():
    global last_update_timestamp, update_interval, crawler_status
    if (time.time() - last_update_timestamp < update_interval):
        logger.info("Crawl interval of " + str(update_interval) +
                    " seconds not reached, skip crawl")
        return
    if (crawler_status != "idle"):
        logger.info("Crawler is " + crawler_status + ", skip crawl")
        return
    crawler_status = "crawling"
    logger.info("Crawling images with config: store_mode=" + store_mode + ", ranking_mode=" + ranking_mode + ", get_all_ranking_pages=" + str(get_all_ranking_pages) +
                ", allow_multiple_pages=" + str(allow_multiple_pages) + ", get_all_multiple_pages=" + str(get_all_multiple_pages))
    image_count = 0
    db_count = 0
    download_count = 0
    # crawl images:
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
            for i in range(len(urls)):
                url = urls[i]
                pk = str(illust.id) + "_" + str(i)
                local_filename = ""
                if (store_mode == "full"):
                    extension = os.path.splitext(url)[1]
                    local_filename = slugify(
                        f"{str(illust.id)}_{illust.user.name}_{illust.title}_p{str(i)}", True) + extension
                    if(api.download(url, path=download_folder, name=local_filename)):
                        download_count += 1
                    local_filename = download_folder + os.sep + local_filename
                data = {"id": illust.id, "author_id": illust.user.id, "author_name": illust.user.name, "title": illust.title, "page_no": i,
                        "page_count": illust.page_count, "r18": illust.x_restrict, "ai_type": illust.illust_ai_type, "tags": illust.tags, "url": url, "local_filename": local_filename}
                # insert into database
                image_count += 1
                if (insertDB(db, pk, data)):
                    db_count += 1
        next_qs = api.parse_qs(json_result.next_url)
        if (not get_all_ranking_pages):
            break
    logger.info(
        f"Crawled {image_count} images, {db_count} images added to database, {download_count} images downloaded")
    last_update_timestamp = time.time()
    crawler_status = "idle"
