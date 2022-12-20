import os
import re
import random
import logging
import configupdater
import pixiv_crawler

from typing import Optional, List
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse
from tinydb import TinyDB, where, Query


def read_config():
    global reverse_proxy
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

    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    logger.log(logging.INFO, "API config loaded")


def randomDB(r18: int = 0, num: int = 1, id: int = -1, author_ids: List[int] = [], author_names: List[str] = [], title: str = "", ai_type: int = -1, tags: List[str] = [], local_file: bool = False):
    if r18 not in [0, 1]:
        r18 = 0
    q = where("r18") == r18
    if num < 1:
        num = 1
    if id != -1:
        q = q & where("id") == id
    if author_ids != []:
        q = q & where("author_id").one_of(author_ids)
    if author_names != []:
        q = q & where("author_name").matches(
            r"(?=("+'|'.join(author_names)+r"))", flags=re.IGNORECASE)
    if title != "":
        q = q & where("title").search(title)
    if ai_type != -1:
        q = q & where("ai_type") == ai_type
    if tags != []:
        q = q & Query().tags.any(Query().translated_name.matches(r"(?=("+'|'.join(tags)+r"))",
                                                                 flags=re.IGNORECASE) or Query().name.matches(r"(?=("+'|'.join(tags)+r"))", flags=re.IGNORECASE))
    if local_file:
        q = q & where("local_filename").matches(r".+")
    results = db.search(q)
    if len(results) >= num:
        results = random.sample(results, num)
    return results


app = FastAPI()


@app.on_event("startup")
async def startup_event():
    global logger, db
    logger = logging.getLogger("uvicorn")
    db = TinyDB('db.json')
    read_config()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/api/v1")
def get_image_json(background_tasks: BackgroundTasks, r18: int = 0, num: int = 1, id: int = -1, author_ids: List[int] = [], author_names: List[str] = [], title: str = "", ai_type: int = -1, tags: List[str] = []):
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
def get_image(background_tasks: BackgroundTasks, r18: int = 0, id: int = -1, author_ids: List[int] = [], author_names: List[str] = [], title: str = "", ai_type: int = -1, tags: List[str] = []):
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
