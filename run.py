import os
import logging
import uvicorn
import configupdater


def read_config():
    global host, port
    # read config file
    config = configupdater.ConfigUpdater()
    if not os.path.exists('config.ini'):
        # Create config file
        with open('config.ini', 'w'):
            pass
    config.read('config.ini')
    if not config.has_section("PixivCrawler"):
        config.add_section("PixivCrawler")
    if config.has_option("PixivCrawler", "host"):
        host = config["PixivCrawler"]["host"].value
    else:
        host = "0.0.0.0"
        logger.warning("host invalid, using default: " + host)
    config.set("PixivCrawler", "host", host)
    if config.has_option("PixivCrawler", "port"):
        port = int(config["PixivCrawler"]["port"].value)
    else:
        port = 8000
        logger.warning("port invalid, using default: " + str(port))
    config.set("PixivCrawler", "port", port)

    # save config
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    logger.info("PixivCrawler config loaded")


def log_filter(record):
    record.levelprefix = record.levelname + ":"
    return True


if __name__ == "__main__":
    global logger
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    log_config["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    log_config["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    logger = logging.getLogger("uvicorn")
    logger.addHandler(logging.StreamHandler())
    logger.handlers[0].setFormatter(logging.Formatter(
        "%(asctime)s %(levelprefix)-9s %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addFilter(log_filter)
    logger.setLevel(logging.INFO)
    print("-----Starting PixivCrawler API-----")
    read_config()
    uvicorn.run("pixiv_crawler_api:app", host=host,
                port=port, reload=True, log_config=log_config)
