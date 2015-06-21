import asyncio
import base64
import hashlib
import os

import aiohttp
from aiohttp import hdrs

from aiohttp.websocket import WS_KEY, WebSocketParser, WebSocketWriter


class ClientSession(aiohttp.ClientSession):
    """
    Cut and paste from aiohttp.client module.
    BASIC MODIFICATIONS: pass two new kwargs to ClientWebSocketReponse.
    """
    @asyncio.coroutine
    def ws_connect(self, url, *,
                   protocols=(),
                   timeout=10.0,
                   autoclose=True,
                   autoping=True,
                   ws_client_session=None,
                   key=None):
        """Initiate websocket connection."""

        sec_key = base64.b64encode(os.urandom(16))

        headers = {
            hdrs.UPGRADE: hdrs.WEBSOCKET,
            hdrs.CONNECTION: hdrs.UPGRADE,
            hdrs.SEC_WEBSOCKET_VERSION: '13',
            hdrs.SEC_WEBSOCKET_KEY: sec_key.decode(),
        }
        if protocols:
            headers[hdrs.SEC_WEBSOCKET_PROTOCOL] = ','.join(protocols)

        # send request
        resp = yield from self.request('get', url, headers=headers,
                                       read_until_eof=False)

        # check handshake
        if resp.status != 101:
            raise WSServerHandshakeError('Invalid response status')

        if resp.headers.get(hdrs.UPGRADE, '').lower() != 'websocket':
            raise WSServerHandshakeError('Invalid upgrade header')

        if resp.headers.get(hdrs.CONNECTION, '').lower() != 'upgrade':
            raise WSServerHandshakeError('Invalid connection header')

        # key calculation
        resp_key = resp.headers.get(hdrs.SEC_WEBSOCKET_ACCEPT, '')
        match = base64.b64encode(
            hashlib.sha1(sec_key + WS_KEY).digest()).decode()
        if resp_key != match:
            raise WSServerHandshakeError('Invalid challenge response')

        # websocket protocol
        protocol = None
        if protocols and hdrs.SEC_WEBSOCKET_PROTOCOL in resp.headers:
            resp_protocols = [
                proto.strip() for proto in
                resp.headers[hdrs.SEC_WEBSOCKET_PROTOCOL].split(',')]

            for proto in resp_protocols:
                if proto in protocols:
                    protocol = proto
                    break

        reader = resp.connection.reader.set_parser(WebSocketParser)
        writer = WebSocketWriter(resp.connection.writer, use_mask=True)

        return self._ws_response_class(reader,
                                       writer,
                                       protocol,
                                       resp,
                                       timeout,
                                       autoclose,
                                       autoping,
                                       self._loop,
                                       ws_client_session,
                                       key)
