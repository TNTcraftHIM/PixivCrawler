import apsw
import time
import logging
import traceback
import os
import re
import unicodedata
import configupdater
import xxhash

from PIL import Image, ImageFile, UnidentifiedImageError
from pixivpy3 import *
from pixiv_auth_selenium import get_refresh_token, get_token_expiration, get_proxy

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


def substring_in_list(s, substrings):
    for substring in substrings:
        if substring.startswith('*') and substring.endswith('*'):
            substring = substring.replace('*', '') # Remove '*' and perform fuzzy matching
            if substring in s:
                return True
        elif substring.startswith('*'):
            substring = substring.replace('*', '') + '$' # Replace '*' with empty and add '$' at the end to indicate the end of the string
            if re.search(substring, s):
                return True
        elif substring.endswith('*'):
            substring = '^' + substring.replace('*', '') # Replace '*' with empty and add '^' at the beginning to indicate the start of the string
            if re.search(substring, s):
                return True
        else:  # If the substring does not contain '*', perform full word matching
            if substring == s:
                return True
    return False


def initDB(db_path: str = "db.sqlite3"):
    db = apsw.Connection(db_path)
    cursor = db.cursor()

    # Create pictures table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pictures (
    picture_id INTEGER PRIMARY KEY,
    id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    author_name TEXT NOT NULL,
    title TEXT NOT NULL,
    page_no INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    r18 TINYINT NOT NULL,
    ai_type TINYINT NOT NULL,
    url TEXT NOT NULL,
    local_filename TEXT NOT NULL DEFAULT '',
    local_filename_compressed TEXT NOT NULL DEFAULT ''
    );''')

    # Create indices for pictures table
    cursor.execute('CREATE INDEX IF NOT EXISTS index_pictures_author_name ON pictures(author_name);')
    cursor.execute('CREATE INDEX IF NOT EXISTS index_pictures_r18 ON pictures(r18);')
    cursor.execute('CREATE INDEX IF NOT EXISTS index_pictures_ai_type ON pictures(ai_type);')

    # Create tags table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    translated_name TEXT UNIQUE
    );''')

    # Create tags_fts table and triggers
    cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS tags_fts USING FTS5(name, translated_name, content="tags", content_rowid="tag_id", tokenize='unicode61');
    ''')
    # Create triggers for insert, delete and update operations
    # Trigger for insert operation
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS tags_ai AFTER INSERT ON tags BEGIN
        INSERT INTO tags_fts(rowid, name, translated_name) VALUES (new.tag_id, new.name, new.translated_name);
    END;
    ''')
    # Trigger for delete operation
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS tags_ad AFTER DELETE ON tags BEGIN
        INSERT INTO tags_fts(tags_fts, rowid, name, translated_name) VALUES('delete', old.tag_id, old.name, old.translated_name);
    END;
    ''')
    # Trigger for update operation
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS tags_au AFTER UPDATE ON tags BEGIN
        INSERT INTO tags_fts(tags_fts, rowid, name, translated_name) VALUES('delete', old.tag_id, old.name, old.translated_name);
        INSERT INTO tags_fts(rowid, name, translated_name) VALUES (new.tag_id, new.name, new.translated_name);
    END;
    ''')

    # Create picture_tags table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS picture_tags (
    picture_id INTEGER REFERENCES pictures(picture_id) ON DELETE CASCADE ON UPDATE CASCADE,
    tag_id INTEGER REFERENCES tags(tag_id) ON DELETE CASCADE ON UPDATE CASCADE,
    PRIMARY KEY (picture_id, tag_id)
    );''')

    # Create indices for picture_tags table
    cursor.execute('CREATE INDEX IF NOT EXISTS index_picture_tags_picture_id ON picture_tags(picture_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS index_picture_tags_tag_id ON picture_tags(tag_id);')

    # commit by apsw

    return db


def lenDB():
    global db
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM pictures")
    return cursor.fetchone()[0]


def insertDB(pk, data, force_update=False):
    global db
    # convert pk into xxhash integer
    pk = xxhash.xxh32_intdigest(pk)
    try:
        # create a cursor object
        cursor = db.cursor()
        # check if force_update is True
        if force_update:
            # use the INSERT OR REPLACE statement to proform 'UPSERT' operation
            cursor.execute("INSERT OR REPLACE INTO pictures (picture_id, id, author_id, author_name, title, page_no, page_count, r18, ai_type, url, local_filename, local_filename_compressed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, (SELECT local_filename_compressed FROM pictures WHERE picture_id = ?))", ((
                pk), data["id"], data["author_id"], data["author_name"], data["title"], data["page_no"], data["page_count"], data["r18"], data["ai_type"], data["url"], data["local_filename"], pk))
            # commit changes
            # commit by apsw
            # insert tags
            for tag in data["tags"]:
                # calculate tag_id by hashing tag name
                tag_id = xxhash.xxh32_intdigest(str(tag["name"]))
                # use the INSERT OR REPLACE statement to proform 'UPSERT' operation
                cursor.execute("INSERT OR REPLACE INTO tags (tag_id, name, translated_name) VALUES (?, ?, ?)", ((tag_id, tag["name"], tag["translated_name"])))
                # commit changes
                # commit by apsw
                # use the INSERT OR REPLACE statement to proform 'UPSERT' operation
                cursor.execute(
                    "INSERT OR REPLACE INTO picture_tags (picture_id, tag_id) VALUES (?, (SELECT tag_id FROM tags WHERE name = ?))", ((pk), tag["name"]))
                # commit changes
                # commit by apsw
        else:
            # use the INSERT statement to insert data only if it does not exist
            cursor.execute("INSERT INTO pictures (picture_id, id, author_id, author_name, title, page_no, page_count,r18, ai_type, url, local_filename) VALUES (?, ?, ?, ?, ?, ?, ? , ? , ? , ? , ?)", ((
                pk), data["id"], data["author_id"], data["author_name"], data["title"], data["page_no"], data["page_count"], data["r18"], data["ai_type"], data["url"], data["local_filename"]))
            # commit changes
            # commit by apsw
            # insert tags
            for tag in data["tags"]:
                # calculate tag_id by hashing tag name
                tag_id = xxhash.xxh32_intdigest(str(tag["name"]))
                # use the INSERT OR IGNORE statement to insert data only if it does not exist
                cursor.execute("INSERT OR IGNORE INTO tags (tag_id, name, translated_name) VALUES (?, ?, ?)", ((tag_id, tag["name"], tag["translated_name"])))
                # commit changes
                # commit by apsw
                # use the INSERT OR IGNORE statement to insert data only if it does not exist
                cursor.execute(
                    "INSERT OR IGNORE INTO picture_tags (picture_id, tag_id) VALUES (?, (SELECT tag_id FROM tags WHERE name = ?))", ((pk), tag["name"]))
                # commit changes
                # commit by apsw
        return True
    except apsw.ConstraintError as e:
        if force_update:
            logger.warning(
                "Aborting database insertion for picture_id: " + str(pk) + " due to error: " + str(e))
        return False
    except Exception as e:
        logger.error("Aborting database insertion for picture_id: " + str(pk) + " due to error: " +
              str(e) + "\n" + traceback.format_exc())
        return False


def cursor_to_dict(cursor: apsw.Cursor, query: str):
    cursor.execute(query)
    rows = cursor.fetchone()
    if rows:
        columns = [desc[0] for desc in cursor.getdescription()]
        rows = [rows] + cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    return []


def get_list(string: str):
    list = []
    for x in string.split(","):
        x = x.strip()
        if x:
            list.append(x)
    return list


def read_config():
    global api, config, db_path, store_mode, download_folder, download_quality, download_reverse_proxy, ranking_modes, get_all_ranking_pages, allow_multiple_pages, get_all_multiple_pages, update_interval, crawler_status, last_update_timestamp, excluding_tags, stop_compression_task, max_rate_limit_retries
    crawler_status = "reloading config"
    # read config file
    config = configupdater.ConfigUpdater()
    config.read('config.ini', encoding='utf-8')
    if not os.path.exists('config.ini'):
        # Create config file
        with open('config.ini', 'w', encoding='utf-8'):
            pass
    if not config.has_section("Crawler"):
        config.append("\n")
        config.add_section("Crawler")
    # get db_path to determine where to store the database (default: db.sqlite3)
    if config.has_option("Crawler", "db_path") and config["Crawler"]["db_path"].value != "":
        db_path = config["Crawler"]["db_path"].value
    else:
        db_path = "db.sqlite3"
        logger.warning("db_path invalid, using default: " + db_path)
    config.set("Crawler", "db_path", db_path)
    # get store_mode to determine whether to store images as links or download them (default: light)
    comment = ""
    if config.has_option("Crawler", "store_mode") and (config["Crawler"]["store_mode"].value in ["light", "full"]):
        store_mode = config["Crawler"]["store_mode"].value
    else:
        if not config.has_option("Crawler", "store_mode"):
            comment = (
                "light(store image urls only, functions under /api/v1/img will not work), full(store images locally)")
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
                "tags to exclude for crawler (comma separated)， add '*' for wildcard matching, e.g. *furry* for all tags containing 'furry'")
        excluding_tags = "manga, muscle, otokonoko, young boy, shota, furry, gay, homo, bodybuilding, macho, yaoi, futa, futanari, *漫画*"
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
    comment = ""
    if config.has_option("Crawler", "allow_multiple_pages"):
        allow_multiple_pages = bool(
            config["Crawler"]["allow_multiple_pages"].value.capitalize() == "True")
    else:
        comment = (
            "True(allow illustrations with multiple pages), False(only get illustrations with one page)")
        allow_multiple_pages = False
        logger.warning("allow_multiple_pages invalid, using default: " +
                       str(allow_multiple_pages))
    config.set("Crawler", "allow_multiple_pages", allow_multiple_pages)
    if comment != "":
        config["Crawler"]["allow_multiple_pages"].add_before.comment(comment)
    # get get_all_multiple_pages flag (default: False, only get the first page)
    comment = ""
    if config.has_option("Crawler", "get_all_multiple_pages"):
        get_all_multiple_pages = bool(
            config["Crawler"]["get_all_multiple_pages"].value.capitalize() == "True")
    else:
        comment = (
            "True(get all pages of illustrations with multiple pages), False(only get the first page)")
        get_all_multiple_pages = False
        logger.warning("get_all_multiple_pages invalid, using default: " +
                       str(get_all_multiple_pages))
    config.set("Crawler", "get_all_multiple_pages", get_all_multiple_pages)
    if comment != "":
        config["Crawler"]["get_all_multiple_pages"].add_before.comment(comment)
    # get update_interval
    comment = ""
    if config.has_option("Crawler", "update_interval") and int(config["Crawler"]["update_interval"].value) >= 0:
        update_interval = int(config["Crawler"]["update_interval"].value)
    else:
        if (not config.has_option("Crawler", "update_interval")):
            comment = (
                "minimum interval (seconds) between each automatic crawl when user is calling the API (set to 0 to disable automatic crawl)")
        update_interval = 0
        logger.warning(
            "update_interval invalid, using default: " + str(update_interval))
    config.set("Crawler", "update_interval", str(update_interval))
    if comment != "":
        config["Crawler"]["update_interval"].add_before.comment(comment)
    # get max_rate_limit_retries
    comment = ""
    if config.has_option("Crawler", "max_rate_limit_retries") and int(config["Crawler"]["max_rate_limit_retries"].value) >= 0:
        max_rate_limit_retries = int(
            config["Crawler"]["max_rate_limit_retries"].value)
    else:
        if (not config.has_option("Crawler", "max_rate_limit_retries")):
            comment = (
                "maximum number of retries when encountering rate limit, each retry will pause for 30 seconds")
        max_rate_limit_retries = 5
        logger.warning("max_rate_limit_retries invalid, using default: " +
                       str(max_rate_limit_retries))
    config.set("Crawler", "max_rate_limit_retries", str(max_rate_limit_retries))
    if comment != "":
        config["Crawler"]["max_rate_limit_retries"].add_before.comment(comment)
    # reset stop_compression_task flag (default: False)
    stop_compression_task = False

    # save config file
    with open('config.ini', 'w', encoding='utf-8') as configfile:
        config.write(configfile)

    last_update_timestamp = -1
    auth_api(True)
    logger.info("Crawler config loaded")
    crawler_status = "idle"


def auth_api(log_info=False):
    global api
    # init api
    refreshtoken = get_refresh_token(log_info=log_info)
    proxy = get_proxy()
    REQUESTS_KWARGS = {
        'proxies': {
            'https': proxy,
            'http': proxy
        }
    }
    api = AppPixivAPI(**REQUESTS_KWARGS)
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
db = initDB(db_path)


def crawl_images(manual=False, force_update=False, dates=[None]):
    class RateLimitException(Exception):
        pass
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
    excluding_tags_list = [tag.lower() for tag in get_list(excluding_tags)]
    # crawl images:
    try:
        for date in dates:
            crawler_status = 'crawling automatically since update_interval of ' + str(update_interval) + " has been reached" if not manual else 'crawling manually {}{}'.format('and forcing updates ' if force_update else '', 'to crawl from date {} to {} [{}% completed]'.format(dates[0], dates[-1], round(dates.index(date)/len(dates)*100, 2)) if dates[0] != None else '')
            if get_token_expiration():
                auth_api()
            for mode in get_list(ranking_modes):
                if date == None:
                    next_qs = {"mode": mode}
                else:
                    next_qs = {"mode": mode, "date": date}
                while next_qs:
                    json_result = api.illust_ranking(**next_qs)
                    rate_limit_retries_count = 0
                    while "rate limit" in str(json_result).lower():
                        if rate_limit_retries_count >= max_rate_limit_retries:
                            raise RateLimitException
                        rate_limit_retries_count += 1
                        logger.warning(
                            "Crawler rate limit encountered, retrying in 30 seconds (" + str(rate_limit_retries_count) + "/" + str(max_rate_limit_retries) + " retries)")
                        # Pause for 30 seconds and try again
                        time.sleep(30)
                        json_result = api.illust_ranking(**next_qs)
                    if json_result.illusts != None:
                        for illust in json_result.illusts:
                            if (illust.type == "manga" and "manga" in excluding_tags_list):
                                continue
                            if (not allow_multiple_pages and illust.page_count > 1):
                                continue
                            # if any tag in excluding_tags_list is in illust.tags, skip
                            excluding_tags_found = False
                            for tag in illust.tags:
                                if (excluding_tags_list and ((tag.name is not None and substring_in_list(tag.name.lower(), excluding_tags_list)) or (tag.translated_name is not None and substring_in_list(tag.translated_name.lower(), excluding_tags_list)))):
                                    excluding_tags_found = True
                                    break
                            if excluding_tags_found:
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
                                        download_url = url.replace(
                                            "i.pximg.net", download_reverse_proxy)
                                    local_filename = download_folder + os.sep + local_filename
                                data = {"id": illust.id, "author_id": illust.user.id, "author_name": illust.user.name, "title": illust.title, "page_no": i,
                                        "page_count": illust.page_count, "r18": illust.x_restrict, "ai_type": illust.illust_ai_type, "tags": illust.tags, "url": url, "local_filename": local_filename}
                                image_count += 1
                                # insert into database
                                if (insertDB(pk, data, force_update)):
                                    db_count += 1
                                    # download images if local_filename is not empty
                                    if(local_filename):
                                        if (not os.path.exists(download_folder)):
                                            os.makedirs(download_folder)
                                        if (api.download(download_url, name=local_filename)):
                                            download_count += 1
                    if (not get_all_ranking_pages):
                        break
                    next_qs = api.parse_qs(json_result.next_url)
        last_update_timestamp = time.time()
    except RateLimitException:
        logger.error(" Aborting crawler task due to error: rate limit retries of " + str(max_rate_limit_retries) + "/" + str(max_rate_limit_retries) + " reached")
    except Exception as e:
        logger.error("Aborting crawler task due to error: " +
                     str(e) + "\n" + traceback.format_exc())
    logger.info(
        f"Crawled {image_count} images, {db_count} images added to database, {download_count} images downloaded")
    crawler_status = "idle"


def compress_images(image_quality: int = 75, force_compress: bool = False, delete_original: bool = False):
    global db, crawler_status, stop_compression_task
    if (crawler_status != "idle"):
        logger.info("Crawler is currently " +
                    crawler_status + ", skipping image compression")
        return
    cursor = db.cursor()
    results = cursor_to_dict(cursor, "SELECT * FROM pictures WHERE local_filename != ''{}".format(" AND local_filename_compressed = ''" if not force_compress else ""))
    crawler_status = "compressing images"
    logger.info(
        "Image compression task started with quality {}".format(image_quality))
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
                try:
                    compress_image(original_filename,
                                   compressed_filename, image_quality)
                except (FileNotFoundError, UnidentifiedImageError):
                    logger.log(logging.ERROR,
                               "Skipping file '{}' due to being an invalid image".format(original_filename))
                    remove_local_file(image["picture_id"])
                    continue
                if delete_original:
                    os.remove(original_filename)
                    original_filename = compressed_filename
                cursor.execute(  # update both local_filename and local_filename_compressed
                    "UPDATE pictures SET local_filename = ?, local_filename_compressed = ? WHERE picture_id = ?", (original_filename, compressed_filename, image["picture_id"]))
                # commit by apsw
                count += 1
    except Exception as e:
        logger.log(logging.ERROR,
                   "Aborting image compression task due to error: " + str(e) + "\n" + traceback.format_exc())
    logger.log(logging.INFO, "Compressed {} images, {} invalid images skipped and removed".format(
        count, len(results) - count))
    crawler_status = "idle"


def remove_local_file(picture_id, remove_only_compressed: bool = False):
    global db
    cursor = db.cursor()
    image = cursor_to_dict(cursor, "SELECT * FROM pictures WHERE picture_id = ?", (picture_id,))[0]
    if image:
        remove_only_compressed = (
            image["local_filename_compressed"] != image["local_filename"]) and remove_only_compressed
        logger.log(logging.INFO, ("Removing file '{}' and related references".format(
            image["local_filename"])))
        if not remove_only_compressed and image["local_filename"] and os.path.exists(image["local_filename"]):
            os.remove(image["local_filename"])
        if "local_filename_compressed" in image and os.path.exists(image["local_filename_compressed"]):
            os.remove(image["local_filename_compressed"])
        cursor.execute(
            "UPDATE pictures SET local_filename_compressed = ''{} WHERE picture_id = ?".format(", local_filename = ''" if not remove_only_compressed else ""), (picture_id,))
        # commit by apsw
