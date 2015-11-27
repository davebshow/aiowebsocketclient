import asyncio
import io
import sys
import traceback
from collections import defaultdict
from itertools import chain
from urllib.parse import urlparse


import aiohttp
from aiohttp import websocket_client


class ClientWebSocketResponse(websocket_client.ClientWebSocketResponse):

    def __init__(self, reader, writer, protocol,
                 response, timeout, autoclose, autoping, loop):
        super().__init__(reader, writer, protocol, response, timeout,
                         autoclose, autoping, loop)
        self._key = (None, None, None)
        self._ws_connector = None

    def __repr__(self):
        out = io.StringIO()
        print('<ClientWebSocketResponse({}:{}, ssl:{})>'.format(
              self._key[0], self._key[1], self._key[2]), file=out)
        return out.getvalue()

    @asyncio.coroutine
    def release(self):
        if self._ws_connector is not None:
            yield from self._ws_connector._release(self._key, self)
        else:
            yield from self._close()

    @asyncio.coroutine
    def close(self):
        if self._ws_connector is not None:
            yield from self._ws_connector._release(
                self._key, self, should_close=True)
        else:
            yield from self._close()

    @asyncio.coroutine
    def _close(self):
        yield from super().close()


class WebSocketConnector:

    def __init__(self, *, conn_timeout=None, force_close=False, limit=1024,
                 client_session=None, loop=None,
                 ws_response_class=ClientWebSocketResponse):
        """Manages socket pooling for multiple websocket connections.

        Based on aiohttp.ClientSession and aiohttp.BaseConnector.

        :param float conn_timeout: timeout for establishing connection
                                   (optional). Values ``0`` or ``None``
                                   mean no timeout (in seconds)

        :param bool force_close: close underlying sockets after
                                 releasing connection

        :param int limit: limit for simultaneous connections to the same
                          endpoint.  Endpoints are the same if they are
                          have equal ``(host, port, is_ssl)`` triple.
                          Default is 1024

        :param aiohttp.client.ClientSession: Underlying HTTP session used to
                                             to establish websocket connections

        :param loop: `event loop`
                     used for processing HTTP requests.
                     If param is ``None``, `asyncio.get_event_loop`
                     is used for getting default event loop.
                     (optional)

        :param ws_response_class: WebSocketResponse class implementation.
                                  ``ClientWebSocketResponse`` by default

        """
        if loop is None:
            loop = asyncio.get_event_loop()
        self._closed = False
        if loop.get_debug():
            self._source_traceback = traceback.extract_stack(sys._getframe(1))
        self._conns = {}
        self._acquired = defaultdict(list)
        self._conn_timeout = conn_timeout
        self._force_close = force_close
        self._waiters = defaultdict(list)
        self._loop = loop
        self._limit = limit
        self._semaphore = asyncio.Semaphore(value=self._limit, loop=self._loop)
        if client_session is None:
            connector = aiohttp.TCPConnector(
                loop=self._loop, conn_timeout=conn_timeout)
            client_session = aiohttp.ClientSession(
                loop=self._loop, ws_response_class=ws_response_class,
                connector=connector)
        self._client_session = client_session

    @property
    def force_close(self):
        """Ultimately close connection on releasing if True."""
        return self._force_close

    @property
    def limit(self):
        """The limit for simultaneous connections to the same endpoint.
        Endpoints are the same if they are have equal
        (host, port, is_ssl) triple.
        If limit is None the connector has no limit (default).
        """
        return self._limit

    @asyncio.coroutine
    def close(self):
        """Close all opened websockets and underlying client session."""
        if self._closed:
            return
        self._closed = True
        try:
            if hasattr(self._loop, 'is_closed'):
                if self._loop.is_closed():
                    return
            for key, data in self._conns.items():
                for websocket in data:
                    yield from websocket._close()
            for websocket in chain(*self._acquired.values()):
                yield from websocket._close()
        finally:
            if self._client_session is not None:
                self._client_session.close()
                self._client_session = None
            self._conns.clear()
            self._acquired.clear()

    @property
    def closed(self):
        """Is client closed.
        A readonly property.
        """
        return self._closed

    @property
    def client_session(self):
        return self._client_session

    @asyncio.coroutine
    def ws_connect(self, url, *,
                   protocols=(),
                   timeout=10.0,
                   autoclose=True,
                   autoping=True):
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
        scheme = parsed.scheme
        ssl = scheme in ["https", "wss"]
        key = (host, port, ssl)

        yield from self._semaphore.acquire()

        websocket = self._get(key)
        if websocket is None:
            websocket = yield from self._create_connection(
                url, protocols, timeout, autoclose, autoping, key)

        self._acquired[key].append(websocket)
        return websocket

    def _get(self, key):
        conns = self._conns.get(key)
        while conns:
            websocket = conns.pop()
            if websocket.closed:
                websocket = None
            else:
                return websocket
        return None

    @asyncio.coroutine
    def _release(self, key, websocket, *, should_close=False):
        if self._closed:
            return
        acquired = self._acquired[key]
        try:
            acquired.remove(websocket)
        except ValueError:
            pass
        else:
            self._semaphore.release()

        if self._force_close:
            should_close = True

        if should_close:
            yield from websocket._close()
        else:
            conns = self._conns.get(key)
            if conns is None:
                conns = self._conns[key] = []
            conns.append(websocket)

    @asyncio.coroutine
    def _create_connection(self, url, protocols, timeout, autoclose, autoping,
                           key):
        resp = yield from self._client_session.ws_connect(
            url,
            protocols=protocols,
            timeout=timeout,
            autoclose=autoclose,
            autoping=autoping)
        resp._ws_connector = self
        resp._key = key
        return resp

    def detach(self):
        """Detach client session from websocketsession without closing
        the former.
        """
        self._client_session = None
