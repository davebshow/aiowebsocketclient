aiowebsocketclient
==================

`On Github`_


.. _On Github: https://github.com/davebshow/aiowebsocketclient

WebSocketClientSession
----------------------

This class is based on aiohttp.ClientSession and aiohttp.BaseConnector classes.

It allows you to use pooling with simulataneous websocket connections across
various endpoints. Encapsulates the :class: `aiohttp.client.ClientSession`.
THIS DOCUMENTATION BORROWS PARAM DESCRIPTIONS FROM aiohttp.

Usage example::

     >>> import asyncio
     >>> from aiowebsocketclient import WebSocketClientSession
     >>> ws_session = WebSocketClientSession()
     >>> ws1 = yield from ws_session.ws_connect('http://127.0.0.1:58793/')
     >>> ws2 = yield from ws_session.ws_connect('http://127.0.0.1:33270')
     >>> ws3 = yield from ws_session.ws_connect('http://127.0.0.1:33270')
     >>> print("{}{}{}".format(ws1, ws2, ws3))
     <ClientWebSocketResponse(127.0.0.1:58793)>
     <ClientWebSocketResponse(127.0.0.1:33270)>
     <ClientWebSocketResponse(127.0.0.1:33270)>
     >>> yield from asyncio.gather(*[ws1.release(), ws2.release(),
     ...                             ws3.release()])
     >>> ws4 = yield from ws_session.ws_connect('http://127.0.0.1:58793/')
     >>> assert ws1 == ws4
     >>> yield from ws_session.close()  # Close all connections.


.. class:: WebSocketClientSession(*, conn_timeout=None, force_close=False,
                                  limit=None, headers=None,
                                  client_session=None, loop=None,
                                  ws_response_class=ClientWebSocketResponse)

   The class for creating client sessions and making requests. Returns a
   :class:`ClientWebSocketResponse` object. This object is nearly identical to
   :class:`aiohttp.websocket_clientClientWebSocketResponse`, except it adds a
   method ``release`` to release unused connections to the session pool.

   :param float conn_timeout: timeout for establishing connection
                              (optional). Values ``0`` or ``None``
                              mean no timeout

   :param bool force_close: close underlying sockets after
                            releasing connection

   :param int limit: limit for simultaneous connections to the same
                     endpoint.  Endpoints are the same if they are
                     have equal ``(host, port, is_ssl)`` triple.
                     If *limit* is ``None`` the client has no limit

   :param aiohttp.client.ClientSession: Underlying HTTP session used to
                                        to establish websocket connections

   :param loop: `event loop`
      used for processing HTTP requests.
      If param is ``None``, `asyncio.get_event_loop`
      is used for getting default event loop.
      (optional)

   :param ws_response_class: WebSocketResponse class implementation.
                             ``ClientWebSocketResponse`` by default
