import asyncio
import base64
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from core import gmail_compose,home_automation,mcp_bridge,outlook_service,resource_monitor,resource_store


class ExternalResourceTests(unittest.TestCase):
    def test_gmail_draft_changes_are_not_sent(self):
        raw=gmail_compose.raw_message({'to':'test@example.com','subject':'Teste','text':'Texto'})
        api=Mock();drafts=api.users.return_value.drafts.return_value
        drafts.get.return_value.execute.side_effect=[{'message':{'raw':raw}},{'message':{'raw':raw+'changed'}}]
        def gate(title,detail,callback):return callback()
        with patch.object(gmail_compose.google,'service',return_value=api),patch.object(gmail_compose,'request',side_effect=gate):
            with self.assertRaises(ValueError):gmail_compose.run({'action':'send','draft_id':'draft-1'})
        drafts.send.assert_not_called()
        with self.assertRaises(ValueError):gmail_compose.raw_message({'to':'test@example.com\nBcc:evil@example.com','subject':'Teste','text':'x'})

    def test_home_control_verifies_state_and_refuses_alarm(self):
        with patch.object(home_automation,'call',side_effect=[{'state':'off'},[],{'state':'off'}]),patch.object(home_automation,'request',side_effect=lambda title,detail,callback:callback()):
            result=home_automation.run({'action':'control','entity_id':'light.test','service':'turn_on'})
        self.assertFalse(result['ok']);self.assertTrue(result['uncertain'])
        with self.assertRaises(ValueError):home_automation.run({'action':'control','entity_id':'lock.front','service':'unlock'})

    def test_outlook_pagination_domain_validation(self):
        with patch.object(outlook_service,'graph') as graph:
            with self.assertRaises(ValueError):outlook_service.run({'action':'list','page_url':'https://evil.test/v1.0/me/messages'})
            graph.assert_not_called()
        with patch.object(outlook_service,'graph',return_value={'value':[{'id':'real'}],'@odata.nextLink':'https://graph.microsoft.com/v1.0/me/messages?$skiptoken=real'}):
            result=outlook_service.run({'action':'list'})
        self.assertFalse(result['complete']);self.assertEqual(result['items'][0]['id'],'real')

    def test_monitor_only_reports_changes_once(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(resource_store,'DATABASE',Path(folder)/'resources.sqlite3'):
            path=Path(folder)/'test.txt';path.write_text('one')
            resource_monitor.run({'action':'create','path':str(path)})
            self.assertEqual(resource_monitor.poll(),[])
            path.write_text('two')
            self.assertEqual(len(resource_monitor.poll()),1)
            self.assertEqual(resource_monitor.poll(),[])
            path.unlink();self.assertTrue(resource_monitor.poll()[0]['missing'])

    def test_mcp_real_local_server_and_tool_schema(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        script=("from mcp.server.fastmcp import FastMCP\n"
                f"app=FastMCP('ResourceTest',host='127.0.0.1',port={port},json_response=True)\n"
                "@app.tool()\ndef add(a:int,b:int)->int:return a+b\n"
                "app.run(transport='streamable-http')\n")
        process=subprocess.Popen([sys.executable,'-c',script],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            for _ in range(100):
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                except OSError:time.sleep(.05)
            else:self.fail('Servidor MCP de teste nao iniciou.')
            with patch.object(mcp_bridge,'settings',return_value={'endpoint':f'http://127.0.0.1:{port}/mcp','allowed_tools':'add'}):
                result=mcp_bridge.run({'action':'list'})
                self.assertEqual(result['tools'][0]['name'],'add')
                with patch.object(mcp_bridge,'request',side_effect=lambda title,detail,callback:callback()):
                    result=mcp_bridge.run({'action':'call','tool':'add','arguments_json':'{"a":2,"b":3}'})
                self.assertTrue(result['ok']);self.assertIn('5',result['content_json'])
                with self.assertRaises(ValueError):mcp_bridge.run({'action':'call','tool':'delete','arguments_json':'{}'})
        finally:
            process.terminate();process.wait(timeout=10)
