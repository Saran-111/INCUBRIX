import os
from pathlib import Path
from typing import Dict, List, Optional, Type
import yaml
from app.connectors.base import BaseConnector
from app.connectors.implementations.discourse import DiscourseConnector
from app.connectors.implementations.lemmy import LemmyConnector
from app.connectors.implementations.devto import DevToConnector
from app.connectors.implementations.ghost import GhostConnector
from app.connectors.implementations.webhook_hmac import WebhookHmacConnector
from app.connectors.implementations.assisted import AssistedConnector
from app.connectors.implementations.hashnode import HashnodeConnector
from app.connectors.implementations.slack import SlackConnector
from app.connectors.implementations.mailchimp import MailchimpConnector
from app.core.errors import ErrorCodes, IncubrixAPIException

CONNECTOR_CLASSES: Dict[str, Type[BaseConnector]] = {
    "discourse": DiscourseConnector,
    "lemmy": LemmyConnector,
    "devto": DevToConnector,
    "ghost": GhostConnector,
    "webhook_hmac": WebhookHmacConnector,
    "assisted": AssistedConnector,
    "hashnode": HashnodeConnector,
    "slack": SlackConnector,
    "mailchimp": MailchimpConnector,
}

class ConnectorRegistry:
    def __init__(self):
        self._connectors: Dict[str, BaseConnector] = {}
        self._manifests: Dict[str, dict] = {}
        self._disabled: Dict[str, bool] = {}
        self._manifest_dir = Path(__file__).parent / "manifests"
        self._load_all()

    def _load_all(self):
        if not self._manifest_dir.exists():
            return

        for manifest_file in self._manifest_dir.glob("*.yaml"):
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                key = data.get("key")
                if not key:
                    continue
                self._manifests[key] = data
                self._disabled[key] = False
                
                cls = CONNECTOR_CLASSES.get(key)
                if cls:
                    self._connectors[key] = cls(key=key, manifest_data=data)

    def get(self, connector_key: str) -> BaseConnector:
        if connector_key not in self._connectors:
            raise IncubrixAPIException(
                code=ErrorCodes.CONNECTOR_NOT_FOUND,
                message=f"Connector '{connector_key}' is not registered.",
                retryable=False,
                status_code=404
            )
        if self._disabled.get(connector_key, False):
            raise IncubrixAPIException(
                code=ErrorCodes.CONNECTOR_DISABLED,
                message=f"Connector '{connector_key}' is disabled via kill-switch.",
                retryable=False,
                status_code=403
            )
        return self._connectors[connector_key]

    def get_manifest(self, connector_key: str) -> dict:
        if connector_key not in self._manifests:
            raise IncubrixAPIException(
                code=ErrorCodes.CONNECTOR_NOT_FOUND,
                message=f"Manifest for connector '{connector_key}' not found.",
                retryable=False,
                status_code=404
            )
        return self._manifests[connector_key]

    def list_all(self) -> List[dict]:
        return list(self._manifests.values())

    def set_disabled(self, connector_key: str, disabled: bool):
        """Allows toggling connector kill switch for testing."""
        if connector_key in self._disabled:
            self._disabled[connector_key] = disabled

connector_registry = ConnectorRegistry()
