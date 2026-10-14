from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import AsyncMock
from playwright.async_api import async_playwright
from actions.browser_control import _BrowserSession


class BrowserIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/login')
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<title>Zaya test repository</title><p>Repository</p>')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page()
        self.session = _BrowserSession.__new__(_BrowserSession)
        self.session.browser_name = 'isolated-test'
        self.session._get_page = AsyncMock(return_value=self.page)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()
        self.server.shutdown()
        self.server.server_close()

    async def test_real_navigation_and_redirect_failure(self):
        result = await self.session.go_to(self.url + '/owner/repository')
        self.assertEqual(result.status, 'success')
        self.assertEqual(result.data['current_url'], self.url + '/owner/repository')
        result = await self.session.go_to(self.url + '/redirect')
        self.assertEqual(result.status, 'failed')
        self.assertEqual(result.data['current_url'], self.url + '/login')
