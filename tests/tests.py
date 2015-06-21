import asyncio
import socket
import unittest
from urllib.parse import urlparse

import aiohttp
from aiohttp import web

from aiowebsocketclient import WebSocketClientSession


class TestWebSocketClientFunctional(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        if self.handler:
            self.loop.run_until_complete(self.handler.finish_connections())

        self.loop.close()

    def find_unused_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
        return port

    @asyncio.coroutine
    def create_server(self, method, path, handler):
        app = web.Application(loop=self.loop)
        app.router.add_route(method, path, handler)

        port = self.find_unused_port()
        self.handler = app.make_handler()
        srv = yield from self.loop.create_server(
            self.handler, '127.0.0.1', port)
        url = "http://127.0.0.1:{}".format(port) + path
        self.addCleanup(srv.close)
        return app, srv, url

    @asyncio.coroutine
    def simple_wshandler(self, request):
        ws = web.WebSocketResponse()
        ws.start(request)

        msg = yield from ws.receive_str()
        ws.send_str(msg + '/answer')
        yield from ws.close()
        return ws

    @asyncio.coroutine
    def wshandler(self, request):

        ws = web.WebSocketResponse()
        ws.start(request)
        while True:
            msg = yield from ws.receive()
            if msg.tp == aiohttp.MsgType.text:
                ws.send_str(msg.data + '/answer')
            elif msg.tp == aiohttp.MsgType.close:
                yield from ws.close()
                break
            elif msg.tp == aiohttp.MsgType.error:
                print('ws connection closed with exception %s',
                      ws.exception())

        return ws

    def get_key(self, url):
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
        scheme = parsed.scheme
        ssl = scheme in ["https", "wss"]
        key = (host, port, ssl)
        return key

    def test_conn_close(self):

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/',
                                                      self.simple_wshandler)

            key = self.get_key(url)

            ws_session = WebSocketClientSession(loop=self.loop)

            resp = yield from ws_session.ws_connect(url)
            resp.send_str('ask')
            msg = yield from resp.receive()

            self.assertEqual(msg.data, 'ask/answer')

            yield from resp.close()
            self.assertFalse(ws_session._acquired[key])
            self.assertIsNone(ws_session._conns.get(key, None))

            yield from ws_session.close()

        self.loop.run_until_complete(go())

    def test_conn_force_close(self):

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/',
                                                      self.simple_wshandler)

            key = self.get_key(url)

            ws_session = WebSocketClientSession(force_close=True,
                                                loop=self.loop)
            resp = yield from ws_session.ws_connect(url)
            resp.send_str('ask')
            msg = yield from resp.receive()
            self.assertEqual(msg.data, 'ask/answer')
            yield from resp.release()

            self.assertFalse(ws_session._acquired[key])
            self.assertIsNone(ws_session._conns.get(key, None))

            yield from ws_session.close()

        self.loop.run_until_complete(go())

    def test_conn_release(self):

        @asyncio.coroutine
        def handler(request):
            ws = web.WebSocketResponse()
            ws.start(request)

            msg = yield from ws.receive_str()
            ws.send_str(msg + '/answer')
            yield from ws.close()
            return ws

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/', handler)

            key = self.get_key(url)

            ws_session = WebSocketClientSession(loop=self.loop)
            resp = yield from ws_session.ws_connect(url)
            resp.send_str('ask')
            msg = yield from resp.receive()
            self.assertEqual(msg.data, 'ask/answer')
            yield from resp.release()
            self.assertFalse(ws_session._acquired[key])
            self.assertEqual(ws_session._conns.get(key)[0], resp)
            yield from ws_session.close()

        self.loop.run_until_complete(go())

    def test_session_close_release(self):

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/',
                                                      self.simple_wshandler)

            key = self.get_key(url)

            ws_session = WebSocketClientSession(loop=self.loop)
            resp = yield from ws_session.ws_connect(url)
            resp.send_str('ask')
            msg = yield from resp.receive()
            self.assertEqual(msg.data, 'ask/answer')
            yield from resp.release()
            yield from ws_session.close()
            self.assertFalse(ws_session._acquired)
            self.assertFalse(ws_session._conns)
            self.assertTrue(ws_session.closed)

        self.loop.run_until_complete(go())

    def test_session_close_no_release(self):

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/',
                                                      self.simple_wshandler)

            key = self.get_key(url)

            ws_session = WebSocketClientSession(loop=self.loop)
            resp = yield from ws_session.ws_connect(url)
            resp.send_str('ask')
            msg = yield from resp.receive()
            self.assertEqual(msg.data, 'ask/answer')
            yield from ws_session.close()
            self.assertFalse(ws_session._acquired)
            self.assertFalse(ws_session._conns)
            self.assertTrue(ws_session.closed)
            self.assertIsNone(ws_session.client_session)

        self.loop.run_until_complete(go())

    def test_simple_conn_reuse(self):

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/',
                                                      self.wshandler)

            key = self.get_key(url)
            ws_session = WebSocketClientSession(loop=self.loop)

            resp = yield from ws_session.ws_connect(url)
            resp.send_str('ask')
            msg = yield from resp.receive()
            self.assertEqual(msg.data, 'ask/answer')
            yield from resp.release()

            resp2 = yield from ws_session.ws_connect(url)
            resp2.send_str('ask-again')
            msg = yield from resp2.receive()
            self.assertEqual(msg.data, 'ask-again/answer')
            yield from resp2.release()

            self.assertEqual(ws_session._conns.get(key)[0], resp, resp2)
            yield from ws_session.close()

        self.loop.run_until_complete(go())

    def test_multi_conn(self):

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/',
                                                      self.wshandler)

            key = self.get_key(url)
            ws_session = WebSocketClientSession(loop=self.loop)

            resp = yield from ws_session.ws_connect(url)
            resp2 = yield from ws_session.ws_connect(url)
            self.assertNotEqual(resp, resp2)

            self.assertEqual(len(ws_session._acquired[key]), 2)
            yield from resp.release()
            yield from resp2.release()

            self.assertEqual(len(ws_session._conns[key]), 2)
            yield from ws_session.close()

        self.loop.run_until_complete(go())

    def test_multi_resource_multi_conn(self):

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/',
                                                      self.wshandler)
            _, _, url2 = yield from self.create_server('GET', '/',
                                                       self.wshandler)

            key = self.get_key(url)

            key2 = self.get_key(url2)

            self.assertNotEqual(key, key2)

            ws_session = WebSocketClientSession(loop=self.loop)

            resp = yield from ws_session.ws_connect(url)
            resp2 = yield from ws_session.ws_connect(url2)
            resp3 = yield from ws_session.ws_connect(url2)
            self.assertNotEqual(resp, resp2)
            self.assertNotEqual(resp, resp3)
            self.assertNotEqual(resp2, resp3)

            self.assertEqual(len(ws_session._acquired[key]), 1)
            self.assertEqual(len(ws_session._acquired[key2]), 2)
            yield from resp.release()
            yield from resp2.release()

            self.assertEqual(len(ws_session._conns[key]), 1)
            self.assertEqual(len(ws_session._conns[key2]), 1)

            resp4 = yield from ws_session.ws_connect(url2)

            self.assertEqual(resp2, resp4)

            self.assertEqual(len(ws_session._acquired[key2]), 2)

            yield from resp3.release()
            yield from resp4.release()

            self.assertEqual(len(ws_session._conns[key2]), 2)

            yield from ws_session.close()
            self.assertFalse(ws_session._conns)

        self.loop.run_until_complete(go())

    def test_slow_fast_conns(self):

        @asyncio.coroutine
        def slow_task(resp, loop):
            yield from asyncio.sleep(0.5, loop=loop)
            resp.send_str('ask')
            msg = yield from resp.receive()
            self.assertEqual(msg.data, 'ask/answer')
            yield from resp.release()
            return loop.time()

        @asyncio.coroutine
        def task(ws_session, url, loop, prev_resp):
            resp = yield from ws_session.ws_connect(url)
            self.assertNotEqual(resp, prev_resp)
            resp.send_str('ask-again')
            msg = yield from resp.receive()
            self.assertEqual(msg.data, 'ask-again/answer')
            yield from resp.release()
            return loop.time()

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/',
                                                      self.wshandler)

            key = self.get_key(url)
            ws_session = WebSocketClientSession(loop=self.loop)
            resp = yield from ws_session.ws_connect(url)
            results = yield from asyncio.gather(
                *[slow_task(resp, self.loop),
                  task(ws_session, url, self.loop, resp)], loop=self.loop)

            slow = results[0]
            fast = results[1]
            self.assertTrue(fast < slow)

            self.assertEqual(len(ws_session._acquired[key]), 0)
            self.assertEqual(len(ws_session._conns[key]), 2)
            yield from ws_session.close()

        self.loop.run_until_complete(go())

    def test_wait_for_conn(self):

        @asyncio.coroutine
        def slow_task(resp, loop):
            yield from asyncio.sleep(0.5, loop=loop)
            resp.send_str('ask')
            msg = yield from resp.receive()
            self.assertEqual(msg.data, 'ask/answer')
            yield from resp.release()
            return loop.time()

        @asyncio.coroutine
        def task(ws_session, url, loop, prev_resp):
            resp = yield from ws_session.ws_connect(url)
            self.assertEqual(resp, prev_resp)
            resp.send_str('ask-again')
            msg = yield from resp.receive()
            self.assertEqual(msg.data, 'ask-again/answer')
            return loop.time()

        @asyncio.coroutine
        def go():
            _, _, url = yield from self.create_server('GET', '/',
                                                      self.wshandler)

            key = self.get_key(url)
            ws_session = WebSocketClientSession(loop=self.loop, limit=1)
            resp = yield from ws_session.ws_connect(url)
            results = yield from asyncio.gather(
                *[task(ws_session, url, self.loop, resp),
                  slow_task(resp, self.loop)], loop=self.loop)

            slow = results[1]
            fast = results[0]
            self.assertTrue(slow < fast)

            yield from resp.release()
            self.assertEqual(len(ws_session._acquired[key]), 0)
            self.assertEqual(len(ws_session._conns[key]), 1)
            yield from ws_session.close()

        self.loop.run_until_complete(go())


class TestClientSessionMngmnt(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        self.loop.close()

    def test_detach_client_session(self):
        @asyncio.coroutine
        def go():
            sess = aiohttp.ClientSession(loop=self.loop)
            ws_session = WebSocketClientSession(loop=self.loop,
                                                client_session=sess)
            ws_session.detach()
            yield from ws_session.close()

            self.assertFalse(sess.closed)
            sess.close()
        self.loop.run_until_complete(go())

    def test_client_session_close(self):
        @asyncio.coroutine
        def go():
            sess = aiohttp.ClientSession(loop=self.loop)
            ws_session = WebSocketClientSession(loop=self.loop,
                                                client_session=sess)
            yield from ws_session.close()

            self.assertTrue(sess.closed)

        self.loop.run_until_complete(go())


if __name__ == "__main__":
    unittest.main()
