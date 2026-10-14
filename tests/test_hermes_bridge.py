import importlib.util
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from services.whatsapp.bridge import HookReceiver, install_hook


class BridgeTests(unittest.TestCase):
    def test_authenticated_hook_roundtrip_and_offline_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            descriptor = Path(folder) / 'bridge.json'
            hook = install_hook(Path(folder) / 'hermes', descriptor)
            spec = importlib.util.spec_from_file_location('zaya_test_hook', hook / 'handler.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            context = {'platform': 'whatsapp', 'chat_id': '123@s.whatsapp.net', 'message': 'hello'}
            module.handle('agent:start', context)  # offline durable event
            received = []
            receiver = HookReceiver(lambda event, ctx: received.append((event, ctx)), descriptor)
            receiver.start()
            try:
                module.handle('agent:end', {**context, 'response': 'reply'})
                self.assertEqual(len(received), 2)
                data = json.loads(descriptor.read_text())
                request = urllib.request.Request(data['url'], data=b'{}')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 401)
                self.assertEqual(receiver.server.server_address[0], '127.0.0.1')
            finally:
                receiver.close()
