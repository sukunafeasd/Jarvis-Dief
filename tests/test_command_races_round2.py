"""A superseded library lookup must not become a new user command."""
import asyncio
import threading
import unittest
from unittest.mock import AsyncMock, Mock

from test_command_chaos_round import assistant


class ForgeLookupRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_user_turn_cancels_delayed_project_open(self):
        owner = assistant()
        owner._forge_mode = True
        owner._dispatch_forge = AsyncMock()
        started, release = threading.Event(), threading.Event()

        def library(*args):
            started.set()
            release.wait(3)
            return {'projects': [{'name': 'Reator', 'id': 'fixture'}]}

        owner.ui.forge_runtime.command = Mock(side_effect=library)
        owner.ui.record_ultron_user('abra o projeto Reator')
        task = asyncio.create_task(owner._route_protocol_user_once('abra o projeto Reator'))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 1))
            owner.ui.record_ultron_user('nao abra nada')
        finally:
            release.set()
            await asyncio.wait_for(task, 2)
        owner._dispatch_forge.assert_not_awaited()
