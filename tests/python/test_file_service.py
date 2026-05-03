"""
Tests unitaires — File Service (EXO v8)
Sandboxed file operations.
"""

import sys
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def file_service(tmp_path):
    """Create a FileService with a temporary sandbox."""
    from file_service import FileService
    svc = FileService(sandbox=tmp_path)
    return svc


class TestFileService:
    """Tests du FileService."""

    def test_create_service(self, file_service):
        assert file_service is not None

    def test_write_and_read(self, file_service):
        result = file_service.write("test.txt", "Hello EXO")
        assert result["written"] is True

        content = file_service.read("test.txt")
        assert content["content"] == "Hello EXO"

    def test_list_files(self, file_service):
        file_service.write("a.txt", "aaa")
        file_service.write("b.txt", "bbb")
        listing = file_service.list_files()
        assert len(listing["files"]) >= 2

    def test_list_with_pattern(self, file_service):
        file_service.write("doc.txt", "text")
        file_service.write("img.png", "image")
        listing = file_service.list_files(pattern="*.txt")
        names = [f["name"] for f in listing["files"]]
        assert "doc.txt" in names
        assert "img.png" not in names

    def test_read_nonexistent(self, file_service):
        with pytest.raises(FileNotFoundError):
            file_service.read("nonexistent.txt")

    def test_path_traversal_blocked(self, file_service):
        with pytest.raises(PermissionError):
            file_service.read("../../etc/passwd")

    def test_forbidden_extension(self, file_service):
        with pytest.raises(PermissionError):
            file_service.write("malware.exe", "payload")

    def test_forbidden_bat(self, file_service):
        with pytest.raises(PermissionError):
            file_service.write("script.bat", "@echo off")

    def test_forbidden_ps1(self, file_service):
        with pytest.raises(PermissionError):
            file_service.write("script.ps1", "Get-Process")

    def test_file_delete(self, file_service):
        file_service.write("temp.txt", "temp content")
        result = file_service.delete("temp.txt")
        assert result["deleted"] is True
        # Should not exist anymore
        with pytest.raises(FileNotFoundError):
            file_service.read("temp.txt")

    def test_subdirectory_write(self, file_service):
        result = file_service.write("subdir/nested.txt", "nested content")
        assert result["written"] is True
        content = file_service.read("subdir/nested.txt")
        assert content["content"] == "nested content"

    def test_max_file_size(self, file_service):
        # Try to write a file larger than 1MB
        big_content = "x" * (1024 * 1024 + 10)
        with pytest.raises(ValueError):
            file_service.write("big.txt", big_content)
