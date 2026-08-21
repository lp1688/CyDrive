import os
import sys
import tempfile
import unittest
import asyncio
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web, FormData

sys.path.insert(0, os.path.abspath("."))

from cydrive.config import CyDriveConfig
from cydrive.database import MetaDatabase
from cydrive.web_ui.app import CyWebDashboard

class TestWebDashboardEndpoints(AioHTTPTestCase):

    async def get_application(self):
        self.test_dir = tempfile.mkdtemp(prefix="cydrive_web_test_")
        self.db_path = os.path.join(self.test_dir, "test_meta.db")
        self.db = MetaDatabase(self.db_path)
        self.config = CyDriveConfig(
            bot_token="123456:ABC-TEST",
            chat_id=7540135753,
            storage_path=self.test_dir,
            cache_path=os.path.join(self.test_dir, "cache")
        )
        self.dashboard = CyWebDashboard(self.config, self.db, telegram_engine=None)
        return self.dashboard.app

    def tearDown(self):
        super().tearDown()
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_01_index_html(self):
        """Tests index page HTML delivery."""
        resp = await self.client.request("GET", "/")
        self.assertEqual(resp.status, 200)
        text = await resp.text()
        self.assertIn("CyDrive", text)
        self.assertIn("Cloud Drive", text)

    async def test_02_stats_api(self):
        """Tests /api/stats JSON endpoint."""
        resp = await self.client.request("GET", "/api/stats")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data["total_files"], 0)
        self.assertEqual(data["chat_id"], 7540135753)
        self.assertEqual(data["drive_letter"], "Y:")

    async def test_03_upload_and_list_and_delete_api(self):
        """Tests upload, list, and delete workflow via Web API."""
        # 1. Upload mock file
        form = FormData()
        form.add_field('file', b'Test Cynet Data 2026', filename='cyber_test.txt', content_type='text/plain')
        resp = await self.client.request("POST", "/api/upload", data=form)
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertTrue(data.get("success"))

        # 2. List files
        resp = await self.client.request("GET", "/api/files")
        self.assertEqual(resp.status, 200)
        files = await resp.json()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["name"], "cyber_test.txt")

        # 3. Download file
        resp = await self.client.request("GET", "/api/download/cyber_test.txt")
        self.assertEqual(resp.status, 200)
        body = await resp.read()
        self.assertEqual(body, b'Test Cynet Data 2026')

        # 4. Delete file
        resp = await self.client.request("POST", "/api/delete", json={"filename": "cyber_test.txt"})
        self.assertEqual(resp.status, 200)
        del_data = await resp.json()
        self.assertTrue(del_data.get("success"))

        # 5. Verify deleted from list
        resp = await self.client.request("GET", "/api/files")
        files_after = await resp.json()
        self.assertEqual(len(files_after), 0)

if __name__ == "__main__":
    unittest.main()
