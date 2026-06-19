"""Base classes for job discovery providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class JobResult:
    title: str
    company: str
    location: str | None = None
    url: str | None = None
    description: str | None = None
    requirements: list[str] = field(default_factory=list)
    job_type: str = "full_time"
    remote_type: str = "hybrid"
    salary_min: int | None = None
    salary_max: int | None = None
    source: str = "unknown"
    external_id: str | None = None
    deadline: str | None = None

    def dedup_key(self) -> str:
        """Stable key for deduplication across sources."""
        t = self.title.lower().strip()
        c = self.company.lower().strip()
        return f"{t}|{c}"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "description": self.description,
            "requirements": self.requirements,
            "job_type": self.job_type,
            "remote_type": self.remote_type,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "source": self.source,
            "external_id": self.external_id,
            "deadline": self.deadline,
        }


class BaseJobSource(ABC):
    name: str = "unknown"
    display_name: str = "Unknown"
    requires_api_key: bool = False

    @abstractmethod
    async def search(
        self,
        query: str,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobResult]:
        """Search for jobs matching query. Returns empty list on any error."""
        ...

    def is_available(self) -> bool:
        return True
