#!/usr/bin/env python

import os
import time
import json
import re
import requests
import configupdater

from argparse import ArgumentParser
from base64 import urlsafe_b64encode
from hashlib import sha256
from pprint import pprint
from secrets import token_urlsafe
from sys import exit
from urllib.parse import urlencode
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# Get login credentials
global_username = ""
global_password = ""

config = configupdater.ConfigUpdater()
if not os.path.exists('config.ini'):
    # Create config file
    with open('config.ini', 'w'):
        pass
config.read('config.ini')
if (not config.has_section("Auth")):
    config.add_section("Auth")
if (config.has_option("Auth", "pixiv_username") and config.has_option("Auth", "pixiv_password")):
    global_username = config["Auth"]["pixiv_username"].value
    global_password = config["Auth"]["pixiv_password"].value
with open('config.ini', 'w') as configfile:
    config.write(configfile)

# Latest app version can be found using GET /v1/application-info/android
USER_AGENT = "PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)"
REDIRECT_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"
REQUESTS_KWARGS = {
    # 'proxies': {
    #     'https': 'http://127.0.0.1:1087',
    # },
    # 'verify': False
}

global_refresh_token = ""
global_expires_in = -1


def s256(data):
    """S256 transformation method."""

    return urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")


def oauth_pkce(transform):
    """Proof Key for Code Exchange by OAuth Public Clients (RFC7636)."""

    code_verifier = token_urlsafe(32)
    code_challenge = transform(code_verifier.encode("ascii"))

    return code_verifier, code_challenge


def print_auth_token_response(response):
    global global_refresh_token, global_expires_in
    data = response.json()

    try:
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
    except KeyError:
        print("error:")
        pprint(data)
        exit(1)

    expires_in = data.get("expires_in", 0)
    print("access_token:", access_token)
    print("refresh_token:", refresh_token)
    print("expires_in:", expires_in)
    global_refresh_token = refresh_token
    global_expires_in = expires_in


def get_webdriver(headless=False):
    caps = DesiredCapabilities.CHROME.copy()
    caps["goog:loggingPrefs"] = {
        "performance": "ALL"}  # enable performance logs
    options = webdriver.ChromeOptions()
    options.add_experimental_option(
        "excludeSwitches", ['enable-automation', 'enable-logging'])
    # if username and password are specified, run in headless mode
    if (headless):
        options.add_argument("--headless")
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(
        service=service, options=options, desired_capabilities=caps)
    return driver


def login(captcha=False):
    global global_username, global_password
    driver = get_webdriver(not captcha)
    code_verifier, code_challenge = oauth_pkce(s256)
    login_params = {
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "client": "pixiv-android",
    }
    print("[INFO] Gen code_verifier:", code_verifier)

    driver.get(f"{LOGIN_URL}?{urlencode(login_params)}")

    # logging in with username and password (if there is one in the config file, otherwise wait for user input)
    if (global_username == "" and global_password == ""):
        global_username = input("pixiv_username: ")
        global_password = input("pixiv_password: ")
    if (global_username != "" and global_password != ""):
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "degQSE")))
        element.click()
        time.sleep(1)
        element.send_keys(global_username)
        time.sleep(1)
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "hfoSmp")))
        element.click()
        time.sleep(1)
        element.send_keys(global_password)
        time.sleep(1)
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "fguACh")))
        element.click()
    else:
        print("no username and password specified, please login manually in the browser window")
    while True:
        # wait for login
        if driver.current_url[:40] == "https://accounts.pixiv.net/post-redirect":
            break
        if captcha == False and driver.find_elements(By.CLASS_NAME, 'dKhCxY'):
            print("captcha detected, opening a new visible browser window")
            driver.quit()
            return login(captcha=True)
        if captcha:
            print("please reolve the captcha manually in the browser window")
            captcha = False
        time.sleep(1)

    # filter code url from performance logs
    code = None
    for row in driver.get_log('performance'):
        data = json.loads(row.get("message", {}))
        message = data.get("message", {})
        if message.get("method") == "Network.requestWillBeSent":
            url = message.get("params", {}).get("documentURL")
            if url[:8] == "pixiv://":
                code = re.search(r'code=([^&]*)', url).groups()[0]
                break

    driver.close()

    print("[INFO] Get code:", code)

    response = requests.post(
        AUTH_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "include_policy": "true",
            "redirect_uri": REDIRECT_URI,
        },
        headers={
            "user-agent": USER_AGENT,
            "app-os-version": "14.6",
            "app-os": "ios",
        },
        **REQUESTS_KWARGS
    )

    print_auth_token_response(response)


def refresh(refresh_token):
    response = requests.post(
        AUTH_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "include_policy": "true",
            "refresh_token": refresh_token,
        },
        headers={
            "user-agent": USER_AGENT,
            "app-os-version": "14.6",
            "app-os": "ios",
        },
        **REQUESTS_KWARGS
    )
    print_auth_token_response(response)


def get_refresh_token():
    global global_refresh_token, global_expires_in, global_username, global_password
    refresh_token = ""
    token_expired = False

    config = configupdater.ConfigUpdater()
    config.read("config.ini")
    if (not config.has_section("Auth")):
        config.add_section("Auth")

    if (config.has_option("Auth", "refresh_token")):
        refresh_token = config["Auth"]["refresh_token"].value
        if (not (config["Auth"]["refresh_token"].value != "" and config.has_option("Auth", "expires_in") and config.has_option("Auth", "last_update_timestamp")) or ((time.time() - float(config["Auth"]["last_update_timestamp"].value)) >= float(config["Auth"]["expires_in"].value))):
            token_expired = True

    if not token_expired and refresh_token != "":
        global_refresh_token = refresh_token
        global_expires_in = config["Auth"]["expires_in"].value
        print("token not expired")
    else:
        if refresh_token == "":
            login()
        else:
            refresh(refresh_token)

    while global_refresh_token == "":
        time.sleep(1)

    last_update_timestamp = -1
    if token_expired or refresh_token == "":
        if (global_username != "" and global_password != ""):
            last_update_timestamp = time.time()
    else:
        last_update_timestamp = float(
            config["Auth"]["last_update_timestamp"].value)
    config.set("Auth", "pixiv_username", global_username)
    config.set("Auth", "pixiv_password", global_password)
    config.set("Auth", "refresh_token", global_refresh_token)
    config.set("Auth", "expires_in", str(global_expires_in))
    config.set("Auth", "last_update_timestamp", str(last_update_timestamp))
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    return global_refresh_token


def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    parser.set_defaults(func=lambda _: parser.print_usage())
    login_parser = subparsers.add_parser("login")
    login_parser.set_defaults(func=lambda _: login())
    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("refresh_token")
    refresh_parser.set_defaults(func=lambda ns: refresh(ns.refresh_token))
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
