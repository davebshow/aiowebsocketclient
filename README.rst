aiowebsocketclient
==================

WebSocketClientSession
----------------------

This class is based on aiohttp.ClientSession and aiohttp.BaseConnector classes.

It allows you to use pooling with simulataneous websocket connections across
various endpoints. Encapsulates the aiohttp.ClientSession and
aiohttp.TCPConnector classes. THIS DOCUMENTATION BORROWS PARAM DESCRIPTIONS
FROM aiohttp.

Usage example::

     >>> from aiowebsocketclient import WebSocketClientSession
     >>> ws_session = WebSocketClientSession()
     >>> conn1 = yield from ws_session.ws_connect('http://127.0.0.1:58241/')
     >>> conn2 = yield from ws_session.ws_connect('http://127.0.0.1:58241/')
     >>> conn3 = yield from ws_session.ws_connect('http://127.0.0.1:50526/')
     >>> conn1.send_str("hello")
     >>> conn2.send_str("world")
     >>> conn3.send_str("hello world")
     >>> msg = yield from conn1.receive()



.. class:: WebSocketClientSession(*, conn_timeout=None, force_close=False,
                                  limit=None, connector=None, headers=None,
                                  client_session=None, loop=None, auth=auth,
                                  ws_response_class=ClientWebSocketResponse)

   The class for creating client sessions and making requests.

   :param float conn_timeout: timeout for connection establishing
                              (optional). Values ``0`` or ``None``
                              mean no timeout.

   :param bool force_close: close underlying sockets after
                            connection releasing.

   :param int limit: limit for simultaneous connections to the same
                     endpoint.  Endpoints are the same if they are
                     have equal ``(host, port, is_ssl)`` triple.
                     If *limit* is ``None`` the client has no limit.

   :param aiohttp.connector.BaseConnector connector: BaseConnector
                            sub-class instance to support connection pooling.

   :param aiohttp.client.ClientSession: Underlying HTTP session used to
                                        to establish websocket connections

   :param loop: `event loop`
      used for processing HTTP requests.
      If param is ``None``, `asyncio.get_event_loop`
      is used for getting default event loop, but we strongly
      recommend to use explicit loops everywhere.
      (optional)

   :param ws_response_class: WebSocketResponse class implementation.
                             ``ClientWebSocketResponse`` by default.
