import asyncio
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.catalogue.importer import catalogue_store
from app.certification.harness import certification_harness
from app.core.logging import logger

class RecertificationTicket(BaseModel):
    ticket_id: str
    destination_name: str
    destination_url: str
    connector_key: str
    failure_reason: str
    severity: str = "HIGH"
    status: str = "OPEN"
    created_at: str

class RecertificationSummary(BaseModel):
    total_inspected: int
    recertified_count: int
    demoted_count: int
    tickets_created: List[RecertificationTicket]

class RecertificationScheduler:
    def __init__(self, max_age_days: int = 30):
        self.max_age_days = max_age_days
        self.tickets: List[RecertificationTicket] = []

    async def run_recertification_cycle(self, force_all: bool = False) -> RecertificationSummary:
        destinations = await catalogue_store.list_all()
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=self.max_age_days)

        recertified = 0
        demoted = 0
        new_tickets = []

        for dest in destinations:
            needs_test = force_all
            if not needs_test:
                if not dest.last_certified_at:
                    needs_test = True
                else:
                    try:
                        cert_time = datetime.fromisoformat(dest.last_certified_at)
                        if cert_time < threshold:
                            needs_test = True
                    except Exception:
                        needs_test = True

            if needs_test:
                evidence = await certification_harness.certify_destination(dest)
                if evidence.verdict == "PASSED":
                    recertified += 1
                else:
                    demoted += 1
                    ticket = RecertificationTicket(
                        ticket_id=f"TICK_{uuid.uuid4().hex[:8].upper()}",
                        destination_name=dest.name,
                        destination_url=dest.url,
                        connector_key=dest.connector_key,
                        failure_reason=evidence.error_details or "Probe failed verification",
                        severity="HIGH",
                        status="OPEN",
                        created_at=datetime.now(timezone.utc).isoformat()
                    )
                    self.tickets.append(ticket)
                    new_tickets.append(ticket)
                    logger.warning(
                        f"ALERT: Destination {dest.name} demoted to L0. Ticket {ticket.ticket_id} created."
                    )

        return RecertificationSummary(
            total_inspected=len(destinations),
            recertified_count=recertified,
            demoted_count=demoted,
            tickets_created=new_tickets
        )

recertification_scheduler = RecertificationScheduler()
