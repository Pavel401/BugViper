"""Google Cloud Tasks dispatcher for ingestion jobs."""

import json
import logging
import os
from typing import Optional

from pydantic import BaseModel

from common.job_models import (
    IncrementalPRPayload,
    IncrementalPushPayload,
    IngestionTaskPayload,
)

logger = logging.getLogger(__name__)


class CloudTasksService:
    """Dispatch ingestion tasks to a Cloud Run worker via Cloud Tasks.

    When ``INGESTION_SERVICE_URL`` is not set, ``is_enabled`` is ``False``
    and the main API should fall back to in-process execution.
    """

    def __init__(self):
        self._project = os.environ.get("GCP_PROJECT_ID", "")
        self._location = os.environ.get("GCP_LOCATION", "us-central1")
        self._queue = os.environ.get("CLOUD_TASKS_QUEUE", "ingestion-queue")
        self._service_url = os.environ.get("INGESTION_SERVICE_URL", "")
        self._sa_email = os.environ.get("CLOUD_TASKS_SA_EMAIL", "")

    @property
    def is_enabled(self) -> bool:
        return bool(self._service_url)

    def _dispatch(self, path: str, payload: BaseModel) -> Optional[str]:
        """Create a Cloud Task that POSTs to the ingestion service at *path*.

        Returns the Cloud Task resource name, or ``None`` on failure.
        """
        if not self.is_enabled:
            logger.warning("Cloud Tasks not enabled — INGESTION_SERVICE_URL is unset")
            return None

        # Lazy import so the dependency is only required when Cloud Tasks is active
        from google.cloud import tasks_v2

        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(self._project, self._location, self._queue)

        task_body = json.dumps(payload.model_dump()).encode()
        url = f"{self._service_url.rstrip('/')}{path}"

        task: dict = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": task_body,
            },
            "dispatch_deadline": {"seconds": 1800},  # 30 minutes
        }

        # Add OIDC token for authenticated Cloud Run services
        if self._sa_email:
            task["http_request"]["oidc_token"] = {
                "service_account_email": self._sa_email,
                "audience": self._service_url,
            }

        response = client.create_task(parent=parent, task=task)
        logger.info("Dispatched Cloud Task: %s", response.name)
        return response.name

    def dispatch_ingestion(self, payload: IngestionTaskPayload) -> Optional[str]:
        """Dispatch a full repository ingestion task."""
        return self._dispatch("/tasks/ingest", payload)

    def dispatch_incremental_pr(self, payload: IncrementalPRPayload) -> Optional[str]:
        """Dispatch an incremental PR merge graph-update task."""
        return self._dispatch("/tasks/incremental-pr", payload)

    def dispatch_incremental_push(self, payload: IncrementalPushPayload) -> Optional[str]:
        """Dispatch an incremental direct-push graph-update task."""
        return self._dispatch("/tasks/incremental-push", payload)
