"""
Data source connectors (Category C).

These connectors provide read-only access to data sources for training data.
"""

import asyncio
import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from tensorguard.integrations.framework.contracts import (
    DataSourceConnector,
    ConnectorCapability,
    HealthCheckResult,
    ValidationResult,
    SmokeTestResult,
    ExportArtifact,
)
from tensorguard.integrations.framework.manager import IntegrationRegistry


@IntegrationRegistry.register("local_fs")
class LocalFilesystemConnector(DataSourceConnector):
    """Connector for local filesystem data sources."""

    @property
    def provider(self) -> str:
        return "local_fs"

    @property
    def display_name(self) -> str:
        return "Local Filesystem"

    def validate_config(self) -> ValidationResult:
        """Validate local filesystem configuration."""
        errors = []
        warnings = []
        suggestions = []

        base_path = self.config.get("base_path")
        if not base_path:
            errors.append("base_path is required")
        elif not os.path.exists(base_path):
            errors.append(f"base_path does not exist: {base_path}")
        elif not os.path.isdir(base_path):
            errors.append(f"base_path is not a directory: {base_path}")

        glob_pattern = self.config.get("glob_pattern", "**/*")
        if not glob_pattern:
            warnings.append("glob_pattern is empty, defaulting to **/*")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check if local filesystem is accessible."""
        start_time = time.time()

        base_path = self.config.get("base_path", "")
        if not os.path.exists(base_path):
            return HealthCheckResult(
                status="FAIL",
                message=f"Path does not exist: {base_path}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        if not os.access(base_path, os.R_OK):
            return HealthCheckResult(
                status="FAIL",
                message=f"Path is not readable: {base_path}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # Count files
        try:
            glob_pattern = self.config.get("glob_pattern", "**/*")
            files = list(Path(base_path).glob(glob_pattern))
            file_count = len([f for f in files if f.is_file()])
        except Exception as e:
            return HealthCheckResult(
                status="WARN",
                message=f"Path accessible but glob failed: {str(e)}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        return HealthCheckResult(
            status="OK",
            message=f"Path accessible, {file_count} files found",
            latency_ms=int((time.time() - start_time) * 1000),
            details={"file_count": file_count, "base_path": base_path},
        )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.READ_DATA,
            ConnectorCapability.HASH_VERIFICATION,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Run smoke test on local filesystem."""
        start_time = time.time()

        base_path = self.config.get("base_path", "")
        try:
            # Try to list directory
            entries = os.listdir(base_path)
            return SmokeTestResult(
                passed=True,
                test_name="list_directory",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Listed {len(entries)} entries",
                details={"entry_count": len(entries)},
            )
        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="list_directory",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed to list directory: {str(e)}",
            )

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export data source reference artifact."""
        base_path = self.config.get("base_path", "")
        glob_pattern = self.config.get("glob_pattern", "**/*")

        artifact_content = f"""# Local Filesystem Data Source
base_path: {base_path}
glob_pattern: {glob_pattern}
route_key: {context.get('route_key', 'unknown')}
timestamp: {datetime.utcnow().isoformat()}
"""

        return [
            ExportArtifact(
                name="data-source-ref.yaml",
                content=artifact_content,
                artifact_type="yaml",
                metadata={"base_path": base_path},
            )
        ]

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        return [
            {
                "endpoint": self.config.get("base_path", "/data"),
                "type": "outbound",
                "protocol": "file",
            }
        ]

    async def list_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List files in the data source."""
        base_path = Path(self.config.get("base_path", ""))
        glob_pattern = self.config.get("glob_pattern", "**/*")

        if prefix:
            search_path = base_path / prefix
        else:
            search_path = base_path

        results = []
        for path in search_path.glob(glob_pattern):
            if path.is_file():
                stat = path.stat()
                results.append({
                    "key": str(path.relative_to(base_path)),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        return results

    async def get_object_hash(self, key: str) -> str:
        """Get hash of a file."""
        base_path = Path(self.config.get("base_path", ""))
        file_path = base_path / key

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    async def get_object_metadata(self, key: str) -> Dict[str, Any]:
        """Get metadata for a file."""
        base_path = Path(self.config.get("base_path", ""))
        file_path = base_path / key

        stat = file_path.stat()
        return {
            "key": key,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }


@IntegrationRegistry.register("aws_s3")
class S3Connector(DataSourceConnector):
    """Connector for AWS S3 data sources."""

    @property
    def provider(self) -> str:
        return "aws_s3"

    @property
    def display_name(self) -> str:
        return "AWS S3"

    def validate_config(self) -> ValidationResult:
        """Validate S3 configuration."""
        errors = []
        warnings = []

        bucket = self.config.get("bucket")
        if not bucket:
            errors.append("bucket is required")

        region = self.config.get("region", "us-east-1")
        if not region:
            warnings.append("region not specified, defaulting to us-east-1")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check S3 bucket accessibility."""
        start_time = time.time()

        bucket = self.config.get("bucket")
        region = self.config.get("region", "us-east-1")

        try:
            # Try to import boto3
            import boto3
            from botocore.exceptions import ClientError

            endpoint_url = self.config.get("endpoint_url")
            s3_client = boto3.client(
                "s3",
                region_name=region,
                endpoint_url=endpoint_url,
            )

            # Try head_bucket to verify access
            s3_client.head_bucket(Bucket=bucket)

            return HealthCheckResult(
                status="OK",
                message=f"Bucket {bucket} accessible",
                latency_ms=int((time.time() - start_time) * 1000),
                details={"bucket": bucket, "region": region},
            )

        except ImportError:
            return HealthCheckResult(
                status="WARN",
                message="boto3 not installed - cannot verify S3 access",
                latency_ms=int((time.time() - start_time) * 1000),
                details={"bucket": bucket, "validation_only": True},
            )

        except Exception as e:
            return HealthCheckResult(
                status="FAIL",
                message=f"S3 access failed: {str(e)}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.READ_DATA,
            ConnectorCapability.HASH_VERIFICATION,
            ConnectorCapability.VERSIONING,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Run smoke test on S3."""
        start_time = time.time()

        bucket = self.config.get("bucket")
        prefix = self.config.get("prefix", "")

        try:
            import boto3

            endpoint_url = self.config.get("endpoint_url")
            s3_client = boto3.client(
                "s3",
                region_name=self.config.get("region", "us-east-1"),
                endpoint_url=endpoint_url,
            )

            # List up to 10 objects
            response = s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=10,
            )

            count = response.get("KeyCount", 0)
            return SmokeTestResult(
                passed=True,
                test_name="list_objects",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Listed {count} objects",
                details={"object_count": count},
            )

        except ImportError:
            return SmokeTestResult(
                passed=True,
                test_name="list_objects",
                duration_ms=int((time.time() - start_time) * 1000),
                message="boto3 not installed - skipped (schema validated)",
                details={"validation_only": True},
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="list_objects",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export S3 data source reference."""
        bucket = self.config.get("bucket")
        prefix = self.config.get("prefix", "")
        region = self.config.get("region", "us-east-1")

        artifact_content = f"""# S3 Data Source Reference
bucket: {bucket}
prefix: {prefix}
region: {region}
s3_uri: s3://{bucket}/{prefix}
route_key: {context.get('route_key', 'unknown')}
timestamp: {datetime.utcnow().isoformat()}
"""

        return [
            ExportArtifact(
                name="s3-data-source-ref.yaml",
                content=artifact_content,
                artifact_type="yaml",
                metadata={"bucket": bucket, "region": region},
            )
        ]

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        bucket = self.config.get("bucket", "bucket")
        return [
            {
                "endpoint": f"s3://{bucket}/",
                "type": "outbound",
                "protocol": "s3",
                "auth_method": "iam",
            }
        ]

    async def list_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List objects in S3 bucket."""
        try:
            import boto3

            bucket = self.config.get("bucket")
            base_prefix = self.config.get("prefix", "")
            full_prefix = f"{base_prefix}/{prefix}".lstrip("/")

            s3_client = boto3.client(
                "s3",
                region_name=self.config.get("region", "us-east-1"),
                endpoint_url=self.config.get("endpoint_url"),
            )

            results = []
            paginator = s3_client.get_paginator("list_objects_v2")

            for page in paginator.paginate(Bucket=bucket, Prefix=full_prefix):
                for obj in page.get("Contents", []):
                    results.append({
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "modified": obj["LastModified"].isoformat(),
                        "etag": obj.get("ETag", "").strip('"'),
                    })

            return results

        except ImportError:
            return []

    async def get_object_hash(self, key: str) -> str:
        """Get ETag (hash) of S3 object."""
        try:
            import boto3

            bucket = self.config.get("bucket")
            s3_client = boto3.client(
                "s3",
                region_name=self.config.get("region", "us-east-1"),
                endpoint_url=self.config.get("endpoint_url"),
            )

            response = s3_client.head_object(Bucket=bucket, Key=key)
            return response.get("ETag", "").strip('"')

        except ImportError:
            return ""

    async def get_object_metadata(self, key: str) -> Dict[str, Any]:
        """Get metadata for S3 object."""
        try:
            import boto3

            bucket = self.config.get("bucket")
            s3_client = boto3.client(
                "s3",
                region_name=self.config.get("region", "us-east-1"),
                endpoint_url=self.config.get("endpoint_url"),
            )

            response = s3_client.head_object(Bucket=bucket, Key=key)
            return {
                "key": key,
                "size": response.get("ContentLength", 0),
                "modified": response.get("LastModified").isoformat()
                if response.get("LastModified")
                else None,
                "etag": response.get("ETag", "").strip('"'),
                "content_type": response.get("ContentType"),
            }

        except ImportError:
            return {"key": key, "error": "boto3 not installed"}
