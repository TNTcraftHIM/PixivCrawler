import hashlib
import time
import logging
import traceback
import os
import re
import unicodedata
import configupdater

from PIL import Image, ImageFile
from tinydb import TinyDB, Query
from tinydb.table import Document
from pixivpy3 import *
from pixiv_auth_selenium import get_refresh_token, get_token_expiration

ImageFile.LOAD_TRUNCATED_IMAGES = True

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


def insertDB(pk, data, force_update=False):
    global db
    try:
        if force_update:
            if db.upsert(Document(data, doc_id=int_hash(pk))):
                return True
            else:
                return False
        if db.insert(Document(data, doc_id=int_hash(pk))):
            return True
        else:
            return False
    except Exception as e:
        # logger.error("Aborting database insertion due to error: " +
        #              str(e) + "\n" + traceback.format_exc())
        return False


def get_list(string: str):
    return [x.strip() for x in string.split(",")]


def read_config():
    global api, config, db_path, db_minify, store_mode, download_folder, download_quality, download_reverse_proxy, ranking_modes, get_all_ranking_pages, allow_multiple_pages, get_all_multiple_pages, update_interval, crawler_status, last_update_timestamp, excluding_tags, stop_compression_task
    crawler_status = "reloading config"
    # read config file
    config = configupdater.ConfigUpdater()
    config.read('config.ini')
    if not os.path.exists('config.ini'):
        # Create config file
        with open('config.ini', 'w'):
            pass
    if not config.has_section("Crawler"):
        config.append("\n")
        config.add_section("Crawler")
    # get db_path to determine where to store the database (default: db.json)
    if config.has_option("Crawler", "db_path") and config["Crawler"]["db_path"].value != "":
        db_path = config["Crawler"]["db_path"].value
    else:
        db_path = "db.json"
        logger.warning("db_path invalid, using default: " + db_path)
    config.set("Crawler", "db_path", db_path)
    # get db_minify to determine whether to minify the database (default: True)
    comment = ""
    if config.has_option("Crawler", "db_minify") and (config["Crawler"]["db_minify"].value in ["True", "False"]):
        db_minify = bool(config["Crawler"]["db_minify"].value == "True")
    else:
        if not config.has_option("Crawler", "db_minify"):
            comment = "True(reduce size of database file), False(beautify database so it's easier to read)"
        db_minify = True
        logger.warning("db_minify invalid, using default: " + str(db_minify))
    config.set("Crawler", "db_minify", str(db_minify))
    if comment != "":
        config["Crawler"]["db_minify"].add_before.comment(comment)
    # get store_mode to determine whether to store images as links or download them (default: light)
    comment = ""
    if config.has_option("Crawler", "store_mode") and (config["Crawler"]["store_mode"].value in ["light", "full"]):
        store_mode = config["Crawler"]["store_mode"].value
    else:
        if not config.has_option("Crawler", "store_mode"):
            comment = (
                "light(store image urls only, functions under /api/v1/img will not work), full(store images locally)")
        store_mode = "full"
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
    if not os.path.exists(download_folder) and store_mode == "full":
        os.makedirs(download_folder)
    # get download quality
    comment = ""
    if config.has_option("Crawler", "download_quality") and (config["Crawler"]["download_quality"].value in ["original", "large", "medium"]):
        download_quality = config["Crawler"]["download_quality"].value
    else:
        if not config.has_option("Crawler", "download_quality"):
            comment = (
                "available qualities: original(space-consuming), large(balanced), medium(low resolution)")
        download_quality = "original"
        logger.warning(
            "download_quality invalid, using default: " + download_quality)
    config.set("Crawler", "download_quality", download_quality)
    if comment != "":
        config["Crawler"]["download_quality"].add_before.comment(comment)
    # get download reverse proxy (default: i.pixiv.re)
    comment = ""
    if config.has_option("Crawler", "download_reverse_proxy"):
        download_reverse_proxy = config["Crawler"]["download_reverse_proxy"].value
    else:
        if not config.has_option("Crawler", "download_reverse_proxy"):
            comment = (
                "reverse proxy for downloading images (could be empty), use i.pixiv.re if you cannot access pixiv directly")
        download_reverse_proxy = "i.pixiv.re"
        logger.warning(
            "download_reverse_proxy invalid, using default: " + download_reverse_proxy)
    config.set("Crawler", "download_reverse_proxy", download_reverse_proxy)
    if comment != "":
        config["Crawler"]["download_reverse_proxy"].add_before.comment(comment)
    # get ranking mode
    comment = ""
    if config.has_option("Crawler", "ranking_modes") and all(item in ["day", "week", "month", "day_male", "day_female", "week_original", "week_rookie", "day_r18", "day_male_r18", "day_female_r18", "week_r18", "week_r18g"] for item in get_list(config["Crawler"]["ranking_modes"].value)):
        ranking_modes = config["Crawler"]["ranking_modes"].value
    else:
        if (not config.has_option("Crawler", "ranking_modes")):
            comment = (
                "available modes (comma separated): day, week, month, day_male, day_female, week_original, week_rookie, day_r18, day_male_r18, day_female_r18, week_r18, week_r18g")
        ranking_modes = "day, day_r18, week, week_r18"
        logger.warning(
            "ranking_modes invalid, using default: " + str(ranking_modes))
    config.set("Crawler", "ranking_modes", ranking_modes)
    if comment != "":
        config["Crawler"]["ranking_modes"].add_before.comment(comment)
    # get excluding_tags
    comment = ""
    if config.has_option("Crawler", "excluding_tags"):
        excluding_tags = config["Crawler"]["excluding_tags"].value
    else:
        if not config.has_option("Crawler", "excluding_tags"):
            comment = (
                "tags to exclude for crawler (comma separated)")
        excluding_tags = "manga, muscle, otokonoko, young boy, shota, furry, gay, homo, bodybuilding, macho, yaoi, futa, futanari"
        logger.warning(
            "excluding_tags invalid, using default: " + str(excluding_tags))
    config.set("Crawler", "excluding_tags", excluding_tags)
    if comment != "":
        config["Crawler"]["excluding_tags"].add_before.comment(comment)
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
    if config.has_option("Crawler", "update_interval") and int(config["Crawler"]["update_interval"].value) >= 0:
        update_interval = int(config["Crawler"]["update_interval"].value)
    else:
        if (not config.has_option("Crawler", "update_interval")):
            comment = (
                "minimum interval (seconds) between each background crawl when user is calling the API (set to 0 to disable background crawl)")
        update_interval = 86400
        logger.warning(
            "update_interval invalid, using default: " + str(update_interval))
    config.set("Crawler", "update_interval", str(update_interval))
    if comment != "":
        config["Crawler"]["update_interval"].add_before.comment(comment)
    # reset stop_compression_task flag (default: False)
    stop_compression_task = False

    # save config file
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

    last_update_timestamp = -1
    auth_api(True)
    logger.info("Crawler config loaded")
    crawler_status = "idle"


def auth_api(log_info=False):
    global api
    refreshtoken = get_refresh_token(log_info=log_info)
    api.auth(refresh_token=refreshtoken)
    if log_info:
        user_detail = api.user_detail(api.user_id)
        try:
            logger.info("Pixiv logged in as " + user_detail.user.name)
        except Exception as e:
            logger.critical("Pixiv login failed due to error: " +
                            str(e) + "\n" + traceback.format_exc())
            exit()


def get_crawler_status():
    return crawler_status


def compress_image(image_path, output_path, quality):
    image = Image.open(image_path)
    image = image.convert('RGB')
    image.save(output_path, optimize=True, quality=quality)


def get_extension(filename):
    return os.path.splitext(filename)[1]


# init api
api = AppPixivAPI()

# init logger
logger = logging.getLogger("uvicorn")

# crawler status
crawler_status = "idle"

# read config and auth api
read_config()

# init variables
last_update_timestamp = -1
dismiss_skip_message = False

# init database
if db_minify:
    db = TinyDB(db_path, ensure_ascii=False, encoding='utf-8')
else:
    db = TinyDB(db_path, indent=4, separators=(',', ': '),
                ensure_ascii=False, encoding='utf-8')


def crawl_images(manual=False, force_update=False, dates=[None]):
    global last_update_timestamp, update_interval, crawler_status, dismiss_skip_message
    if (not manual and update_interval == 0):
        if not dismiss_skip_message:
            logger.info("Background crawl disabled, skipping crawl")
            dismiss_skip_message = True
        return
    if (not manual and time.time() - last_update_timestamp < update_interval):
        if not dismiss_skip_message:
            logger.info("Crawl interval of " + str(update_interval) +
                        " seconds not reached, skipping crawl")
            dismiss_skip_message = True
        return
    if (crawler_status != "idle"):
        if not dismiss_skip_message:
            logger.info("Crawler is currently " +
                        crawler_status + ", skipping crawl")
            dismiss_skip_message = True
        return
    crawler_status = 'crawling automatically since update_interval of ' + str(update_interval) + " has been reached" if not manual else 'crawling manually {}{}'.format(
        'and forcing updates ' if force_update else '', 'to crawl from date {} to {}'.format(dates[0], dates[-1]) if dates[0] != None else '')
    logger.info(
        f"Crawler started with config: store_mode={store_mode}, download_folder={download_folder}, download_quality={download_quality}, download_reverse_proxy={download_reverse_proxy}, ranking_modes={get_list(ranking_modes)}, excluding_tags={get_list(excluding_tags)}, {'get_all_ranking_pages, ' if get_all_ranking_pages else ''}{'allow_multiple_pages, ' if allow_multiple_pages else ''}{'get_all_multiple_pages, ' if get_all_multiple_pages else ''}" + crawler_status)
    dismiss_skip_message = False
    image_count = 0
    db_count = 0
    download_count = 0
    # convert excluding_tags to list and convert to lower case
    excluding_tags_list = (tag.lower() for tag in get_list(excluding_tags))
    # crawl images:
    try:
        for i in range(len(dates)):
            crawler_status = 'crawling automatically since update_interval of ' + str(update_interval) + " has been reached" if not manual else 'crawling manually {}{}'.format(
                'and forcing updates ' if force_update else '', 'to crawl from date {} to {} [{}% completed]'.format(dates[0], dates[-1], round(i/len(dates)*100, 2)) if dates[0] != None else '')
            if get_token_expiration():
                auth_api()
            for mode in get_list(ranking_modes):
                if dates[i] == None:
                    next_qs = {"mode": mode}
                else:
                    next_qs = {"mode": mode, "date": dates[i]}
                while next_qs:
                    json_result = api.illust_ranking(**next_qs)
                    if json_result.illusts != None:
                        for illust in json_result.illusts:
                            if (illust.type == "manga"):
                                continue
                            if (not allow_multiple_pages and illust.page_count > 1):
                                continue
                            # if any tag in excluding_tags_list is in illust.tags, skip
                            for tag in illust.tags:
                                if ((tag.name is not None and tag.name.lower() in excluding_tags_list) or (tag.translated_name is not None and tag.translated_name.lower() in excluding_tags_list)):
                                    continue
                            urls = []
                            url = None
                            if illust.page_count == 1:
                                if (download_quality == "original"):
                                    url = illust.meta_single_page.original_image_url
                                elif (download_quality == "large"):
                                    url = illust.image_urls.large
                                else:
                                    url = illust.image_urls.medium
                            if (url == None):
                                for images in illust.meta_pages:
                                    if (download_quality == "original"):
                                        url = images.image_urls.original
                                    elif (download_quality == "large"):
                                        url = images.image_urls.large
                                    else:
                                        url = images.image_urls.medium
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
                                    extension = get_extension(url)
                                    local_filename = slugify(
                                        f"{str(illust.id)}_{illust.user.name}_{illust.title}_p{str(i)}", True) + extension
                                    if download_reverse_proxy != "":
                                        url = url.replace(
                                            "i.pximg.net", download_reverse_proxy)
                                    if(api.download(url, path=download_folder, name=local_filename)):
                                        download_count += 1
                                    local_filename = download_folder + os.sep + local_filename
                                data = {"id": illust.id, "author_id": illust.user.id, "author_name": illust.user.name, "title": illust.title, "page_no": i,
                                        "page_count": illust.page_count, "r18": illust.x_restrict, "ai_type": illust.illust_ai_type, "tags": illust.tags, "url": url, "local_filename": local_filename}
                                # insert into database
                                image_count += 1
                                if (insertDB(pk, data, force_update)):
                                    db_count += 1
                    if (not get_all_ranking_pages):
                        break
                    next_qs = api.parse_qs(json_result.next_url)
        last_update_timestamp = time.time()
    except Exception as e:
        logger.error("Aborting crawler task due to error: " +
                     str(e) + "\n" + traceback.format_exc())
    logger.info(
        f"Crawled {image_count} images, {db_count} images added to database, {download_count} images downloaded")
    crawler_status = "idle"


def compress_images(image_quality: int = 75, force_compress: bool = False, delete_original: bool = False):
    global crawler_status, stop_compression_task
    if (crawler_status != "idle"):
        logger.info("Crawler is currently " +
                        crawler_status + ", skipping image compression")
        return
    q = Query().local_filename.exists() & ~ (Query().local_filename == "")
    if not force_compress:
        q = q & (~ Query().local_filename_compressed.exists())
    results = db.search(q)  # check if local_filename exists
    crawler_status = "compressing images"
    count = 0
    try:
        for image in results:
            crawler_status = "compressing images [{}% completed]".format(
                round((results.index(image))/len(results)*100, 2))
            if stop_compression_task:
                logger.log(logging.INFO, "Stopping image compression task")
                stop_compression_task = False
                break
            if not os.path.exists(image["local_filename"]):
                continue
            if os.path.exists(image["local_filename"]):
                original_filename = image["local_filename"]
                extension = get_extension(original_filename)
                compressed_filename = original_filename.lower().replace(
                    extension, '') + "_compressed" + '.jpg'
                compress_image(original_filename,
                               compressed_filename, image_quality)
                if delete_original:
                    os.remove(original_filename)
                    original_filename = compressed_filename
                db.upsert(
                    Document({"local_filename": original_filename, "local_filename_compressed": compressed_filename}, doc_id=image.doc_id))
                count += 1
    except Exception as e:
        logger.log(logging.ERROR,
                   "Aborting image compression task due to error: " + str(e) + "\n" + traceback.format_exc())
    logger.log(logging.INFO, "Compressed {} images".format(count))
    crawler_status = "idle"
