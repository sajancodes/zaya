"""Phone video is bounded, opt-in, and tied to the answering device/call."""
import asyncio
import base64
import io
from contextlib import suppress
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from PIL import Image
from core.mobile_bridge import MobileBridge
from core.mobile_calls import MobileCallManager
from dashboard.mobile_api import MobileApi
from tests.test_live_listening import agent
from tests.test_phone_call_flow import Timer


class PhoneVideoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge = MobileBridge()
        self.calls = MobileCallManager(self.bridge)
        self.calls.set_reachable_provider(lambda: True)
        timer = patch('core.mobile_calls.threading.Timer', side_effect=Timer)
        timer.start(); self.addCleanup(timer.stop); self.addCleanup(self.calls.stop)
        with patch('dashboard.mobile_api.get_bridge', return_value=self.bridge), \
                patch('dashboard.mobile_api.get_call_manager', return_value=self.calls):
            self.api = MobileApi(SimpleNamespace(device_registry=Mock()))
        self.phone = SimpleNamespace(device={'device_id': 'mine'})
        self.other = SimpleNamespace(device={'device_id': 'other'})
        self.call = self.calls.request_call(title='Fixture call', requested=True)
        stream = io.BytesIO()
        Image.new('RGB', (32, 32), 'navy').save(stream, format='JPEG')
        self.jpeg = stream.getvalue()
        self.frame = {'type': 'call.video.frame', 'call_id': self.call.call_id,
                      'jpeg': base64.b64encode(self.jpeg).decode('ascii')}
        self.toggle = {'type': 'call.video.toggle', 'call_id': self.call.call_id, 'enabled': True}

    def connect(self):
        self.calls.answer(self.call.call_id, device_id='mine')

    def test_only_answered_owner_can_opt_in_and_supply_camera_frames(self):
        self.api._call_video(self.phone, self.toggle)
        self.assertFalse(self.call.video_enabled)
        self.connect()
        self.api._call_video(self.phone, self.frame)
        self.assertTrue(self.api.video_frames.empty())
        self.api._call_video(self.other, self.toggle)
        self.assertFalse(self.call.video_enabled)
        self.api._call_video(self.phone, self.toggle)
        self.api._call_video(self.other, self.frame)
        self.assertTrue(self.api.video_frames.empty())
        self.api._call_video(self.phone, self.frame)
        self.assertEqual(self.api.video_frames.get_nowait()['data'], self.jpeg)

    def test_bad_oversized_and_rapid_frames_are_rejected_and_off_discards_pending_frame(self):
        self.connect()
        self.api._call_video(self.phone, self.toggle)
        for bad in ('not base64', 'a' * 240001, base64.b64encode(b'not JPEG').decode()):
            self.api._call_video(self.phone, dict(self.frame, jpeg=bad))
        self.assertTrue(self.api.video_frames.empty())
        self.api._call_video(self.phone, self.frame)
        first = self.api.video_frames.get_nowait()
        self.api._call_video(self.phone, self.frame)
        self.assertTrue(self.api.video_frames.empty())
        self.api.video_frames.put_nowait(first)
        self.api._call_video(self.phone, dict(self.toggle, enabled=False))
        self.assertTrue(self.api.video_frames.empty())
        self.assertFalse(self.call.video_enabled)
        self.api._call_video(self.phone, self.frame)
        self.assertTrue(self.api.video_frames.empty())

    async def test_relay_sends_live_frame_but_discards_stale_frame_after_hangup(self):
        self.connect()
        self.api._call_video(self.phone, self.toggle)
        self.api._call_video(self.phone, self.frame)
        live = agent()
        live._calls = self.calls
        live._dashboard = SimpleNamespace(mobile=lambda: self.api)
        live.session = SimpleNamespace(send_realtime_input=AsyncMock())
        relay = asyncio.create_task(live._relay_phone_video())
        try:
            await asyncio.sleep(.25)
            live.session.send_realtime_input.assert_awaited_once()
            blob = live.session.send_realtime_input.call_args.kwargs['video']
            self.assertEqual(blob.mime_type, 'image/jpeg')
            self.assertEqual(blob.data, self.jpeg)
            self.api.video_frames.put_nowait({'call_id': self.call.call_id, 'device_id': 'mine', 'data': self.jpeg})
            self.calls.end(self.call.call_id)
            await asyncio.sleep(.25)
            live.session.send_realtime_input.assert_awaited_once()
        finally:
            relay.cancel()
            with suppress(asyncio.CancelledError):
                await relay
