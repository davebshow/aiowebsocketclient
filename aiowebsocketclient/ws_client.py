import asyncio
import io
from collections import defaultdict
from itertools import chain
from urllib.parse import urlparse


import aiohttp
from aiohttp import websocket_client

from aiowebsocketclient.client import ClientSession


class ClientWebSocketResponse(websocket_client.ClientWebSocketResponse):

    def __init__(self, reader, writer, protocol,
                 response, timeout, autoclose, autoping, loop,
                 ws_client_session, key):
        super().__init__(reader, writer, protocol, response, timeout,
                         autoclose, autoping, loop)

        self._key = key
        self._ws_client_session = ws_client_session

    def __repr__(self):
        out = io.StringIO()
        print('<ClientWebSocketResponse({}:{})>'.format(
            self._key[0], self._key[1]), file=out)
        return out.getvalue()

    @asyncio.coroutine
    def release(self):
        if self._ws_client_session is not None:
            yield from self._ws_client_session._release(self._key, self)

    @asyncio.coroutine
    def close(self):
        if self._ws_client_session is not None:
            yield from self._ws_client_session._release(
                self._key, self, should_close=True)
        else:
            yield from self._close()

    @asyncio.coroutine
    def _close(self):
        yield from super().close()


class WebSocketClientSession(object):
    """Manages socket pooling for multiple websocket connections.
    Based on aiohttp.ClientSession and aiohttp.BaseConnector.

    :param conn_timeout: (optional) Connect timeout.
    :param keepalive_timeout: (optional) Keep-alive timeout.
    :param bool force_close: Set to True to force close and do reconnect
        after each request.
    :param loop: Optional event loop.
    """

    def __init__(self, *, conn_timeout=None, force_close=False, limit=None,
                 client_session=None, loop=None,
                 ws_response_class=ClientWebSocketResponse):
        if loop is None:
            loop = asyncio.get_event_loop()
        self._closed = False
        if loop.get_debug():
            self._source_traceback = traceback.extract_stack(sys._getframe(1))
        self._conns = {}
        self._acquired = defaultdict(list)
        self._conn_timeout = conn_timeout
        self._force_close = force_close
        self._limit = limit
        self._waiters = defaultdict(list)
        self._loop = loop
        self._ws_response_class = ws_response_class
        if client_session is None:
            client_session = ClientSession(
                loop=self._loop, ws_response_class=self._ws_response_class)
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

        if self._limit is not None:
            while len(self._acquired[key]) >= self._limit:
                fut = asyncio.Future(loop=self._loop)
                self._waiters[key].append(fut)
                yield from fut

        websocket = self._get(key)
        if websocket is None:
            try:
                if self._conn_timeout:
                    websocket = yield from asyncio.wait_for(
                        self._create_connection(
                            url, protocols, timeout, autoclose, autoping, self,
                            key),
                        self._conn_timeout, loop=self._loop)
                else:
                    websocket = yield from self._create_connection(
                        url, protocols, timeout, autoclose, autoping, self,
                        key)

            except asyncio.TimeoutError as exc:
                raise aiohttp.ClientTimeoutError(
                    'Connection timeout to host %s:%s ssl:%s' % key) from exc

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
        except ValueError:  # pragma: no cover
            pass
        else:
            if self._limit is not None and len(acquired) < self._limit:
                waiters = self._waiters[key]
                while waiters:
                    waiter = waiters.pop(0)
                    if not waiter.done():
                        waiter.set_result(None)
                        break

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
                           ws_client_session, key):
        resp = yield from self._client_session.ws_connect(
            url,
            protocols=protocols,
            timeout=timeout,
            autoclose=autoclose,
            autoping=autoping,
            ws_client_session=ws_client_session,
            key=key)
        return resp

    def detach(self):
        """Detach client session from websocketsession without closing
        the former.
        """
        self._client_session = None
