"""
Tests for the backup and recovery service.
"""

import asyncio
import json
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import pytest
import asyncpg
import redis.asyncio as redis

from sarah.services.backup import BackupService


@pytest.fixture
async def backup_service(tmp_path):
    """Create a backup service instance with temporary directory."""
    service = BackupService()
    service.backup_dir = tmp_path / "backups"
    service.backup_dir.mkdir(exist_ok=True)

    # Mock database pool
    service.db_pool = AsyncMock(spec=asyncpg.Pool)

    # Mock Redis client
    service.redis_client = AsyncMock(spec=redis.Redis)

    # Mock encryptor
    service.encryptor.encrypt = Mock(side_effect=lambda x: b"encrypted_" + x)
    service.encryptor.decrypt = Mock(
        side_effect=lambda x: x.replace(b"encrypted_", b"")
    )

    yield service

    # Cleanup
    if service.scheduler.running:
        service.scheduler.shutdown()


@pytest.mark.asyncio
async def test_initialize(backup_service):
    """Test backup service initialization."""
    with patch("asyncpg.create_pool") as mock_create_pool:
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_create_pool.return_value = AsyncMock()
            mock_redis.return_value = AsyncMock()

            await backup_service.initialize()

            assert backup_service.db_pool is not None
            assert backup_service.redis_client is not None
            assert backup_service.scheduler.running


@pytest.mark.asyncio
async def test_create_backup(backup_service, tmp_path):
    """Test creating a complete backup."""
    # Mock subprocess for pg_dump
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        # Mock database queries
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "user_id": "test_user",
                "content": "Test memory",
                "context": {"test": "data"},
                "importance": 0.8,
                "embedding": [0.1, 0.2, 0.3],
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        ]
        backup_service.db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock Redis data
        backup_service.redis_client.scan.return_value = (0, [b"key1", b"key2"])
        backup_service.redis_client.get.side_effect = [b"value1", b"value2"]

        # Create test config files
        project_root = Path("/Users/calvindevereaux/Documents/Projects/Sarah")
        (tmp_path / "config.py").write_text("# Test config")
        (tmp_path / "requirements.txt").write_text("fastapi==0.109.0")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("shutil.copy2"):
                backup_path = await backup_service.create_backup("test")

        # Verify backup was created
        assert backup_path.endswith(".tar.gz")
        assert Path(backup_path).exists()

        # Verify backup contents
        with tarfile.open(backup_path, "r:gz") as tar:
            members = tar.getnames()
            assert any("metadata.json" in m for m in members)


@pytest.mark.asyncio
async def test_backup_postgresql(backup_service, tmp_path):
    """Test PostgreSQL backup functionality."""
    backup_path = tmp_path / "test_backup"
    backup_path.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = await backup_service._backup_postgresql(backup_path)

        assert result == backup_path / "postgresql"
        assert (result / "sarah_db.sql.enc").exists()

        # Verify pg_dump was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "pg_dump" in call_args
        assert "-d" in call_args
        assert "sarah_db" in call_args


@pytest.mark.asyncio
async def test_backup_redis(backup_service, tmp_path):
    """Test Redis backup functionality."""
    backup_path = tmp_path / "test_backup"
    backup_path.mkdir()

    # Mock Redis scan and get
    backup_service.redis_client.scan.return_value = (0, [b"test_key1", b"test_key2"])
    backup_service.redis_client.get.side_effect = [b"value1", b"value2"]

    result = await backup_service._backup_redis(backup_path)

    assert result == backup_path / "redis"
    assert (result / "redis_dump.json.enc").exists()

    # Verify encryption was called
    backup_service.encryptor.encrypt.assert_called()


@pytest.mark.asyncio
async def test_cleanup_old_backups(backup_service):
    """Test cleanup of old backups."""
    # Create test backup files with different dates
    old_date = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create old backup file
    old_backup = backup_service.backup_dir / f"sarah_backup_daily_{old_date}.tar.gz"
    old_backup.touch()

    # Mock datetime to make backup appear old
    with patch("sarah.services.backup.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime.now()
        mock_datetime.strptime = datetime.strptime

        # Set retention to 0 days to force cleanup
        backup_service.daily_retention = 0

        await backup_service._cleanup_old_backups("daily")

        # Verify old backup was removed
        assert not old_backup.exists()


@pytest.mark.asyncio
async def test_restore_backup(backup_service, tmp_path):
    """Test restoring from backup."""
    # Create a test backup structure
    backup_name = "sarah_backup_test_20240101_120000"
    backup_dir = tmp_path / backup_name
    backup_dir.mkdir()

    # Create metadata
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "type": "test",
        "version": "1.0",
        "components": [
            {"name": "postgresql", "path": "postgresql", "encrypted": True},
            {"name": "redis", "path": "redis", "encrypted": True},
        ],
    }

    with open(backup_dir / "metadata.json", "w") as f:
        json.dump(metadata, f)

    # Create component directories
    (backup_dir / "postgresql").mkdir()
    (backup_dir / "postgresql" / "sarah_db.sql.enc").write_bytes(b"encrypted_database")

    (backup_dir / "redis").mkdir()
    (backup_dir / "redis" / "redis_dump.json.enc").write_bytes(
        b'encrypted_{"key": "value"}'
    )

    # Create archive
    archive_path = tmp_path / f"{backup_name}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(backup_dir, arcname=backup_name)

    # Mock subprocess and database operations
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        mock_conn = AsyncMock()
        backup_service.db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        success = await backup_service.restore_backup(str(archive_path))

        assert success

        # Verify database operations
        mock_conn.execute.assert_any_call("DROP DATABASE IF EXISTS sarah_db")
        mock_conn.execute.assert_any_call("CREATE DATABASE sarah_db")


@pytest.mark.asyncio
async def test_list_backups(backup_service):
    """Test listing available backups."""
    # Create test backup files
    backups = [
        ("sarah_backup_daily_20240101_020000.tar.gz", "daily"),
        ("sarah_backup_weekly_20240107_030000.tar.gz", "weekly"),
        ("sarah_backup_manual_20240115_143000.tar.gz", "manual"),
    ]

    for filename, _ in backups:
        (backup_service.backup_dir / filename).touch()

    result = await backup_service.list_backups()

    assert len(result) == 3

    # Verify sorting (newest first)
    timestamps = [b["timestamp"] for b in result]
    assert timestamps == sorted(timestamps, reverse=True)

    # Verify backup info
    for backup in result:
        assert "path" in backup
        assert "name" in backup
        assert "type" in backup
        assert "timestamp" in backup
        assert "size" in backup


@pytest.mark.asyncio
async def test_scheduled_backups(backup_service):
    """Test scheduled backup jobs."""
    backup_service._schedule_backups()

    jobs = backup_service.scheduler.get_jobs()
    job_ids = [job.id for job in jobs]

    assert "daily_backup" in job_ids
    assert "weekly_backup" in job_ids
    assert "monthly_backup" in job_ids

    # Verify job triggers
    daily_job = next(j for j in jobs if j.id == "daily_backup")
    assert daily_job.trigger.fields[4].name == "hour"
    assert 2 in daily_job.trigger.fields[4].expressions


@pytest.mark.asyncio
async def test_backup_error_handling(backup_service):
    """Test error handling during backup."""
    # Make pg_dump fail
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="pg_dump: error")

        # Backup should still complete but without PostgreSQL component
        backup_path = await backup_service.create_backup("test")

        # Verify backup was created
        assert Path(backup_path).exists()

        # Extract and check metadata
        with tarfile.open(backup_path, "r:gz") as tar:
            # Find metadata file
            for member in tar.getmembers():
                if "metadata.json" in member.name:
                    f = tar.extractfile(member)
                    metadata = json.load(f)

                    # PostgreSQL should not be in components due to failure
                    component_names = [c["name"] for c in metadata["components"]]
                    assert "postgresql" not in component_names
