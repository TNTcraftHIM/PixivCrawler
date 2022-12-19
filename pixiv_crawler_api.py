import os
import time
import configupdater
import pixiv_crawler

from typing import Optional
from fastapi import FastAPI, BackgroundTasks
from tinydb import TinyDB, where


def read_config():
    config = configupdater.ConfigUpdater()
    if not os.path.exists('config.ini'):
        # Create config file
        with open('config.ini', 'w'):
            pass
    config.read('config.ini')
    if not config.has_section("API"):
        config.add_section("API")
        pixiv_crawler.crawl_images()
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    print("API config loaded")


read_config()
app = FastAPI()


@app.get("/")
def read_root(background_tasks: BackgroundTasks):
    background_tasks.add_task(pixiv_crawler.crawl_images)
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Optional[str] = None):
    return {"item_id": item_id, "q": q}

# reload config for crawler and api


@app.get("/reload")
def reload():
    read_config()
    pixiv_crawler.read_config()
    return {"reload": "success"}
