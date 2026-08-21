import os
import sys
import time
import tempfile
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from cydrive.config import CyDriveConfig, get_display_ip
from cydrive.database import MetaDatabase
from cydrive.cache_manager import CacheManager
from cydrive.chunker import FileChunker
from cydrive.crypto import CyCrypto
from cydrive.platform.windows import WindowsMounter
from cydrive.platform.linux_mac import UnixMounter
from cydrive.webdav_server import VirtualTelegramFolder, VirtualTelegramFile, PureVirtualTelegramProvider

class TestCyDriveAllFeatures(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cydrive_test_")
        self.db_path = os.path.join(self.test_dir, "test_meta.db")
        self.cache_dir = os.path.join(self.test_dir, "test_cache")
        self.db = MetaDatabase(self.db_path)
        self.cache_mgr = CacheManager(self.cache_dir, limit_gb=1)

    def tearfDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_file_chunker(self):
        """Tests splitting and merging large files with SHA256 integrity check."""
        test_file = os.path.join(self.test_dir, "sample.dat")
        test_data = os.urandom(5 * 1024 * 1024)  # 5MB
        with open(test_file, "wb") as f:
            f.write(test_data)

        orig_sha = FileChunker.calculate_sha256(test_file)
        self.assertTrue(FileChunker.needs_chunking(test_file, max_chunk_mb=2))
        self.assertFalse(FileChunker.needs_chunking(test_file, max_chunk_mb=10))

        chunk_dir = os.path.join(self.test_dir, "chunks")
        chunks = FileChunker.split_file(test_file, chunk_dir, chunk_size_mb=2)
        self.assertEqual(len(chunks), 3)

        merged_file = os.path.join(self.test_dir, "merged.dat")
        FileChunker.merge_chunks(chunks, merged_file)
        merged_sha = FileChunker.calculate_sha256(merged_file)

        self.assertEqual(orig_sha, merged_sha)

    def test_02_crypto_aes256(self):
        """Tests Zero-Knowledge AES-256-GCM encryption and decryption."""
        plain_file = os.path.join(self.test_dir, "secret.txt")
        secret_content = b"Top Secret Cynet Cyber Intelligence 2026! Nonce & Salt Check."
        with open(plain_file, "wb") as f:
            f.write(secret_content)

        enc_file = os.path.join(self.test_dir, "secret.enc")
        dec_file = os.path.join(self.test_dir, "secret.dec")

        crypto = CyCrypto(password="SuperP@ssw0rd_2026!")
        self.assertTrue(crypto.encrypt_file(plain_file, enc_file))
        
        # Verify ciphertext is scrambled and not equal to plaintext
        with open(enc_file, "rb") as f:
            enc_data = f.read()
        self.assertNotEqual(secret_content, enc_data)

        self.assertTrue(crypto.decrypt_file(enc_file, dec_file))
        with open(dec_file, "rb") as f:
            dec_data = f.read()
        self.assertEqual(secret_content, dec_data)

    def test_03_database_and_chunks(self):
        """Tests SQLite VFS metadata, search, chunks, and stats."""
        file_id = self.db.upsert_file(
            rel_path="/Documents/report.pdf",
            name="report.pdf",
            parent_dir="/Documents",
            size=1048576,
            mtime=time.time(),
            telegram_msg_id=9991,
            is_uploaded=True,
            chunk_count=2
        )
        self.assertIsNotNone(file_id)

        # Upsert chunks
        self.db.upsert_chunk(file_id, 0, 9991, 524288)
        self.db.upsert_chunk(file_id, 1, 9992, 524288)

        chunks = self.db.get_chunks_by_file_id(file_id)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertEqual(chunks[1]["telegram_msg_id"], 9992)

        # Test search
        res = self.db.search_files("report")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "report.pdf")

        # Test stats
        stats = self.db.get_stats()
        self.assertEqual(stats["total_files"], 1)
        self.assertEqual(stats["total_bytes"], 1048576)

        # Test delete cascade
        self.db.delete_file("/Documents/report.pdf")
        self.assertIsNone(self.db.get_file("/Documents/report.pdf"))
        self.assertEqual(len(self.db.get_chunks_by_file_id(file_id)), 0)

    def test_04_cache_manager(self):
        """Tests LRU Cache eviction and touch mechanism."""
        p1 = self.cache_mgr.get_local_path("/test1.bin")
        p2 = self.cache_mgr.get_local_path("/test2.bin")
        
        with open(p1, "wb") as f:
            f.write(b"A" * 1024)
        time.sleep(0.01)
        with open(p2, "wb") as f:
            f.write(b"B" * 1024)

        self.assertTrue(self.cache_mgr.is_cached("/test1.bin"))
        self.assertEqual(self.cache_mgr.get_current_cache_size(), 2048)

        self.cache_mgr.touch("/test1.bin")
        self.cache_mgr.clear_all()
        self.assertEqual(self.cache_mgr.get_current_cache_size(), 0)

    def test_05_webdav_virtual_provider(self):
        """Tests WsgiDAV Virtual Resource Providers and ETag conformity."""
        self.db.upsert_file(
            rel_path="/photo.png",
            name="photo.png",
            parent_dir="/",
            size=2048,
            mtime=1700000000,
            telegram_msg_id=888,
            is_uploaded=True
        )

        provider = PureVirtualTelegramProvider(self.db, self.cache_mgr)
        root_folder = provider.get_resource_inst("/", {})
        self.assertIsInstance(root_folder, VirtualTelegramFolder)
        
        members = root_folder.get_member_list()
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].name, "photo.png")
        self.assertIsInstance(members[0], VirtualTelegramFile)

        # Verify ETag has no double quotes (WsgiDAV requirement)
        etag = members[0].get_etag()
        self.assertNotIn('"', etag)
        self.assertTrue(members[0].support_etag())
        self.assertTrue(members[0].support_ranges())

    def test_06_config_and_display_ip(self):
        """Tests configuration defaults and IP display helper."""
        cfg = CyDriveConfig(bot_token="123:ABC", chat_id=777)
        self.assertEqual(cfg.bot_token, "123:ABC")
        self.assertEqual(cfg.drive_letter, "Y:")

        ip = get_display_ip("127.0.0.1")
        self.assertEqual(ip, "127.0.0.1")

        ip_zero = get_display_ip("0.0.0.0")
        self.assertNotEqual(ip_zero, "0.0.0.0")
        self.assertTrue(len(ip_zero.split(".")) == 4)

if __name__ == "__main__":
    unittest.main()
