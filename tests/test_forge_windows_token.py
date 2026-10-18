"""Regression checks for identification-only UAC linked tokens."""
import os
import unittest
from unittest.mock import Mock,patch


@unittest.skipUnless(os.name=='nt','Windows token API')
class StandardTokenTests(unittest.TestCase):
    def run_case(self,code,elevated=True):
        import pywintypes
        import win32security as security
        from core.forge.windows_process import standard_token
        current=Mock();linked=Mock();duplicate=Mock()
        def information(token,kind):
            if kind==security.TokenUser:return ('same-user',0)
            if kind==security.TokenElevation:return elevated
            if kind==security.TokenLinkedToken:return linked
            if kind==security.TokenSessionId:return 7
            raise AssertionError(kind)
        with patch('win32security.OpenProcessToken',return_value=current),\
             patch('win32security.GetTokenInformation',side_effect=information),\
             patch('win32security.DuplicateTokenEx',side_effect=pywintypes.error(code,'DuplicateTokenEx','test')),\
             patch('core.forge.windows_process.verify_token') as verify,\
             patch('core.forge.windows_process.shell_standard_token',return_value=duplicate) as fallback:
            if elevated and code==1346:
                result=standard_token()
                self.assertEqual(result,(duplicate,'same-user',True))
                fallback.assert_called_once_with('same-user',7)
                verify.assert_called_once_with(linked,'same-user')
            else:
                with self.assertRaises(pywintypes.error):standard_token()
                fallback.assert_not_called()
        current.Close.assert_called_once()
        if elevated:linked.Close.assert_called_once()

    def test_linked_identification_token_uses_verified_shell(self):self.run_case(1346)
    def test_other_errors_do_not_select_another_token(self):self.run_case(5)
    def test_standard_host_does_not_use_shell_fallback(self):self.run_case(1346,False)
