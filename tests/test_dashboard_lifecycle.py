import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class DashboardLifecycleTests(unittest.TestCase):
    def test_port_failure_does_not_escape_the_dashboard_task(self):
        import dashboard.server as server
        from dashboard.server import DashboardServer

        class FailingServer:
            def __init__(self, config):
                self.config = config

            async def serve(self):
                raise SystemExit(3)

        dashboard = object.__new__(DashboardServer)
        with patch.object(server, 'uvicorn', SimpleNamespace(Server=FailingServer), create=True):
            asyncio.run(dashboard._serve_uvicorn(object(), 'teste'))


if __name__ == '__main__':
    unittest.main()
