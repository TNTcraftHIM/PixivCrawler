import os
import re
import unicodedata

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


api = AppPixivAPI()
refreshtoken = get_refresh_token()
api.auth(refresh_token=refreshtoken)

# get origin url
# json_result = api.illust_detail(59580629)
# illust = json_result.illust
# print(">>> origin url: %s" % illust.image_urls['large'])

# check if download folder exists
if not os.path.exists('downloads'):
    os.makedirs('downloads')

# # get ranking: 1-30
# # mode: [day, week, month, day_male, day_female, week_original, week_rookie, day_manga]
# json_result = api.illust_ranking('day_r18')
# # check if page folder exists
# if not os.path.exists('downloads' + os.sep + 'p1'):
#     os.makedirs('downloads' + os.sep + 'p1')
# for illust in json_result.illusts:
#     title = illust.title
#     url = illust.image_urls.large
#     print(" p1 [%s] %s" % (title, url.replace("i.pximg.net", "i.pixiv.re")))
#     api.download(url, path='downloads',
#                  name=slugify(illust.title, True))

# get all pages:
next_qs = {"mode": "day_r18"}
while next_qs:
    json_result = api.illust_ranking(**next_qs)
    for illust in json_result.illusts:
        prefix = str(illust.id) + "_" + illust.user.name + "_"
        title = illust.title
        url = illust.image_urls.large
        extension = "." + url.split(".")[-1]
        print("[%s] %s" % (title, url.replace("i.pximg.net", "i.pixiv.re")))
        api.download(url, path="downloads", prefix=slugify(prefix, True),
                     name=slugify(title, True) + extension)
    next_qs = api.parse_qs(json_result.next_url)
