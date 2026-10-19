import unittest
from unittest.mock import patch, MagicMock
from actions.port_tunnel import deploy_wormhole, _active_tunnels

class TestPortTunnel(unittest.TestCase):
    def tearDown(self):
        _active_tunnels.clear()

    @patch("actions.port_tunnel.start_tunnel_process")
    def test_deploy_wormhole_start(self, mock_start):
        mock_start.return_value = {
            "status": "success",
            "port": 3000,
            "tunnel_url": "https://zaya-wormhole-demo.trycloudflare.com",
            "provider": "cloudflared"
        }
        res = deploy_wormhole({"action": "start", "port": 3000})
        self.assertIn("https://zaya-wormhole-demo.trycloudflare.com", res)
        self.assertIn("3000", res)

    @patch("actions.port_tunnel.stop_tunnel_process")
    def test_deploy_wormhole_stop(self, mock_stop):
        mock_stop.return_value = {"status": "success", "message": "Closed wormhole tunnel on port 3000."}
        res = deploy_wormhole({"action": "stop", "port": 3000})
        self.assertIn("Closed wormhole tunnel", res)

    def test_deploy_wormhole_list_empty(self):
        res = deploy_wormhole({"action": "status"})
        self.assertIn("active_tunnels", res)

if __name__ == "__main__":
    unittest.main()
