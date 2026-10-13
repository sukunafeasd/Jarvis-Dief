import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from core.spatial_view import SpatialCoreView


class SpatialLifecycleAudit(unittest.TestCase):
    def test_late_health_callback_after_close_does_nothing(self):
        view=SimpleNamespace(_alive=lambda:False,_fail=Mock(),failed=False)
        SpatialCoreView._health_result(view,{'error':'context-lost'})
        view._fail.assert_not_called()

    def test_failure_is_idempotent(self):
        view=SimpleNamespace(_alive=lambda:True,failed=True,_health=Mock(),hide=Mock(),unavailable=Mock())
        SpatialCoreView._fail(view)
        view.hide.assert_not_called();view.unavailable.emit.assert_not_called()

    def test_ready_signal_is_emitted_once(self):
        view=SimpleNamespace(_alive=lambda:True,failed=False,_ready=False,ready=Mock(),_fail=Mock())
        SpatialCoreView._health_result(view,{'ready':'true'})
        SpatialCoreView._health_result(view,{'ready':'true'})
        view.ready.emit.assert_called_once()

    def test_page_load_that_never_finishes_releases_to_fallback(self):
        view=SimpleNamespace(_alive=lambda:True,failed=False,_loaded=False,_created=0,_fail=Mock())
        with patch('core.spatial_view.time.monotonic',return_value=25):
            SpatialCoreView._check_health(view)
        view._fail.assert_called_once()

    def test_fault_record_excludes_secret_exception_message(self):
        from core import runtime_diagnostics
        output=io.StringIO()
        try:raise ValueError('secret-api-key-never-record')
        except ValueError as error:
            with patch.object(runtime_diagnostics,'_sink',output):
                runtime_diagnostics.record_fault(type(error),error.__traceback__)
        self.assertIn('ValueError',output.getvalue())
        self.assertNotIn('secret-api-key',output.getvalue())
