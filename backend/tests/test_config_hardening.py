"""
Unit tests for Phase 13.1 — Configuration & Environment Hardening.
Verifies safe local defaults, Cloud Run runtime support, and environment-driven overrides.
"""
import os
import pytest
from app.core.config import Settings, settings


def test_safe_local_defaults():
    """Verify that all cloud and live services have safe local defaults."""
    default_settings = Settings(
        _env_file=None,  # Do not read .env for pure default evaluation
    )
    # Cloud features must be disabled by default
    assert default_settings.GCS_ENABLED is False
    assert default_settings.PUBSUB_ENABLED is False
    assert default_settings.ENABLE_FIRESTORE is False
    assert default_settings.ENABLE_CLOUD_STORAGE is False
    assert default_settings.STORAGE_BACKEND == "local"
    assert default_settings.DATABASE_BACKEND == "local"

    # Properties
    assert default_settings.is_local_storage is True
    assert default_settings.is_gcs_enabled is False
    assert default_settings.is_pubsub_enabled is False
    assert default_settings.is_local_database is True

    # Deterministic default mode
    assert default_settings.ADK_MODE in ["offline", "live"]
    assert default_settings.effective_gcp_project_id == "chain-of-title-cinema-2026"
    assert default_settings.effective_gcs_bucket == "chain-of-title-cinema-2026"
    assert default_settings.PUBSUB_TOPIC == "chain-of-title-events"


def test_cloud_run_port_resolution(monkeypatch):
    """Verify that Cloud Run PORT environment variable is respected."""
    monkeypatch.setenv("PORT", "8080")
    custom_settings = Settings(_env_file=None, PORT=8080)
    assert custom_settings.PORT == 8080
    assert custom_settings.effective_port == 8080

    # When PORT is unset, fallback to API_PORT
    custom_settings_no_port = Settings(_env_file=None, PORT=None, API_PORT=9000)
    assert custom_settings_no_port.effective_port == 9000


def test_gcs_and_pubsub_environment_overrides(monkeypatch):
    """Verify that GCS and Pub/Sub can be enabled and configured purely via environment variables."""
    custom_settings = Settings(
        _env_file=None,
        GCP_PROJECT_ID="custom-prod-project",
        GCS_BUCKET="custom-prod-bucket",
        GCS_ENABLED=True,
        PUBSUB_TOPIC="custom-clearance-events",
        PUBSUB_ENABLED=True,
    )
    assert custom_settings.is_gcs_enabled is True
    assert custom_settings.effective_gcs_bucket == "custom-prod-bucket"
    assert custom_settings.effective_gcp_project_id == "custom-prod-project"
    assert custom_settings.is_pubsub_enabled is True
    assert custom_settings.pubsub_topic_path == "projects/custom-prod-project/topics/custom-clearance-events"


def test_storage_backend_gcs_activation():
    """Verify that STORAGE_BACKEND=gcs activates is_gcs_enabled property."""
    custom_settings = Settings(
        _env_file=None,
        STORAGE_BACKEND="gcs",
        GCS_ENABLED=False,
    )
    assert custom_settings.is_gcs_enabled is True
    assert custom_settings.is_local_storage is False


def test_cors_origins_parsing():
    """Verify CORS origins can be parsed from comma-separated string or list."""
    settings_str = Settings(
        _env_file=None,
        CORS_ORIGINS="https://demo.run.app, https://client.com",
    )
    origins = settings_str.get_cors_origins()
    assert "https://demo.run.app" in origins
    assert "https://client.com" in origins
    assert len(origins) == 2
