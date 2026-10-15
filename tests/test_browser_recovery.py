import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from playwright.async_api import Error as PlaywrightError, async_playwright
from actions.browser_control import _BrowserSession, browser_control

CLOSED = 'BrowserContext.new_page: Target page, context or browser has been closed'


class BrowserRecoveryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<title>Zaya recovery test</title><p>Browser recovered</p>')

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.server.server_port}/recovery'
        self.folder = tempfile.TemporaryDirectory()
        self.pw = await async_playwright().start()

        async def launch(profile, **kwargs):
            return await self.pw.chromium.launch_persistent_context(profile, **{**kwargs, 'headless': True})

        self.launcher = AsyncMock(side_effect=launch)
        self.session = _BrowserSession('chrome')
        self.session._spec = {'engine': 'chromium', 'exe': self.pw.chromium.executable_path, 'channel': None}
        self.session._pw = SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=self.launcher), stop=AsyncMock())
        self.profile = patch('actions.browser_control._real_profile_dir', return_value=self.folder.name)
        self.profile.start()

    async def asyncTearDown(self):
        await self.session._async_close()
        await self.pw.stop()
        self.profile.stop()
        self.folder.cleanup()
        self.server.shutdown()
        self.server.server_close()

    async def test_closed_window_relaunches_and_verifies_next_url(self):
        result = await self.session.go_to(self.url)
        self.assertEqual(result.status, 'success')
        previous = self.session._context
        await previous.close()
        self.assertIsNone(self.session._context)
        result = await self.session.go_to(self.url + '?second=1')
        self.assertEqual(result.status, 'success', result.summary)
        self.assertIsNot(self.session._context, previous)
        self.assertEqual(result.data['current_url'], self.url + '?second=1')
        self.assertEqual(self.launcher.await_count, 2)
        self.assertIn('Browser recovered', await self.session.get_text())

    async def test_disconnected_browser_relaunches_and_late_close_cannot_clear_new_context(self):
        await self.session._get_page()
        previous = self.session._context
        await previous.browser.close()
        page = await self.session._get_page()
        replacement = self.session._context
        self.session._forget_context(previous)
        self.assertIs(self.session._context, replacement)
        self.assertFalse(page.is_closed())
        self.assertEqual(self.launcher.await_count, 2)

    async def test_closed_tab_reuses_surviving_tab_and_empty_context_gets_new_page(self):
        first = await self.session._get_page()
        context = self.session._context
        second = await context.new_page()
        await first.close()
        self.assertIs(await self.session._get_page(), second)
        await second.close()
        page = await self.session._get_page()
        self.assertFalse(page.is_closed())
        self.assertIs(self.session._context, context)
        self.launcher.assert_awaited_once()

    async def test_concurrent_acquisitions_launch_only_one_context(self):
        pages = await asyncio.gather(*(self.session._get_page() for _ in range(4)))
        self.launcher.assert_awaited_once()
        self.assertEqual(len(self.session._context.pages), 1)
        self.assertTrue(all(page is pages[0] for page in pages))


class BrowserRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_navigation_recovers_once_when_target_closes_during_goto(self):
        session = _BrowserSession('chrome')
        old_context = Mock(pages=[], close=AsyncMock())
        old = Mock(context=old_context, goto=AsyncMock(side_effect=PlaywrightError(CLOSED)))
        replacement = Mock(url='https://example.com/page', is_closed=Mock(return_value=False), goto=AsyncMock())
        session._context = old_context
        session._get_page = AsyncMock(side_effect=[old, replacement])
        result = await session.go_to('https://example.com/page')
        self.assertEqual(result.status, 'success')
        old.goto.assert_awaited_once()
        replacement.goto.assert_awaited_once()
        old_context.close.assert_awaited_once()

    async def test_cached_matching_url_does_not_turn_a_navigation_error_into_success(self):
        session = _BrowserSession('chrome')
        page = Mock(url='https://example.com/page', goto=AsyncMock(side_effect=PlaywrightError('net::ERR_CONNECTION_REFUSED')))
        session._get_page = AsyncMock(return_value=page)
        result = await session.go_to('https://example.com/page')
        self.assertEqual(result.status, 'failed')
        self.assertIn('ERR_CONNECTION_REFUSED', result.evidence[0]['error'])
        page.goto.assert_awaited_once()

    async def test_context_disappearing_during_page_creation_retries_only_once(self):
        session = _BrowserSession('chrome')
        contexts = [Mock(pages=[], new_page=AsyncMock(side_effect=PlaywrightError(CLOSED))),
                    Mock(pages=[], new_page=AsyncMock(side_effect=PlaywrightError(CLOSED)))]
        for context in contexts:
            context.close = AsyncMock()
        available = iter(contexts)

        async def launch():
            session._context = next(available)

        session._launch = AsyncMock(side_effect=launch)
        with self.assertRaises(PlaywrightError):
            await session._get_page()
        self.assertEqual(session._launch.await_count, 2)
        contexts[0].close.assert_awaited_once()

    async def test_a_click_that_loses_its_page_is_never_replayed(self):
        session = _BrowserSession('chrome')
        page = Mock(click=AsyncMock(side_effect=PlaywrightError(CLOSED)))
        session._get_page = AsyncMock(return_value=page)
        with self.assertRaises(PlaywrightError):
            await session.click(selector='#submit')
        page.click.assert_awaited_once()

    async def test_explicit_close_clears_stopped_driver_so_reopen_can_start_it(self):
        session = _BrowserSession('chrome')
        driver = Mock(stop=AsyncMock())
        session._pw = driver
        session._context = Mock(close=AsyncMock())
        state = {'browser': 'chrome', 'verified': True}
        with patch('core.site_registry.browser_state', state):
            await session._async_close()
        self.assertFalse(state['verified'])
        self.assertIsNone(session._pw)
        session._async_init = AsyncMock()
        session._launch_context = AsyncMock()
        await session._launch()
        session._async_init.assert_awaited_once()
        driver.stop.assert_awaited_once()

    async def test_browser_failure_is_failed_with_exception_evidence(self):
        session = Mock(go_to=AsyncMock())

        def fail(coroutine):
            coroutine.close()
            raise PlaywrightError(CLOSED)

        session.run.side_effect = fail
        registry = Mock()
        registry.has.return_value = True
        registry.get.return_value = session
        with patch('actions.browser_control._registry', registry):
            result = browser_control({'action': 'go_to', 'url': 'https://example.com', 'mode': 'automation'})
        self.assertEqual(result.status, 'failed')
        self.assertIn(CLOSED, result.evidence[0]['error'])
        self.assertFalse(result.retryable)
        session.run.assert_called_once()
