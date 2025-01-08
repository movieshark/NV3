import ssl

from requests import Session
from requests.adapters import HTTPAdapter


"""
Disclaimer:

Frankly, this workaround shouldn't exist...
But the server only supports AES128-SHA ciphers, which is not supported by the default SSL context on the latest Python versions.
So we have to create a custom SSL context with the required ciphers.

SHA-1 is highly discouraged, but as long as the server doesn't support any other cipher, we have no choice but to use it.
Your browser would use the same, so it's not less secure than using the site in a browser.
"""


class SSLAdapter(HTTPAdapter):
    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)


def create_custom_session() -> Session:
    ssl_context = ssl.create_default_context()
    ssl_context.set_ciphers("AES128-SHA")

    session = Session()
    session.mount("https://", SSLAdapter(ssl_context=ssl_context))
    return session
