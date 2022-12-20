import os
import re
import random
import logging
import configupdater
import pixiv_crawler

from typing import Optional, List
from fastapi import FastAPI, BackgroundTasks, Query as QueryParam
from fastapi.responses import FileResponse
from tinydb import TinyDB, where, Query


def read_config():
    global reverse_proxy, image_num_limit, author_num_limit, tag_num_limit
    config = configupdater.ConfigUpdater()
    if not os.path.exists('config.ini'):
        # Create config file
        with open('config.ini', 'w'):
            pass
    config.read('config.ini')
    if not config.has_section("API"):
        config.add_section("API")
        logger.info("First run, crawling before starting")
        pixiv_crawler.crawl_images()
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
        q = q & where("id") == id
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
        q = q & where("ai_type") == ai_type
    if tags != []:
        if len(tags) > tag_num_limit:
            tags = (tags)[:tag_num_limit]
        q = q & Query().tags.any(Query().translated_name.matches(r"(?=("+'|'.join(tags)+r"))",
                                                                 flags=re.IGNORECASE) or Query().name.matches(r"(?=("+'|'.join(tags)+r"))", flags=re.IGNORECASE))
    if local_file:
        q = q & where("local_filename").matches(r".+")
    if q == baseq:
        results = [db.all()[random.randint(1, len(db) - 1)]]
    else:
        results = db.search(q)
        if len(results) >= num:
            results = random.sample(results, num)
    return results


app = FastAPI()


@app.on_event("startup")
async def startup_event():
    global logger, db
    logger = logging.getLogger("uvicorn")
    db = TinyDB('db.json', ensure_ascii=False)
    read_config()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/api/v1")
def get_image_json(background_tasks: BackgroundTasks, r18: Optional[int] = 2, num: Optional[int] = 1, id: Optional[int] = None, author_ids: Optional[List[int]] = QueryParam(default=[]), author_names: Optional[List[str]] = QueryParam(default=[]), title: Optional[str] = "", ai_type: Optional[int] = None, tags: Optional[List[str]] = QueryParam(default=[])):
    background_tasks.add_task(pixiv_crawler.crawl_images)
    results = randomDB(r18=r18, num=num, id=id, author_ids=author_ids,
                       author_names=author_names, title=title, ai_type=ai_type, tags=tags)
    if not results:
        return {"status": "error", "data": "no results"}
    for item in results:
        item["url"] = item["url"].replace("i.pximg.net", reverse_proxy)
    return {"status": "success", "data": results}

# reload config for crawler and api


@app.get("/api/v1/img")
# directly return image file
def get_image(background_tasks: BackgroundTasks, r18: Optional[int] = 2, id: Optional[int] = None, author_ids: Optional[List[int]] = QueryParam(default=[]), author_names: Optional[List[str]] = QueryParam(default=[]), title: Optional[str] = "", ai_type: Optional[int] = None, tags: Optional[List[str]] = QueryParam(default=[])):
    background_tasks.add_task(pixiv_crawler.crawl_images)
    results = randomDB(r18=r18, id=id, author_ids=author_ids,
                       author_names=author_names, title=title, ai_type=ai_type, tags=tags, local_file=True)
    if not results:
        return {"status": "error", "data": "no results"}
    return FileResponse(results[0]["local_filename"])


@app.get("/api/v1/reload")
def reload():
    read_config()
    pixiv_crawler.read_config()
    return {"status": "success"}
