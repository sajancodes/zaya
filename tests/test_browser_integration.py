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
        try:
            self.playwright = await async_playwright().start()
            chrome_exe = self.playwright.chromium.executable_path
            launch_kwargs = {'headless': True}
            from pathlib import Path
            if not Path(chrome_exe).exists():
                from actions.browser_control import _find_exe_windows
                found = _find_exe_windows("chrome") or _find_exe_windows("msedge")
                if found and Path(found).exists():
                    launch_kwargs['executable_path'] = found
                else:
                    self.skipTest("No chromium executable found for integration test")
            self.browser = await self.playwright.chromium.launch(**launch_kwargs)
            self.page = await self.browser.new_page()
        except Exception as e:
            self.skipTest(f"Playwright driver/browser unavailable in this environment: {e}")
        self.session = _BrowserSession.__new__(_BrowserSession)
        self.session.browser_name = 'isolated-test'
        self.session._get_page = AsyncMock(return_value=self.page)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    async def asyncTearDown(self):
        if hasattr(self, 'browser') and self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright') and self.playwright:
            await self.playwright.stop()
        if hasattr(self, 'server') and self.server:
            self.server.shutdown()
            self.server.server_close()

    async def test_real_navigation_and_redirect_failure(self):
        result = await self.session.go_to(self.url + '/owner/repository')
        self.assertEqual(result.status, 'success')
        self.assertEqual(result.data['current_url'], self.url + '/owner/repository')
        result = await self.session.go_to(self.url + '/redirect')
        self.assertEqual(result.status, 'failed')
        self.assertEqual(result.data['current_url'], self.url + '/login')
