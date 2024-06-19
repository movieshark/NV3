import threading
from json import loads
from socketserver import ThreadingMixIn
from unicodedata import normalize
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import requests
import xbmc
import xbmcaddon
import xbmcvfs
from bottle import default_app, hook, request, response, route


class SilentWSGIRequestHandler(WSGIRequestHandler):
    """Custom WSGI Request Handler with logging disabled"""

    protocol_version = "HTTP/1.1"

    def log_message(self, *args, **kwargs):
        """Disable log messages"""
        pass


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    """Multi-threaded WSGI server"""

    allow_reuse_address = True
    daemon_threads = True
    timeout = 1


@hook("before_request")
def set_server_header():
    response.set_header("Server", request.app.config["name"])


@route("/")
def index():
    response.content_type = "text/plain"
    return request.app.config["welcome_text"]


@route("/proxy/<url:path>", method=["HEAD"])
def proxy_head(url):
    headers_raw = request.headers.get("h")
    headers = loads(headers_raw) if headers_raw else {}

    if not url:
        return "No URL provided"

    try:
        resp = requests.head(
            url, verify=request.app.config.get("cert_path"), headers=headers
        )
        response.set_header("Content-Type", resp.headers.get("Content-Type"))
        return ""

    except requests.RequestException as e:
        return f"Error: {e}"

    except Exception as e:
        return f"Error: {e}"

    finally:
        if "resp" in locals():
            resp.close()


@route("/proxy/<url:path>", method=["GET"])
def proxy(url):
    headers_raw = request.headers.get("h")
    headers = loads(headers_raw) if headers_raw else {}

    if not url:
        return "No URL provided"
    query = request.query_string
    if query:
        url += f"?{query}"
    xbmc.log(f"Proxying: {url}", xbmc.LOGDEBUG)
    xbmc.log(f"Headers: {headers}", xbmc.LOGDEBUG)

    try:
        resp = requests.get(
            url,
            stream=True,
            headers=headers,
            verify=request.app.config.get("cert_path"),
        )
        if "Content-Type" in resp.headers:
            response.set_header("Content-Type", resp.headers.get("Content-Type"))
        if "Content-Disposition" in resp.headers:
            response.set_header(
                "Content-Disposition", resp.headers.get("Content-Disposition")
            )
        if "Content-Range" in resp.headers:
            response.set_header("Content-Range", resp.headers.get("Content-Range"))

        response.set_header("Connection", "keep-alive")
        response.set_header("Accept-Ranges", "bytes")
        response.set_header("Transfer-Encoding", "chunked")

        """If the remote doesn't send a Content-Length header, we either need to
        request the whole file at once, calculate Content-Length ourselves and send
        the file either in chunks or all at once. But if Content-Length isn't present,
        ISA won't be able to play the file.
        
        Apparently there is a workaround: https://github.com/xbmc/inputstream.adaptive/blob/b19e01120d628794ca08b65fb428b6d83422f10c/src/utils/CurlUtils.cpp#L291
        
        So the idea is to use Transfer-Encoding: chunked and send the file in chunks.
        In which case, ISA doesn't need to know the Content-Length in advance, it will stop
        reading the stream when it encounters the last (empty) chunk."""

        for chunk in resp.iter_content(chunk_size=None):
            data = bytes(f"{len(chunk):X}\r\n", "utf-8") + chunk + b"\r\n"
            yield data
        yield b"0\r\n\r\n"

    except requests.RequestException as e:
        return f"Error: {e}"

    except Exception as e:
        return f"Error: {e}"

    finally:
        if "resp" in locals():
            resp.close()
        response.close()


class WebServerThread(threading.Thread):
    def __init__(self, httpd: WSGIServer):
        threading.Thread.__init__(self)
        self.web_killed = threading.Event()
        self.httpd = httpd

    def run(self):
        while not self.web_killed.is_set():
            self.httpd.handle_request()

    def stop(self):
        self.web_killed.set()


def main_service(addon: xbmcaddon.Addon) -> WebServerThread:
    name = f"{addon.getAddonInfo('name')} v{addon.getAddonInfo('version')}"
    name = normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    handle = f"[{name}]"
    app = default_app()
    welcome_text = f"{name} Web Service"
    cert_path = xbmcvfs.translatePath(
        addon.getAddonInfo("path") + "resources/assets/nvt_gov_hu.pem"
    )
    app.config["name"] = name
    app.config["welcome_text"] = welcome_text
    app.config["cert_path"] = cert_path
    try:
        httpd = make_server(
            addon.getSetting("webaddress"),
            addon.getSettingInt("webport"),
            app,
            server_class=ThreadedWSGIServer,
            handler_class=SilentWSGIRequestHandler,
        )
    except OSError as e:
        if e.errno == 98:
            xbmc.log(
                f"{handle} Web service: port {addon.getSetting('webport')} already in use",
                xbmc.LOGERROR,
            )
            return
        raise
    xbmc.log(f"{handle} Web service starting", xbmc.LOGINFO)
    web_thread = WebServerThread(httpd)
    web_thread.start()
    return web_thread


if __name__ == "__main__":
    monitor = xbmc.Monitor()
    addon = xbmcaddon.Addon()
    web_thread = main_service(addon)

    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
    if web_thread and web_thread.is_alive():
        web_thread.stop()
        try:
            web_thread.join()
        except RuntimeError:
            pass
    xbmc.log(f"[{addon.getAddonInfo('name')}] Web service stopped", xbmc.LOGINFO)
