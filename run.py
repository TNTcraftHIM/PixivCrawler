import os
import sys
import uvicorn
import logging
import configupdater

from uvicorn import Config, Server
from loguru import logger

LOG_LEVEL = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO"))


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
        config.append("\n")
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


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage())


def setup_logging():
    # intercept everything at the root logger
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(LOG_LEVEL)

    # remove every other logger's handlers
    # and propagate to root logger
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    # configure loguru
    logger.configure(handlers=[{"sink": sys.stdout,
                     "format": "<green>{time:YYYY-MM-dd HH:mm:ss}</> | <yellow>{level: <8}</> | {message}", "colorize": True}])


if __name__ == "__main__":
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"][
        "fmt"] = "\x1b[0;32m%(asctime)s\u001b[0m | \u001b[33m%(levelname)-8s\u001b[0m | %(message)s"
    log_config["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    log_config["formatters"]["default"][
        "fmt"] = "\x1b[0;32m%(asctime)s\u001b[0m | \u001b[33m%(levelname)-8s\u001b[0m | %(message)s"
    log_config["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    setup_logging()
    print("---Starting PixivCrawler API---")
    read_config()
    server = Server(
        Config(
            "pixiv_crawler_api:app",
            host=host,
            port=port,
            log_level=3,
            log_config=log_config,
        ),
    )
    setup_logging()
    server.run()
