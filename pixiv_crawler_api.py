import os
import re
import logging
import datetime
import configupdater
import pixiv_crawler

from typing import Optional, List
from numpy.random import default_rng
from fastapi import FastAPI, BackgroundTasks, Query as QueryParam
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from tinydb import TinyDB, where, Query


def read_config():
    global privilege_api_key, reverse_proxy, image_num_limit, author_num_limit, tag_num_limit, stop_compression_task
    config = configupdater.ConfigUpdater()
    if not os.path.exists('config.ini'):
        # Create config file
        with open('config.ini', 'w'):
            pass
    config.read('config.ini')
    if not config.has_section("API"):
        config.append("\n")
        config.add_section("API")
    if len(db) == 0:
        logger.info("First run, crawling before starting")
        pixiv_crawler.crawl_images()
    # privilege API key
    comment = ""
    if config.has_option("API", "privilege_api_key") and config["API"]["privilege_api_key"].value != "":
        privilege_api_key = config["API"]["privilege_api_key"].value
    else:
        if not config.has_option("API", "privilege_api_key"):
            comment = "API key for privileged API calls (e.g. reload config/crawl images from past dates)"
        # generate random key of length 32 using choice
        privilege_api_key = ''.join(random.choice(list(
            "0123456789abcdef"), 32))
        logger.warning(
            "privilege_api_key invalid, using default: " + privilege_api_key)
    config.set("API", "privilege_api_key", privilege_api_key)
    if comment != "":
        config["API"]["privilege_api_key"].add_before.comment(comment)
    # reverse proxy config
    comment = ""
    if config.has_option("API", "reverse_proxy"):
        reverse_proxy = config["API"]["reverse_proxy"].value
    else:
        comment = "reverse proxy for image urls in API reponses (e.g. i.pixiv.re)"
        reverse_proxy = "i.pixiv.re"
        logger.warning(
            "reverse_proxy invalid, using default: " + reverse_proxy)
    config.set("API", "reverse_proxy", reverse_proxy)
    if comment != "":
        config["API"]["reverse_proxy"].add_before.comment(comment)
    # limit of number of images to return
    comment = ""
    if config.has_option("API", "image_num_limit") and config["API"]["image_num_limit"].value.isdigit():
        image_num_limit = int(config["API"]["image_num_limit"].value)
    else:
        comment = "limit of maximum number of images to return"
        image_num_limit = 10
        logger.warning(
            "image_num_limit invalid, using default: " + str(image_num_limit))
    config.set("API", "image_num_limit", image_num_limit)
    if comment != "":
        config["API"]["image_num_limit"].add_before.comment(comment)
    # limit of number of authors in query
    comment = ""
    if config.has_option("API", "author_num_limit") and config["API"]["author_num_limit"].value.isdigit():
        author_num_limit = int(config["API"]["author_num_limit"].value)
    else:
        comment = "limit of maximum number of authors in query"
        author_num_limit = 5
        logger.warning(
            "author_num_limit invalid, using default: " + str(author_num_limit))
    config.set("API", "author_num_limit", author_num_limit)
    if comment != "":
        config["API"]["author_num_limit"].add_before.comment(comment)
    # limit of number of tags in query
    comment = ""
    if config.has_option("API", "tag_num_limit") and config["API"]["tag_num_limit"].value.isdigit():
        tag_num_limit = int(config["API"]["tag_num_limit"].value)
    else:
        comment = "limit of maximum number of tags in query"
        tag_num_limit = 10
        logger.warning(
            "tag_num_limit invalid, using default: " + str(tag_num_limit))
    config.set("API", "tag_num_limit", tag_num_limit)
    if comment != "":
        config["API"]["tag_num_limit"].add_before.comment(comment)
    # reset stop compression task flag
    stop_compression_task = False
    # save config
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    logger.log(logging.INFO, "API config loaded")


def randomDB(r18: int = 2, num: int = 1, id: int = None, author_ids: List[int] = [], author_names: List[str] = [], title: str = "", ai_type: int = None, tags: List[str] = [], local_file: bool = False):
    if len(db) == 0:
        return
    if r18 not in [0, 1, 2]:
        r18 = 2
    baseq = where("r18").one_of([0, 1])
    if r18 in [0, 1]:
        q = where("r18") == r18
    else:
        q = baseq
    if num < 1:
        num = 1
    if num > image_num_limit:
        num = image_num_limit
    if id != None:
        q = q & (where("id") == id)
    if author_ids != []:
        if len(author_ids) > author_num_limit:
            author_ids = (author_ids)[:author_num_limit]
        q = q & where("author_id").one_of(author_ids)
    if author_names != []:
        if len(author_names) > author_num_limit:
            author_names = (author_names)[:author_num_limit]
        q = q & where("author_name").matches(
            r"(?=("+'|'.join(author_names)+r"))", flags=re.IGNORECASE)
    if title != "":
        q = q & where("title").search(title)
    if ai_type != None:
        q = q & (where("ai_type") == ai_type)
    if tags != []:
        if len(tags) > tag_num_limit:
            tags = (tags)[:tag_num_limit]
        q = q & Query().tags.any(Query().translated_name.matches(r"(?=("+'|'.join(tags)+r"))",
                                                                 flags=re.IGNORECASE) | Query().name.matches(r"(?=("+'|'.join(tags)+r"))", flags=re.IGNORECASE))
    if local_file:
        q = q & where("local_filename").matches(r".+")
    if q == baseq:
        results = db.all()
    else:
        results = db.search(q)
    results_len = len(results)
    if results_len < num:
        num = results_len
    results = list(random.choice(results, num, replace=False))
    return results


def clear_db_cache():
    # this function should only be invoked by pixiv_crawler.py
    db.clear_cache()
    logger.info("DB cache cleared")


def convert_date(date_text):
    try:
        date = datetime.datetime.strptime(date_text, '%Y-%m-%d')
        # keep only date part and return
        return date.date()
    except ValueError:
        return False


def get_dates(start_date: datetime.date, end_date: datetime.date = datetime.date.today()):
    dates = []
    while start_date <= end_date:
        dates.append(start_date.strftime('%Y-%m-%d'))
        start_date += datetime.timedelta(days=1)
    return dates


def get_days_ago_date(days_ago: int):
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime('%Y-%m-%d')


app = FastAPI()
random = default_rng()


@app.on_event("startup")
async def startup_event():
    global logger, db
    logger = logging.getLogger("uvicorn")
    db = TinyDB('db.json', ensure_ascii=False, encoding='utf-8')
    db = db.table("_default", cache_size=None)
    read_config()


@app.get("/", description="Get PixivCrawler API credit info and crawler status")
def read_info():
    return {"PixivCrawler": "GitHub@TNTcraftHIM", "status": "crawler is currently " + pixiv_crawler.get_crawler_status()}


@app.get("/api/v1", description="Get image JSON according to query")
def get_image_json(background_tasks: BackgroundTasks, r18: Optional[int] = QueryParam(default=2, description="Whether to include R18 images (0 = No R18 images, 1 = Only R18 image, 2 = Both)"), num: Optional[int] = QueryParam(default=1, description="Specify number of illustrations"), id: Optional[int] = QueryParam(default=None, description="Specify illustrations' ID"), author_ids: Optional[List[int]] = QueryParam(default=[], description="Specify list of authors' (ID) illustrations"), author_names: Optional[List[str]] = QueryParam(default=[], description="Specify list of authors' (name) illustrations"), title: Optional[str] = QueryParam(default="", description="Specify keywords in illustrations' title"), ai_type: Optional[int] = QueryParam(default=None, description="Specify illustrations' ai_type"), tags: Optional[List[str]] = QueryParam(default=[], description="Specify list of tags in illustrations")):
    background_tasks.add_task(pixiv_crawler.crawl_images)
    results = randomDB(r18=r18, num=num, id=id, author_ids=author_ids,
                       author_names=author_names, title=title, ai_type=ai_type, tags=tags)
    if not results:
        return {"status": "error", "data": "no result"}
    for item in results:
        item["url"] = item["url"].replace("i.pximg.net", reverse_proxy)
        del item["local_filename"]
        # also delete local_filename_compressed if exists
        if "local_filename_compressed" in item:
            del item["local_filename_compressed"]
    return JSONResponse({"status": "success", "data": results}, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json; charset=utf-8"})


@app.get("/api/v1/img", description="Get image file from local storage according to query (need store_mode to be \"full\" and have files downloaded in local storage)")
# directly return image file
def get_image_file(background_tasks: BackgroundTasks, r18: Optional[int] = QueryParam(default=2, description="Whether to include R18 images (0 = No R18 images, 1 = Only R18 image, 2 = Both)"), id: Optional[int] = QueryParam(default=None, description="Specify illustrations' ID"), author_ids: Optional[List[int]] = QueryParam(default=[], description="Specify list of authors' (ID) illustrations"), author_names: Optional[List[str]] = QueryParam(default=[], description="Specify list of authors' (name) illustrations"), title: Optional[str] = QueryParam(default="", description="Specify keywords in illustrations' title"), ai_type: Optional[int] = QueryParam(default=None, description="Specify illustrations' ai_type"), tags: Optional[List[str]] = QueryParam(default=[], description="Specify list of tags in illustrations")):
    background_tasks.add_task(pixiv_crawler.crawl_images)
    results = randomDB(r18=r18, id=id, author_ids=author_ids,
                       author_names=author_names, title=title, ai_type=ai_type, tags=tags, local_file=True)
    if not results or not results[0]["local_filename"] or not os.path.exists(results[0]["local_filename"]):
        return {"status": "error", "data": "no result"}
    filename = results[0]["local_filename"]
    if "local_filename_compressed" in results[0] and os.path.exists(results[0]["local_filename_compressed"]):
        filename = results[0]["local_filename_compressed"]
    return FileResponse(filename, headers={"Access-Control-Allow-Origin": "*"})


@app.get("/api/v1/html", description="Get image in a HTML page according to query")
def get_image_html(background_tasks: BackgroundTasks, r18: Optional[int] = QueryParam(default=2, description="Whether to include R18 images (0 = No R18 images, 1 = Only R18 image, 2 = Both)"), id: Optional[int] = QueryParam(default=None, description="Specify illustrations' ID"), author_ids: Optional[List[int]] = QueryParam(default=[], description="Specify list of authors' (ID) illustrations"), author_names: Optional[List[str]] = QueryParam(default=[], description="Specify list of authors' (name) illustrations"), title: Optional[str] = QueryParam(default="", description="Specify keywords in illustrations' title"), ai_type: Optional[int] = QueryParam(default=None, description="Specify illustrations' ai_type"), tags: Optional[List[str]] = QueryParam(default=[], description="Specify list of tags in illustrations")):
    background_tasks.add_task(pixiv_crawler.crawl_images)
    results = randomDB(r18=r18, id=id, author_ids=author_ids,
                       author_names=author_names, title=title, ai_type=ai_type, tags=tags)
    if not results:
        return {"status": "error", "data": "no result"}
    results = results[0]
    url = results["url"].replace("i.pximg.net", reverse_proxy)
    html = "<html style=\"background-repeat: no-repeat; background-position: center; background-attachment: scroll; background-size: cover; height: 100%; margin: 0; background-image: url('{}');\"> <head> <title>{}</title> </head> <body style=\"background-repeat: no-repeat; background-position: center; background-attachment: scroll; background-size: cover; height: 100%; margin: 0; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); -moz-backdrop-filter: blur(10px); -o-backdrop-filter: blur(10px); -ms-backdrop-filter: blur(10px);\"> <img style=\"display: block; margin-left: auto; margin-right: auto; height: 100%;\" src=\"{}\" /> </body> </html>".format(
        url, "["+results["author_name"]+"]" + results["title"], url)
    return HTMLResponse(html, headers={"Access-Control-Allow-Origin": "*"})


@app.get("/api/v1/redirect", description="Get image and redirect to its URL according to query")
def get_image_redirect(background_tasks: BackgroundTasks, r18: Optional[int] = QueryParam(default=2, description="Whether to include R18 images (0 = No R18 images, 1 = Only R18 image, 2 = Both)"), id: Optional[int] = QueryParam(default=None, description="Specify illustrations' ID"), author_ids: Optional[List[int]] = QueryParam(default=[], description="Specify list of authors' (ID) illustrations"), author_names: Optional[List[str]] = QueryParam(default=[], description="Specify list of authors' (name) illustrations"), title: Optional[str] = QueryParam(default="", description="Specify keywords in illustrations' title"), ai_type: Optional[int] = QueryParam(default=None, description="Specify illustrations' ai_type"), tags: Optional[List[str]] = QueryParam(default=[], description="Specify list of tags in illustrations")):
    background_tasks.add_task(pixiv_crawler.crawl_images)
    results = randomDB(r18=r18, id=id, author_ids=author_ids,
                       author_names=author_names, title=title, ai_type=ai_type, tags=tags)
    if not results:
        return {"status": "error", "data": "no result"}
    return RedirectResponse(results[0]["url"].replace("i.pximg.net", reverse_proxy), status_code=302, headers={"Access-Control-Allow-Origin": "*"})


@app.get("/api/v1/crawl", description="Manually add crawl task, could be used to crawl images from the past (need api_key to work)")
# manually crawl images (need correct api key to work)
def crawl(background_tasks: BackgroundTasks, api_key: str, force_update: Optional[bool] = QueryParam(default=False, description="Whether to update records in the database if it already exists"), start_date: Optional[str] = QueryParam(default=None, description="Start date for crawler to crawl from", example=get_days_ago_date(2)), end_date: Optional[str] = QueryParam(default=None, description="End date for crawler to crawl from, could be empty if start date is specified (will crawl until today)", example=get_days_ago_date(0))):
    if api_key != privilege_api_key:
        return {"status": "error", "data": "invalid api key"}
    if start_date != None:
        start_date = convert_date(start_date)
        if not start_date:
            return {"status": "error", "data": "invalid start_date, should be YYYY-MM-DD"}
    if end_date != None:
        end_date = convert_date(end_date)
        if not end_date:
            return {"status": "error", "data": "invalid end_date, should be YYYY-MM-DD"}
        if start_date == None:
            return {"status": "error", "data": "start_date should be specified if end date is specified"}
        if start_date != None and start_date > end_date:
            return {"status": "error", "data": "start_date should be earlier than end date"}
    dates = [None]
    if start_date != None:
        if end_date != None:
            dates = get_dates(start_date, end_date)
        else:
            dates = get_dates(start_date)
    crawler_status = pixiv_crawler.get_crawler_status()
    if crawler_status != "idle":
        return {"status": "error", "data": "crawler is currently " + crawler_status + ", please wait until it is done"}
    background_tasks.add_task(
        pixiv_crawler.crawl_images, True, force_update, dates)
    return {"status": "success", "data": f"crawl task {'from date {} to {} '.format(dates[0], dates[-1]) if start_date != None else ''}added"}


@app.get("/api/v1/compress", description="Compress local images (need api_key to work)")
# compress local images (need correct api key to work)
def compress(background_tasks: BackgroundTasks, api_key: str, stop_task: Optional[bool] = QueryParam(default=False, description="Whether to stop compression task if it is running"), force_compress: Optional[bool] = QueryParam(default=False, description="Whether to compress an image if it is already compressed"), delete_original: Optional[bool] = QueryParam(default=False, description="Whether to delete original image after compression (Warning: This operation cannot be undone)"), image_quality: Optional[int] = QueryParam(default=75, description="Image quality for compression (0-100)")):
    if api_key != privilege_api_key:
        return {"status": "error", "data": "invalid api key"}
    pixiv_crawler.stop_compression_task = stop_task
    if stop_task:
        return {"status": "success", "data": "image compression task stopped"}
    crawler_status = pixiv_crawler.get_crawler_status()
    if crawler_status != "idle":
        return {"status": "error", "data": "crawler is currently " + crawler_status + ", please wait until it is done"}
    background_tasks.add_task(
        pixiv_crawler.compress_images, image_quality=image_quality, force_compress=force_compress, delete_original=delete_original)
    return {"status": "success", "data": "image compression task added"}


@app.get("/api/v1/reload", description="Reload config for crawler and API (need api_key to work)")
# reload config for crawler and api
# need correct api key to work
def reload(api_key: str):
    if api_key != privilege_api_key:
        return {"status": "error", "data": "invalid api key"}
    read_config()
    pixiv_crawler.read_config()
    return {"status": "success"}
