import re
from json import JSONDecodeError, dumps, loads
from sys import argv
from urllib.parse import parse_qsl, urlencode

import requests
import web_service
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from Cryptodome.Cipher import PKCS1_v1_5
from Cryptodome.PublicKey import RSA
import inputstreamhelper

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 GLS/100.10.9939.100"
addon = xbmcaddon.Addon()
cert_path = xbmcvfs.translatePath(
    addon.getAddonInfo("path") + "resources/assets/nvt_gov_hu.pem"
)


def encrypt_password(password, modulus, exponent):
    """Encrypts the password using the given RSA public key.

    Don't ask why the 0 byte at the end, seemingly the server
     accepts it, but the original code does it this way.

    Endianness swap is also necessary!
    """
    key = RSA.construct((int(modulus, 16), int(exponent, 16)))
    cipher = PKCS1_v1_5.new(key)
    ciphertext = cipher.encrypt(password.encode() + b"\x00")[::-1]
    return ciphertext.hex()


def login():
    """Handles the login process. Call, whenever you need to login."""
    username = addon.getSetting("username")
    password = addon.getSetting("password")
    if not username or not password:
        dialog = xbmcgui.Dialog()
        dialog.ok(
            "Hiba",
            "A kiegészítő használatához be kell állítani a felhasználónevet és a jelszót.",
        )
        addon.openSettings()
        exit()
    js_rsa = requests.get(
        "https://vpn.nvt.gov.hu/Login/JS_RSA.js",
        headers={"User-Agent": user_agent},
        verify=cert_path,
    ).text
    modulus = re.search(r"var modulus = '(.+?)';", js_rsa).group(1)
    exponent = re.search(r"var exponent = '(.+?)';", js_rsa).group(1)
    data = {
        "selectedRealm": "ssl_vpn",
        "loginType": "Standard",
        "userName": username,
        "pin": "",
        "password": encrypt_password(password, modulus, exponent),
        "HeightData": "",
    }
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Cookie": "CheckCookieSupport=1; CPCVPN_REQUESTED_URL=aHR0cHM6Ly92cG4ubnZ0Lmdvdi5odS9QVC9odHRwczovL200c3BvcnQuaHUv; CPCVPN_SELECTED_REALM=ssl_vpn",
        "Origin": "https://vpn.nvt.gov.hu",
        "Pragma": "no-cache",
        "Referer": "https://vpn.nvt.gov.hu/Login/Login",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": user_agent,
    }
    response = requests.post(
        "https://vpn.nvt.gov.hu/Login/Login",
        headers=headers,
        data=data,
        allow_redirects=False,
        verify=cert_path,
    )
    if response.status_code == 200:
        error_message = re.search(
            r'<div id="errorMsgDIV">\s*<span class="errorMessage">(.+?)</span>',
            response.text,
        )
        if error_message:
            dialog = xbmcgui.Dialog()
            dialog.ok("Hiba", error_message.group(1))
            addon.openSettings()
            exit()
    elif response.status_code in [301, 302]:
        cookies = dumps(response.cookies.get_dict(), separators=(",", ":"))
        addon.setSetting("cookies", str(cookies))
        dialog = xbmcgui.Dialog()
        dialog.notification(
            "Sikeres bejelentkezés",
            "Sikeresen bejelentkeztél a [I]VPN[/I] szolgáltatásba.",
            sound=False,
        )
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok(
            "Hiba",
            f"Ismeretlen hiba történt a bejelentkezés során, kód: {response.status_code}",
        )
        exit()


def main_menu():
    channels = [
        {
            "name": "M1",
            "handle": "mtv1live",
            "icon": "https://upload.wikimedia.org/wikipedia/en/thumb/a/ac/M1_logo_2012.png/896px-M1_logo_2012.png",
        },
        {
            "name": "M2",
            "handle": "mtv2live",
            "icon": "https://upload.wikimedia.org/wikipedia/commons/b/b5/M2_gyerekcsatorna_log%C3%B3ja.png",
        },
        {
            "name": "M4 Sport",
            "handle": "mtv4live",
            "icon": "https://upload.wikimedia.org/wikipedia/hu/thumb/f/fd/M4_logo.png/200px-M4_logo.png",
        },
        {
            "name": "M4 Sport+",
            "handle": "mtv4plus",
            "icon": "https://upload.wikimedia.org/wikipedia/commons/5/5b/M4_Sport%2B_logo.png",
        },  # not part of the offering, but seems to work
        {
            "name": "M5",
            "handle": "mtv5live",
            "icon": "https://upload.wikimedia.org/wikipedia/commons/b/b4/M5logo.png",
        },
        {
            "name": "Duna",
            "handle": "dunalive",
            "icon": "https://upload.wikimedia.org/wikipedia/en/2/24/Duna_logo_2012.png",
        },
        {
            "name": "Duna World",
            "handle": "dunaworldlive",
            "icon": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Duna_World_HD_2012.svg/1200px-Duna_World_HD_2012.svg.png",
        },
    ]
    for channel in channels:
        list_item = xbmcgui.ListItem(label=channel["name"])
        list_item.setArt({"icon": channel["icon"]})
        list_item.setProperty("IsPlayable", "true")
        url = f"{argv[0]}?action=play&handle={channel['handle']}&ext=.m3u8"
        xbmcplugin.addDirectoryItem(
            handle=int(argv[1]), url=url, listitem=list_item, isFolder=False
        )
    xbmcplugin.setContent(int(argv[1]), "videos")
    xbmcplugin.endOfDirectory(int(argv[1]))


def play(channel):
    """Plays the selected channel using either the inputstream.adaptive or the built-in player.

    Playlist extraction is a hack as the HTML source has a JS object with JS functions. Couldn't
     completely parse it with regex, so I had to add a closing bracket and brace to make it a valid JSON.
     Might break in the future.

    ISA cannot handle bad certificates so we use a proxy service to bypass it. The service is started
     whenever a playback starts on a thread and is stopped when the playback stops.
    """
    cookies = loads(addon.getSetting("cookies"))
    params = {"noflash": "yes", "video": channel}
    r = requests.get(
        "https://vpn.nvt.gov.hu/PT/https://player.mediaklikk.hu/playernew/player.php",
        params=params,
        cookies=cookies,
        headers={
            "User-Agent": user_agent,
            "Referer": "https://vpn.nvt.gov.hu/PT/https://mediaklikk.hu",
        },
        verify=cert_path,
        allow_redirects=False,
    )
    if r.status_code in [301, 302]:
        login()
        cookies = loads(addon.getSetting("cookies"))
        r = requests.get(
            "https://vpn.nvt.gov.hu/PT/https://player.mediaklikk.hu/playernew/player.php",
            params=params,
            cookies=cookies,
            headers={
                "User-Agent": user_agent,
                "Referer": "https://vpn.nvt.gov.hu/PT/https://mediaklikk.hu",
            },
            verify=cert_path,
            allow_redirects=False,
        )
    elif r.status_code != 200:
        dialog = xbmcgui.Dialog()
        dialog.ok(
            "Hiba",
            f"Ismeretlen hiba történt a lejátszás során, kód: {r.status_code}",
        )
        exit()
    playlist = re.search(r"""['"]playlist['"]\s*:\s*(\[[^\]]+\])""", r.text).group(1)
    try:
        playlist = loads(playlist)
    except JSONDecodeError:
        playlist = loads(playlist + "}}}]")
    url = None
    for item in playlist:
        if item["type"] == "hls" and "index.m3u8" in item["file"]:
            url = item["file"]
            break
        elif item["type"] == "dash" and "manifest.mpd" in item["file"]:
            url = item["file"]
            break
    if url:
        headers = {
            "User-Agent": user_agent,
            "Referer": "https://vpn.nvt.gov.hu/PT/https://mediaklikk.hu",
            "Cookie": "; ".join([f"{k}={v}" for k, v in cookies.items()]),
        }
        kodi_version = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
        is_proxy = False
        if (
            kodi_version < 20
            or not xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)")
            or ("index.m3u8" in url and not addon.getSettingBool("useisa"))
        ):
            url += "|" + urlencode(headers)
        else:
            headers = {
                "h": dumps(headers),
            }
            url = f"http://{addon.getSetting('webaddress')}:{addon.getSetting('webport')}/proxy/{url}"
            is_proxy = True
        list_item = xbmcgui.ListItem(path=url)
        if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)") and (
            "index.m3u8" in url and addon.getSettingBool("useisa")
        ):
            list_item.setProperty("inputstream", "inputstream.adaptive")
            if kodi_version < 20 and "index.m3u8" in url:
                list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
            elif kodi_version < 20 and "manifest.mpd" in url:
                list_item.setProperty("inputstream.adaptive.manifest_type", "mpd")
            widevine_custom_data = (
                item.get("drm", {}).get("widevine", {}).get("customData")
            )
            if kodi_version >= 19:
                list_item.setProperty(
                    "inputstream.adaptive.manifest_headers", urlencode(headers)
                )
                list_item.setProperty(
                    "inputstream.adaptive.stream_headers", urlencode(headers)
                )
            if "manifest.mpd" in url and widevine_custom_data:
                is_helper = inputstreamhelper.Helper("mpd", "com.widevine.alpha")
                if is_helper.check_inputstream():
                    list_item.setProperty(
                        "inputstream.adaptive.license_type", "com.widevine.alpha"
                    )
                    license_headers = {
                        "User-Agent": user_agent,
                        "Referer": "https://vpn.nvt.gov.hu/PT/https://mediaklikk.hu",
                        "Content-Type": "",
                        "customdata": widevine_custom_data,
                    }
                    list_item.setProperty(
                        "inputstream.adaptive.license_key",
                        f"https://wv-keyos.licensekeyserver.com/|{urlencode(license_headers)}|R{{SSM}}|",
                    )
                else:
                    dialog = xbmcgui.Dialog()
                    dialog.ok(
                        "Hiba",
                        "A Widevine támogatás hiányzik, ellenőrizd, hogy van-e aktív CDM az Inputstream Helper beállításokban.",
                    )
                    exit()
        if is_proxy:
            service = web_service.main_service(addon)
            monitor = xbmc.Monitor()
            player = xbmc.Player()
        xbmcplugin.setResolvedUrl(int(argv[1]), True, list_item)
        if is_proxy:
            timeout = 0
            while not player.isPlaying() and not monitor.abortRequested():
                if timeout > 8:
                    xbmc.log(
                        "Playback did not start in time, stopping the service",
                        xbmc.LOGINFO,
                    )
                    if service and service.is_alive():
                        service.stop()
                        try:
                            service.join()
                        except RuntimeError:
                            pass
                        return
                timeout += 1
                monitor.waitForAbort(1)
            while not monitor.abortRequested() and player.isPlaying():
                if monitor.waitForAbort(1):
                    break
            if service and service.is_alive():
                service.stop()
                try:
                    service.join()
                except RuntimeError:
                    pass
                xbmc.log(
                    f"[{addon.getAddonInfo('name')}] Web service stopped", xbmc.LOGINFO
                )
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok(
            "Hiba",
            "Nem található nem támogatott stream.[CR]Ha nincs fent az [I]inputstream.adaptive[/I] kiegészítő, a telepítése segíthet több stream elérésében.",
        )
        exit()


if __name__ == "__main__":
    params = dict(parse_qsl(argv[2].replace("?", "")))
    action = params.get("action")

    if action is None:
        main_menu()
    elif action == "play":
        if not addon.getSetting("cookies"):
            login()
        play(params.get("handle"))
