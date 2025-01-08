import ssl

from requests import Session
from requests.adapters import HTTPAdapter


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
