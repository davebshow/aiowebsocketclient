# aiowebsocketclient 0.0.2


## WebSocketConnector

This class is based on aiohttp.ClientSession and aiohttp.BaseConnector classes.

It allows you to use pooling with simulataneous websocket connections across
various endpoints. Encapsulates the :class: `aiohttp.client.ClientSession`.
THIS DOCUMENTATION BORROWS PARAM DESCRIPTIONS FROM aiohttp.

```python
>>> import asyncio
>>> from aiowebsocketclient import WebSocketConnector
>>> ws_session = WebSocketConnector()
>>> ws1 = yield from ws_session.ws_connect('http://127.0.0.1:58793/')
>>> ws2 = yield from ws_session.ws_connect('http://127.0.0.1:33270/')
>>> ws3 = yield from ws_session.ws_connect('http://127.0.0.1:33270/')
>>> print("{}{}{}".format(ws1, ws2, ws3))
<ClientWebSocketResponse(127.0.0.1:58793)>
<ClientWebSocketResponse(127.0.0.1:33270)>
<ClientWebSocketResponse(127.0.0.1:33270)>
>>> yield from asyncio.gather(*[ws1.release(), ws2.release(), ws3.release()])
>>> ws4 = yield from ws_session.ws_connect('http://127.0.0.1:58793/')
>>> assert ws1 == ws4
>>> yield from ws_session.close()  # Close all connections.
```
