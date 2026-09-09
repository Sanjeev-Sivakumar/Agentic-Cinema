"""
Unit tests for Google Cloud Pub/Sub Publisher Adapter.
Verifies:
1. Disabled/offline mode (default): returns cleanly, 0 network calls, 0 credentials needed.
2. Enabled mode with mocks: correct topic path, payload data, and string attributes.
3. Strict error isolation: simulated failures, network timeouts, or auth errors never raise or disrupt pipeline.
4. EventBus integration: dual fan-out to in-memory subscriber queues and Pub/Sub publisher.
"""
import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.core.config import settings
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.services.pubsub_publisher import PubSubEventPublisher
from app.services.events import InMemoryEventBus


@pytest.fixture
def sample_event() -> ProcessingEvent:
    return ProcessingEvent(
        production_id="prod_pubsub_test",
        job_id="job_pubsub_test",
        event_type=EventType.STAGE_STARTED,
        stage=PipelineStage.SCREENPLAY_EXTRACTION,
        sequence_number=1,
        progress=8.0,
        message="Screenplay extraction started",
        workflow_id="wf_pubsub_001",
    )


@pytest.mark.asyncio
async def test_pubsub_disabled_by_default(sample_event):
    """When PUBSUB_ENABLED=False, publishing returns False with zero SDK initialization."""
    orig_enabled = settings.PUBSUB_ENABLED
    try:
        settings.PUBSUB_ENABLED = False
        publisher = PubSubEventPublisher()

        result = await publisher.publish_event(sample_event)
        assert result is False
        assert publisher._get_client() is None
    finally:
        settings.PUBSUB_ENABLED = orig_enabled


def test_pubsub_topic_path_resolution():
    """Verify settings properties resolve topic path correctly."""
    orig_proj = settings.GCP_PROJECT_ID
    orig_topic = settings.PUBSUB_TOPIC
    try:
        settings.GCP_PROJECT_ID = "chain-of-title-cinema-2026"
        settings.PUBSUB_TOPIC = "chain-of-title-events"

        assert settings.effective_gcp_project_id == "chain-of-title-cinema-2026"
        assert settings.pubsub_topic_path == "projects/chain-of-title-cinema-2026/topics/chain-of-title-events"
    finally:
        settings.GCP_PROJECT_ID = orig_proj
        settings.PUBSUB_TOPIC = orig_topic


@pytest.mark.asyncio
async def test_pubsub_enabled_publish_mocked(sample_event):
    """When PUBSUB_ENABLED=True, message and string attributes are correctly formatted and published."""
    orig_enabled = settings.PUBSUB_ENABLED
    orig_proj = settings.GCP_PROJECT_ID
    orig_topic = settings.PUBSUB_TOPIC

    try:
        settings.PUBSUB_ENABLED = True
        settings.GCP_PROJECT_ID = "chain-of-title-cinema-2026"
        settings.PUBSUB_TOPIC = "chain-of-title-events"

        publisher = PubSubEventPublisher()

        # Mock PublisherClient
        mock_future = MagicMock()
        mock_future.result.return_value = "msg_123456789"

        mock_client = MagicMock()
        mock_client.publish.return_value = mock_future

        with patch("google.cloud.pubsub_v1.PublisherClient", return_value=mock_client):
            success = await publisher.publish_event(sample_event)

            assert success is True
            assert mock_client.publish.called

            # Inspect call arguments
            call_args, call_kwargs = mock_client.publish.call_args
            topic_arg = call_args[0]
            assert topic_arg == "projects/chain-of-title-cinema-2026/topics/chain-of-title-events"

            # Verify serialized JSON payload
            data_bytes = call_kwargs.get("data")
            assert isinstance(data_bytes, bytes)
            payload = json.loads(data_bytes.decode("utf-8"))
            assert payload["production_id"] == "prod_pubsub_test"
            assert payload["job_id"] == "job_pubsub_test"
            assert payload["event_type"] == "STAGE_STARTED"

            # Verify attributes are string dictionary
            assert call_kwargs.get("event_type") == "STAGE_STARTED"
            assert call_kwargs.get("job_id") == "job_pubsub_test"
            assert call_kwargs.get("production_id") == "prod_pubsub_test"
            assert call_kwargs.get("stage") == "Screenplay Extraction"
            assert call_kwargs.get("workflow_id") == "wf_pubsub_001"
    finally:
        settings.PUBSUB_ENABLED = orig_enabled
        settings.GCP_PROJECT_ID = orig_proj
        settings.PUBSUB_TOPIC = orig_topic


@pytest.mark.asyncio
async def test_pubsub_error_isolation(sample_event):
    """Simulated publish exception is caught, logged as warning, and never raises."""
    orig_enabled = settings.PUBSUB_ENABLED
    try:
        settings.PUBSUB_ENABLED = True
        publisher = PubSubEventPublisher()

        mock_client = MagicMock()
        mock_client.publish.side_effect = RuntimeError("Simulated GCP network timeout")

        with patch("google.cloud.pubsub_v1.PublisherClient", return_value=mock_client):
            # Should not raise exception
            success = await publisher.publish_event(sample_event)
            assert success is False
    finally:
        settings.PUBSUB_ENABLED = orig_enabled


@pytest.mark.asyncio
async def test_event_bus_dual_fanout_with_pubsub(sample_event):
    """Verify InMemoryEventBus delivers to both local subscribers and Pub/Sub publisher."""
    bus = InMemoryEventBus()

    received_events = []
    subscriber_ready = asyncio.Event()

    async def _subscriber():
        subscriber_ready.set()
        async for evt in bus.subscribe(sample_event.job_id):
            received_events.append(evt)
            if len(received_events) >= 1:
                break

    sub_task = asyncio.create_task(_subscriber())
    await subscriber_ready.wait()
    await asyncio.sleep(0.01)

    with patch("app.services.pubsub_publisher.pubsub_publisher.publish_event", new_callable=AsyncMock) as mock_pub:
        mock_pub.return_value = True
        await bus.publish(sample_event)
        await asyncio.sleep(0.05)

        # 1. In-memory queue received event
        assert len(received_events) == 1
        assert received_events[0].event_id == sample_event.event_id

        # 2. History recorded event
        history = bus.get_history(sample_event.job_id)
        assert len(history) == 1

        # 3. Pub/Sub publisher was called
        mock_pub.assert_called_once()

    await sub_task
