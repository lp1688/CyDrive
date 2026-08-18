import os
import hashlib
from typing import List, Generator, Tuple

CHUNK_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB read buffer

class FileChunker:
    """Handles splitting and merging of large files (> 2GB limit bypass)."""

    @staticmethod
    def calculate_sha256(file_path: str) -> str:
        """Calculates SHA-256 hash of a file efficiently."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_BUFFER_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def needs_chunking(file_path: str, max_chunk_mb: int = 1900) -> bool:
        """Checks if a file exceeds the single Telegram upload limit."""
        size_bytes = os.path.getsize(file_path)
        return size_bytes > (max_chunk_mb * 1024 * 1024)

    @staticmethod
    def split_file(file_path: str, output_dir: str, chunk_size_mb: int = 1900) -> List[str]:
        """Splits a file into multiple chunks and returns their paths."""
        os.makedirs(output_dir, exist_ok=True)
        chunk_size_bytes = chunk_size_mb * 1024 * 1024
        chunk_paths = []
        base_name = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            chunk_index = 0
            while True:
                chunk_file = os.path.join(output_dir, f"{base_name}.part{chunk_index:03d}")
                bytes_written = 0

                with open(chunk_file, "wb") as chunk_f:
                    while bytes_written < chunk_size_bytes:
                        to_read = min(CHUNK_BUFFER_SIZE, chunk_size_bytes - bytes_written)
                        data = f.read(to_read)
                        if not data:
                            break
                        chunk_f.write(data)
                        bytes_written += len(data)

                if bytes_written > 0:
                    chunk_paths.append(chunk_file)
                    chunk_index += 1
                else:
                    if os.path.exists(chunk_file):
                        os.remove(chunk_file)
                    break

        return chunk_paths

    @staticmethod
    def merge_chunks(chunk_paths: List[str], output_file_path: str) -> str:
        """Merges ordered chunk parts back into the original file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_file_path)), exist_ok=True)
        with open(output_file_path, "wb") as out_f:
            for part_path in chunk_paths:
                with open(part_path, "rb") as part_f:
                    while data := part_f.read(CHUNK_BUFFER_SIZE):
                        out_f.write(data)
        return output_file_path
