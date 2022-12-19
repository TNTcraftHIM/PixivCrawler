import os
import uvicorn
import configupdater

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
    print("host invalid, using default: " + host)
config.set("PixivCrawler", "host", host)
if config.has_option("PixivCrawler", "port"):
    port = int(config["PixivCrawler"]["port"].value)
else:
    port = 8000
    print("port invalid, using default: " + str(port))
config.set("PixivCrawler", "port", port)

# save config
with open('config.ini', 'w') as configfile:
    config.write(configfile)


if __name__ == "__main__":
    uvicorn.run("pixiv_crawler_api:app", host=host, port=port, reload=True)
