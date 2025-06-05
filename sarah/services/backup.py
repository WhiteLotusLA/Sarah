"""
Backup and recovery service for Sarah AI system.

Provides automated backups, point-in-time recovery, and disaster recovery capabilities.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import asyncpg
import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from sarah.config import config
from sarah.sanctuary.encryption import Encryptor

logger = logging.getLogger(__name__)


class BackupService:
    """Manages automated backups and recovery operations."""

    def __init__(self):
        self.backup_dir = Path(
            config.get(
                "backup_dir", "/Users/calvindevereaux/Documents/Projects/Sarah/backups"
            )
        )
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.scheduler = AsyncIOScheduler()
        self.encryptor = Encryptor()

        # Backup retention settings
        self.daily_retention = config.get(
            "backup_daily_retention", 7
        )  # Keep 7 daily backups
        self.weekly_retention = config.get(
            "backup_weekly_retention", 4
        )  # Keep 4 weekly backups
        self.monthly_retention = config.get(
            "backup_monthly_retention", 3
        )  # Keep 3 monthly backups

    async def initialize(self):
        """Initialize backup service connections and schedule."""
        try:
            # Initialize database connection
            self.db_pool = await asyncpg.create_pool(
                host=config.get("db_host", "localhost"),
                port=config.get("db_port", 5432),
                user=config.get("db_user", "sarah"),
                password=config.get("db_password", "sarah_secure_password"),
                database=config.get("db_name", "sarah_db"),
                min_size=1,
                max_size=5,
            )

            # Initialize Redis connection
            self.redis_client = await redis.from_url(
                f"redis://{config.get('redis_host', 'localhost')}:{config.get('redis_port', 6379)}/0"
            )

            # Schedule automated backups
            self._schedule_backups()
            self.scheduler.start()

            logger.info("Backup service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize backup service: {e}")
            raise

    def _schedule_backups(self):
        """Schedule automated backups based on configuration."""
        # Daily backups at 2 AM
        self.scheduler.add_job(
            self.create_daily_backup,
            CronTrigger(hour=2, minute=0),
            id="daily_backup",
            replace_existing=True,
        )

        # Weekly backups on Sunday at 3 AM
        self.scheduler.add_job(
            self.create_weekly_backup,
            CronTrigger(day_of_week=6, hour=3, minute=0),
            id="weekly_backup",
            replace_existing=True,
        )

        # Monthly backups on the 1st at 4 AM
        self.scheduler.add_job(
            self.create_monthly_backup,
            CronTrigger(day=1, hour=4, minute=0),
            id="monthly_backup",
            replace_existing=True,
        )

        logger.info("Backup schedules configured")

    async def create_backup(self, backup_type: str = "manual") -> str:
        """Create a complete system backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"sarah_backup_{backup_type}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Starting {backup_type} backup: {backup_name}")

            # Create backup metadata
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "type": backup_type,
                "version": "1.0",
                "components": [],
            }

            # Backup PostgreSQL database
            db_backup_path = await self._backup_postgresql(backup_path)
            if db_backup_path:
                metadata["components"].append(
                    {
                        "name": "postgresql",
                        "path": str(db_backup_path.relative_to(backup_path)),
                        "encrypted": True,
                    }
                )

            # Backup Redis data
            redis_backup_path = await self._backup_redis(backup_path)
            if redis_backup_path:
                metadata["components"].append(
                    {
                        "name": "redis",
                        "path": str(redis_backup_path.relative_to(backup_path)),
                        "encrypted": True,
                    }
                )

            # Backup configuration files
            config_backup_path = await self._backup_config(backup_path)
            if config_backup_path:
                metadata["components"].append(
                    {
                        "name": "config",
                        "path": str(config_backup_path.relative_to(backup_path)),
                        "encrypted": False,
                    }
                )

            # Backup user data and memories
            data_backup_path = await self._backup_user_data(backup_path)
            if data_backup_path:
                metadata["components"].append(
                    {
                        "name": "user_data",
                        "path": str(data_backup_path.relative_to(backup_path)),
                        "encrypted": True,
                    }
                )

            # Save metadata
            metadata_path = backup_path / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            # Create compressed archive
            archive_path = self.backup_dir / f"{backup_name}.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(backup_path, arcname=backup_name)

            # Clean up uncompressed backup
            shutil.rmtree(backup_path)

            # Clean up old backups
            await self._cleanup_old_backups(backup_type)

            logger.info(f"Backup completed successfully: {archive_path}")
            return str(archive_path)

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise

    async def _backup_postgresql(self, backup_path: Path) -> Optional[Path]:
        """Backup PostgreSQL database using pg_dump."""
        try:
            db_backup_path = backup_path / "postgresql"
            db_backup_path.mkdir(exist_ok=True)

            # Use pg_dump to create backup
            dump_file = db_backup_path / "sarah_db.sql"
            cmd = [
                "pg_dump",
                "-h",
                config.get("db_host", "localhost"),
                "-p",
                str(config.get("db_port", 5432)),
                "-U",
                config.get("db_user", "sarah"),
                "-d",
                config.get("db_name", "sarah_db"),
                "-f",
                str(dump_file),
                "--verbose",
                "--no-password",
            ]

            # Set PGPASSWORD environment variable
            env = os.environ.copy()
            env["PGPASSWORD"] = config.get("db_password", "sarah_secure_password")

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"pg_dump failed: {result.stderr}")
                return None

            # Encrypt the dump file
            encrypted_file = db_backup_path / "sarah_db.sql.enc"
            with open(dump_file, "rb") as f:
                encrypted_data = self.encryptor.encrypt(f.read())
            with open(encrypted_file, "wb") as f:
                f.write(encrypted_data)

            # Remove unencrypted dump
            dump_file.unlink()

            logger.info("PostgreSQL backup completed")
            return db_backup_path

        except Exception as e:
            logger.error(f"PostgreSQL backup failed: {e}")
            return None

    async def _backup_redis(self, backup_path: Path) -> Optional[Path]:
        """Backup Redis data."""
        try:
            redis_backup_path = backup_path / "redis"
            redis_backup_path.mkdir(exist_ok=True)

            # Get all keys and their values
            redis_data = {}
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(cursor, count=1000)
                for key in keys:
                    key_str = key.decode() if isinstance(key, bytes) else key
                    value = await self.redis_client.get(key)
                    if value:
                        redis_data[key_str] = (
                            value.decode() if isinstance(value, bytes) else value
                        )
                if cursor == 0:
                    break

            # Save to JSON and encrypt
            dump_file = redis_backup_path / "redis_dump.json"
            encrypted_file = redis_backup_path / "redis_dump.json.enc"

            json_data = json.dumps(redis_data, indent=2).encode()
            encrypted_data = self.encryptor.encrypt(json_data)

            with open(encrypted_file, "wb") as f:
                f.write(encrypted_data)

            logger.info(f"Redis backup completed: {len(redis_data)} keys backed up")
            return redis_backup_path

        except Exception as e:
            logger.error(f"Redis backup failed: {e}")
            return None

    async def _backup_config(self, backup_path: Path) -> Optional[Path]:
        """Backup configuration files."""
        try:
            config_backup_path = backup_path / "config"
            config_backup_path.mkdir(exist_ok=True)

            # List of config files to backup
            config_files = [
                "config.py",
                "requirements.txt",
                "docker-compose.yml",
                ".env",  # If exists
            ]

            project_root = Path("/Users/calvindevereaux/Documents/Projects/Sarah")
            for file_name in config_files:
                source_file = project_root / file_name
                if source_file.exists():
                    shutil.copy2(source_file, config_backup_path / file_name)

            logger.info("Configuration backup completed")
            return config_backup_path

        except Exception as e:
            logger.error(f"Configuration backup failed: {e}")
            return None

    async def _backup_user_data(self, backup_path: Path) -> Optional[Path]:
        """Backup user-specific data and memories."""
        try:
            data_backup_path = backup_path / "user_data"
            data_backup_path.mkdir(exist_ok=True)

            # Export memories from database
            async with self.db_pool.acquire() as conn:
                # Export memories
                memories = await conn.fetch(
                    """
                    SELECT * FROM memories 
                    ORDER BY created_at DESC
                """
                )

                memories_data = [dict(record) for record in memories]

                # Convert datetime objects to strings
                for memory in memories_data:
                    for key, value in memory.items():
                        if isinstance(value, datetime):
                            memory[key] = value.isoformat()

                # Encrypt and save
                memories_json = json.dumps(memories_data, indent=2).encode()
                encrypted_data = self.encryptor.encrypt(memories_json)

                with open(data_backup_path / "memories.json.enc", "wb") as f:
                    f.write(encrypted_data)

            logger.info("User data backup completed")
            return data_backup_path

        except Exception as e:
            logger.error(f"User data backup failed: {e}")
            return None

    async def _cleanup_old_backups(self, backup_type: str):
        """Clean up old backups based on retention policy."""
        try:
            # Determine retention period
            if backup_type == "daily":
                retention_days = self.daily_retention
            elif backup_type == "weekly":
                retention_days = self.weekly_retention * 7
            elif backup_type == "monthly":
                retention_days = self.monthly_retention * 30
            else:
                return  # Don't cleanup manual backups

            cutoff_date = datetime.now() - timedelta(days=retention_days)

            # Find and remove old backups
            for backup_file in self.backup_dir.glob(
                f"sarah_backup_{backup_type}_*.tar.gz"
            ):
                # Extract timestamp from filename
                try:
                    timestamp_str = (
                        backup_file.stem.split("_")[-2]
                        + "_"
                        + backup_file.stem.split("_")[-1]
                    )
                    file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                    if file_date < cutoff_date:
                        backup_file.unlink()
                        logger.info(f"Removed old backup: {backup_file.name}")
                except Exception as e:
                    logger.warning(
                        f"Could not parse backup file date: {backup_file.name}: {e}"
                    )

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    async def restore_backup(
        self, backup_path: str, components: Optional[List[str]] = None
    ) -> bool:
        """Restore system from a backup."""
        try:
            logger.info(f"Starting restore from: {backup_path}")

            # Extract backup archive
            temp_dir = self.backup_dir / "temp_restore"
            temp_dir.mkdir(exist_ok=True)

            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            # Find the extracted backup directory
            backup_dir = next(temp_dir.iterdir())

            # Load metadata
            with open(backup_dir / "metadata.json", "r") as f:
                metadata = json.load(f)

            # Restore components
            success = True
            for component in metadata["components"]:
                if components and component["name"] not in components:
                    continue

                component_path = backup_dir / component["path"]

                if component["name"] == "postgresql":
                    success &= await self._restore_postgresql(
                        component_path, component.get("encrypted", False)
                    )
                elif component["name"] == "redis":
                    success &= await self._restore_redis(
                        component_path, component.get("encrypted", False)
                    )
                elif component["name"] == "config":
                    success &= await self._restore_config(component_path)
                elif component["name"] == "user_data":
                    success &= await self._restore_user_data(
                        component_path, component.get("encrypted", False)
                    )

            # Cleanup temp directory
            shutil.rmtree(temp_dir)

            logger.info(f"Restore completed: {'Success' if success else 'Failed'}")
            return success

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            return False

    async def _restore_postgresql(self, backup_path: Path, encrypted: bool) -> bool:
        """Restore PostgreSQL database."""
        try:
            # Find the backup file
            if encrypted:
                encrypted_file = backup_path / "sarah_db.sql.enc"
                dump_file = backup_path / "sarah_db.sql"

                # Decrypt the file
                with open(encrypted_file, "rb") as f:
                    encrypted_data = f.read()
                decrypted_data = self.encryptor.decrypt(encrypted_data)

                with open(dump_file, "wb") as f:
                    f.write(decrypted_data)
            else:
                dump_file = backup_path / "sarah_db.sql"

            # Drop existing database and recreate
            async with self.db_pool.acquire() as conn:
                await conn.execute("DROP DATABASE IF EXISTS sarah_db")
                await conn.execute("CREATE DATABASE sarah_db")

            # Restore using psql
            cmd = [
                "psql",
                "-h",
                config.get("db_host", "localhost"),
                "-p",
                str(config.get("db_port", 5432)),
                "-U",
                config.get("db_user", "sarah"),
                "-d",
                config.get("db_name", "sarah_db"),
                "-f",
                str(dump_file),
                "--no-password",
            ]

            env = os.environ.copy()
            env["PGPASSWORD"] = config.get("db_password", "sarah_secure_password")

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            # Clean up decrypted file
            if encrypted and dump_file.exists():
                dump_file.unlink()

            if result.returncode != 0:
                logger.error(f"psql restore failed: {result.stderr}")
                return False

            logger.info("PostgreSQL restore completed")
            return True

        except Exception as e:
            logger.error(f"PostgreSQL restore failed: {e}")
            return False

    async def _restore_redis(self, backup_path: Path, encrypted: bool) -> bool:
        """Restore Redis data."""
        try:
            # Load backup file
            if encrypted:
                encrypted_file = backup_path / "redis_dump.json.enc"
                with open(encrypted_file, "rb") as f:
                    encrypted_data = f.read()
                json_data = self.encryptor.decrypt(encrypted_data)
                redis_data = json.loads(json_data)
            else:
                dump_file = backup_path / "redis_dump.json"
                with open(dump_file, "r") as f:
                    redis_data = json.load(f)

            # Clear existing Redis data
            await self.redis_client.flushall()

            # Restore data
            for key, value in redis_data.items():
                await self.redis_client.set(key, value)

            logger.info(f"Redis restore completed: {len(redis_data)} keys restored")
            return True

        except Exception as e:
            logger.error(f"Redis restore failed: {e}")
            return False

    async def _restore_config(self, backup_path: Path) -> bool:
        """Restore configuration files."""
        try:
            project_root = Path("/Users/calvindevereaux/Documents/Projects/Sarah")

            # Restore each config file
            for config_file in backup_path.iterdir():
                if config_file.is_file():
                    dest_file = project_root / config_file.name
                    # Backup existing file
                    if dest_file.exists():
                        shutil.copy2(dest_file, str(dest_file) + ".backup")
                    # Restore file
                    shutil.copy2(config_file, dest_file)

            logger.info("Configuration restore completed")
            return True

        except Exception as e:
            logger.error(f"Configuration restore failed: {e}")
            return False

    async def _restore_user_data(self, backup_path: Path, encrypted: bool) -> bool:
        """Restore user data and memories."""
        try:
            # Load memories
            if encrypted:
                encrypted_file = backup_path / "memories.json.enc"
                with open(encrypted_file, "rb") as f:
                    encrypted_data = f.read()
                json_data = self.encryptor.decrypt(encrypted_data)
                memories_data = json.loads(json_data)
            else:
                dump_file = backup_path / "memories.json"
                with open(dump_file, "r") as f:
                    memories_data = json.load(f)

            # Restore to database
            async with self.db_pool.acquire() as conn:
                # Clear existing memories
                await conn.execute("TRUNCATE TABLE memories CASCADE")

                # Insert memories
                for memory in memories_data:
                    # Convert ISO strings back to datetime
                    for key, value in memory.items():
                        if key in [
                            "created_at",
                            "updated_at",
                            "accessed_at",
                        ] and isinstance(value, str):
                            memory[key] = datetime.fromisoformat(value)

                    await conn.execute(
                        """
                        INSERT INTO memories (user_id, content, context, importance, embedding, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                        memory["user_id"],
                        memory["content"],
                        memory.get("context"),
                        memory["importance"],
                        memory.get("embedding"),
                        memory["created_at"],
                        memory.get("updated_at"),
                    )

            logger.info(
                f"User data restore completed: {len(memories_data)} memories restored"
            )
            return True

        except Exception as e:
            logger.error(f"User data restore failed: {e}")
            return False

    async def create_daily_backup(self):
        """Create a daily backup."""
        await self.create_backup("daily")

    async def create_weekly_backup(self):
        """Create a weekly backup."""
        await self.create_backup("weekly")

    async def create_monthly_backup(self):
        """Create a monthly backup."""
        await self.create_backup("monthly")

    async def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []

        for backup_file in self.backup_dir.glob("sarah_backup_*.tar.gz"):
            try:
                # Parse backup information from filename
                parts = backup_file.stem.split("_")
                backup_type = parts[2]
                timestamp_str = parts[3] + "_" + parts[4]
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                backups.append(
                    {
                        "path": str(backup_file),
                        "name": backup_file.name,
                        "type": backup_type,
                        "timestamp": timestamp.isoformat(),
                        "size": backup_file.stat().st_size,
                    }
                )
            except Exception as e:
                logger.warning(f"Could not parse backup file: {backup_file.name}: {e}")

        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups

    async def shutdown(self):
        """Shutdown backup service."""
        self.scheduler.shutdown()
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Backup service shutdown complete")


# Global backup service instance
backup_service = BackupService()
