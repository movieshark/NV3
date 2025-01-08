import re
from json import JSONDecodeError, dumps, loads
from sys import argv
from urllib.parse import parse_qsl, urlencode, urljoin

import inputstreamhelper
import tls_handler
import web_service
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

session = tls_handler.create_custom_session()

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 GLS/100.10.9939.100"
addon = xbmcaddon.Addon()
cert_path = xbmcvfs.translatePath(
    addon.getAddonInfo("path") + "resources/assets/nvpn_nvt_gov_hu.pem"
)


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
    data = {
        "method": "OpenLDAP",
        "uname": username,
        "pwd": password,
        "pwd1": "",
        "pwd2": "",
    }
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Cookie": "user_locale=hu",
        "Origin": "https://nvpn.nvt.gov.hu",
        "Pragma": "no-cache",
        "Referer": "https://nvpn.nvt.gov.hu/prx/000/http/localhost/login/index.html",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": user_agent,
    }
    response = session.post(
        "https://nvpn.nvt.gov.hu/prx/000/http/localhost/login",
        headers=headers,
        data=data,
        allow_redirects=False,
        verify=cert_path,
    )
    if response.status_code == 302:
        response_status = session.get(
            "https://nvpn.nvt.gov.hu/prx/000/http/localhost/an_login.js",
            headers=headers,
            verify=cert_path,
        )
        error_message = re.search(
            r"""var _AN_str_errormsg_login = "(.*?)";""", response_status.text
        )
        if error_message and error_message.group(1):
            dialog = xbmcgui.Dialog()
            dialog.ok("Hiba", error_message.group(1))
            addon.openSettings()
            exit()
        else:
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
    r = session.get(
        "https://nvpn.nvt.gov.hu/prx/000/https/player.mediaklikk.hu/playernew/player.php",
        params=params,
        cookies=cookies,
        headers={
            "User-Agent": user_agent,
            "Referer": "https://nvpn.nvt.gov.hu/prx/000/https/mediaklikk.hu",
        },
        allow_redirects=False,
        verify=cert_path,
    )
    if r.status_code in [301, 302]:
        login()
        cookies = loads(addon.getSetting("cookies"))
        r = session.get(
            "https://nvpn.nvt.gov.hu/prx/000/https/player.mediaklikk.hu/playernew/player.php",
            params=params,
            cookies=cookies,
            headers={
                "User-Agent": user_agent,
                "Referer": "https://nvpn.nvt.gov.hu/prx/000/https/mediaklikk.hu",
            },
            allow_redirects=False,
            verify=cert_path,
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
        url = urljoin("https://nvpn.nvt.gov.hu", url)
        headers = {
            "User-Agent": user_agent,
            "Referer": "https://nvpn.nvt.gov.hu/prx/000/https/mediaklikk.hu",
            "Cookie": "; ".join([f"{k}={v}" for k, v in cookies.items()]),
        }
        kodi_version = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
        is_proxy = False
        if (
            kodi_version < 20
            or not xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)")
            or ("index.m3u8" in url and not addon.getSettingBool("useisa"))
        ):
            # Kodi 19.5 on Windows didn't trust the certificate otherwise
            headers["verifypeer"] = "false"
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
                        "Referer": "https://nvpn.nvt.gov.hu/prx/000/https/mediaklikk.hu",
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
            "Nem található támogatott stream.[CR]Ha nincs fent az [I]inputstream.adaptive[/I] kiegészítő, a telepítése segíthet több stream elérésében.",
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
