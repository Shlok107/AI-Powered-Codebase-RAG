"""Dependency advisory checks using exact versions and the OSV query API.

Only resolved versions are reported. Version ranges that cannot be resolved from
a lock file are skipped instead of being guessed from a simple version floor.
"""

from __future__ import annotations

import json
import re
import time
import tomllib
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.security_rules import Finding, SecurityRule, registry

logger = get_logger(__name__)

_REQUIREMENT = re.compile(
    r"^\s*([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*==\s*([A-Za-z0-9][A-Za-z0-9.+!_-]*)\s*(?:;.*)?$"
)
_EXACT_VERSION = re.compile(r"^v?[0-9]+(?:\.[0-9A-Za-z_-]+)+(?:\+[0-9A-Za-z.-]+)?$")
_ALLOWED_REFERENCE_HOSTS = {
    "osv.dev", "github.com", "nvd.nist.gov", "cve.org", "pypi.org", "npmjs.com",
    "www.npmjs.com", "rustsec.org", "pkg.go.dev",
}


@dataclass(frozen=True)
class Dependency:
    ecosystem: str
    name: str
    version: str
    line: int


def _line_for(content: str, *needles: str) -> int:
    for line_number, line in enumerate(content.splitlines(), start=1):
        if all(needle in line for needle in needles):
            return line_number
    return 1


def _deduplicate(dependencies: list[Dependency]) -> list[Dependency]:
    unique: dict[tuple[str, str, str], Dependency] = {}
    for dependency in dependencies:
        key = (dependency.ecosystem, dependency.name.lower(), dependency.version)
        unique.setdefault(key, dependency)
    return list(unique.values())


def parse_dependency_manifest(file_path: str, content: str) -> tuple[list[Dependency], bool]:
    """Return exact resolved dependency versions and whether parsing was incomplete."""
    filename = Path(file_path).name.lower()
    dependencies: list[Dependency] = []

    if filename in {"requirements.txt", "requirements-dev.txt"}:
        for line_number, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "-")):
                continue
            match = _REQUIREMENT.match(line)
            if match:
                dependencies.append(Dependency("PyPI", match.group(1), match.group(2), line_number))
        return dependencies, False

    if filename in {"package-lock.json", "npm-shrinkwrap.json"}:
        try:
            lock = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return [], True
        packages = lock.get("packages")
        if isinstance(packages, dict):
            for install_path, details in packages.items():
                if not install_path or not isinstance(details, dict):
                    continue
                name = details.get("name") or install_path.rsplit("node_modules/", 1)[-1]
                version = details.get("version")
                if isinstance(name, str) and isinstance(version, str) and _EXACT_VERSION.match(version):
                    dependencies.append(
                        Dependency("npm", name, version, _line_for(content, f'"{install_path}"'))
                    )
        else:
            def visit(entries: Any) -> None:
                if not isinstance(entries, dict):
                    return
                for name, details in entries.items():
                    if not isinstance(details, dict):
                        continue
                    version = details.get("version")
                    if isinstance(version, str) and _EXACT_VERSION.match(version):
                        dependencies.append(Dependency("npm", name, version, _line_for(content, f'"{name}"')))
                    visit(details.get("dependencies"))

            visit(lock.get("dependencies"))
        return _deduplicate(dependencies), False

    if filename in {"pyproject.toml", "poetry.lock", "uv.lock", "cargo.lock"}:
        try:
            document = tomllib.loads(content)
        except (tomllib.TOMLDecodeError, TypeError):
            return [], True
        if filename == "pyproject.toml":
            for requirement in document.get("project", {}).get("dependencies", []):
                if not isinstance(requirement, str):
                    continue
                match = _REQUIREMENT.match(requirement.strip().strip("\"'"))
                if match:
                    dependencies.append(
                        Dependency("PyPI", match.group(1), match.group(2), _line_for(content, requirement))
                    )
            return dependencies, False

        ecosystem = "crates.io" if filename == "cargo.lock" else "PyPI"
        for package in document.get("package", []):
            name, version = package.get("name"), package.get("version")
            if isinstance(name, str) and isinstance(version, str) and _EXACT_VERSION.match(version):
                dependencies.append(
                    Dependency(
                        ecosystem,
                        name,
                        version,
                        _line_for(content, f'name = "{name}"', f'version = "{version}"'),
                    )
                )
        return _deduplicate(dependencies), False

    if filename == "go.mod":
        inside_require_block = False
        for line_number, line in enumerate(content.splitlines(), start=1):
            stripped = line.split("//", 1)[0].strip()
            if stripped.startswith("require ("):
                inside_require_block = True
                continue
            if inside_require_block and stripped == ")":
                inside_require_block = False
                continue
            match = re.match(r"(?:require\s+)?([^\s]+)\s+(v[0-9][^\s]+)", stripped)
            if match and (inside_require_block or stripped.startswith("require ")):
                dependencies.append(Dependency("Go", match.group(1), match.group(2), line_number))
        return _deduplicate(dependencies), False

    return [], False


class OsvAdvisoryClient:
    """Batched OSV client with a process-local cache and bounded work per scan."""

    CACHE_SECONDS = 6 * 60 * 60
    BATCH_SIZE = 1000

    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        max_queries: Optional[int] = None,
        max_advisories: Optional[int] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        settings = get_settings()
        self.endpoint = endpoint or settings.osv_api_url
        self.timeout_seconds = timeout_seconds or settings.osv_timeout_seconds
        self.max_queries = max_queries or settings.max_dependency_queries
        self.max_advisories = max_advisories or settings.max_dependency_advisories
        self.transport = transport
        self._cache: dict[tuple[str, str, str], tuple[float, list[dict[str, Any]]]] = {}
        self._advisory_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    async def lookup(
        self, dependencies: list[Dependency]
    ) -> tuple[dict[tuple[str, str, str], list[dict[str, Any]]], bool, bool]:
        """Return matches, advisory-service availability and query-truncation status."""
        unique = _deduplicate(dependencies)
        truncated = len(unique) > self.max_queries
        dependencies_to_check = unique[: self.max_queries]
        now = time.monotonic()
        results: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        uncached: list[Dependency] = []

        for dependency in dependencies_to_check:
            key = (dependency.ecosystem, dependency.name.lower(), dependency.version)
            cached = self._cache.get(key)
            if cached and cached[0] > now:
                results[key] = cached[1]
            else:
                uncached.append(dependency)

        unavailable = False
        advisory_ids_by_package: dict[tuple[str, str, str], list[str]] = {}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                for start in range(0, len(uncached), self.BATCH_SIZE):
                    batch = uncached[start : start + self.BATCH_SIZE]
                    payload = {
                        "queries": [
                            {"package": {"name": dep.name, "ecosystem": dep.ecosystem}, "version": dep.version}
                            for dep in batch
                        ]
                    }
                    response = await client.post(self.endpoint, json=payload)
                    response.raise_for_status()
                    batch_results = response.json()["results"]
                    if not isinstance(batch_results, list) or len(batch_results) != len(batch):
                        raise ValueError("OSV returned an invalid batch response")
                    for dependency, item in zip(batch, batch_results):
                        if not isinstance(item, dict):
                            raise ValueError("OSV returned an invalid package result")
                        vulns = item.get("vulns", [])
                        if not isinstance(vulns, list):
                            raise ValueError("OSV returned an invalid vulnerability list")
                        key = (dependency.ecosystem, dependency.name.lower(), dependency.version)
                        advisory_ids = []
                        for vuln in vulns:
                            if (
                                not isinstance(vuln, dict)
                                or not isinstance(vuln.get("id"), str)
                                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", vuln["id"])
                            ):
                                raise ValueError("OSV returned an invalid advisory identifier")
                            advisory_ids.append(vuln["id"])
                        advisory_ids_by_package[key] = advisory_ids
                        if item.get("next_page_token"):
                            truncated = True

            unique_ids = list(dict.fromkeys(
                advisory_id
                for advisory_ids in advisory_ids_by_package.values()
                for advisory_id in advisory_ids
            ))
            if len(unique_ids) > self.max_advisories:
                unique_ids = unique_ids[: self.max_advisories]
                truncated = True

            details_by_id: dict[str, dict[str, Any]] = {}
            ids_to_fetch: list[str] = []
            for advisory_id in unique_ids:
                cached_detail = self._advisory_cache.get(advisory_id)
                if cached_detail and cached_detail[0] > now:
                    details_by_id[advisory_id] = cached_detail[1]
                else:
                    ids_to_fetch.append(advisory_id)

            semaphore = asyncio.Semaphore(20)

            async def fetch_detail(client: httpx.AsyncClient, advisory_id: str):
                async with semaphore:
                    detail_url = self.endpoint.rsplit("/querybatch", 1)[0] + "/vulns/" + quote(advisory_id, safe="")
                    detail_response = await client.get(detail_url)
                    detail_response.raise_for_status()
                    detail = detail_response.json()
                    if not isinstance(detail, dict) or detail.get("id") != advisory_id:
                        raise ValueError("OSV returned an invalid advisory detail")
                    return advisory_id, detail

            if ids_to_fetch:
                async with httpx.AsyncClient(
                    timeout=self.timeout_seconds,
                    transport=self.transport,
                    follow_redirects=False,
                ) as client:
                    detail_responses = await asyncio.gather(
                        *(fetch_detail(client, advisory_id) for advisory_id in ids_to_fetch),
                        return_exceptions=True,
                    )
                for item in detail_responses:
                    if isinstance(item, BaseException):
                        unavailable = True
                        logger.warning("osv_advisory_detail_unavailable", error_type=type(item).__name__)
                        continue
                    advisory_id, detail = item
                    details_by_id[advisory_id] = detail
                    self._advisory_cache[advisory_id] = (now + self.CACHE_SECONDS, detail)

            for key, advisory_ids in advisory_ids_by_package.items():
                details = [details_by_id[advisory_id] for advisory_id in advisory_ids if advisory_id in details_by_id]
                results[key] = details
                self._cache[key] = (now + self.CACHE_SECONDS, details)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            unavailable = True
            logger.warning("osv_advisory_lookup_unavailable", error_type=type(exc).__name__)

        return results, unavailable, truncated


class DependencyVulnerabilityRule(SecurityRule):
    """Match exact resolved package versions against OSV advisories."""

    def __init__(self, client: Optional[OsvAdvisoryClient] = None) -> None:
        self.client = client or OsvAdvisoryClient()

    @property
    def rule_id(self) -> str:
        return "DEP_VULNERABLE"

    @property
    def title(self) -> str:
        return "Dependency with Known Vulnerability"

    @property
    def category(self) -> str:
        return "dependencies"

    @property
    def severity(self) -> str:
        return "high"

    @property
    def confidence(self) -> str:
        return "high"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        # Network advisory lookup is async and is called by SecurityScanner.
        return []

    async def check_with_status(self, file_path: str, content: str) -> tuple[list[Finding], bool, bool]:
        dependencies, parse_incomplete = parse_dependency_manifest(file_path, content)
        if not dependencies:
            return [], parse_incomplete, False

        advisories, service_unavailable, truncated = await self.client.lookup(dependencies)
        findings: list[Finding] = []
        for dependency in dependencies:
            key = (dependency.ecosystem, dependency.name.lower(), dependency.version)
            for advisory in advisories.get(key, []):
                if not isinstance(advisory, dict):
                    continue
                advisory_id = str(advisory.get("id") or "OSV advisory")[:100]
                summary = str(advisory.get("summary") or advisory.get("details") or "Known affected version")
                summary = " ".join(summary.split())[:500]
                references = []
                for ref in advisory.get("references", []):
                    if not isinstance(ref, dict) or not isinstance(ref.get("url"), str):
                        continue
                    parsed_url = urlparse(ref["url"])
                    if parsed_url.scheme == "https" and parsed_url.hostname in _ALLOWED_REFERENCE_HOSTS:
                        references.append(ref["url"][:500])
                if not references:
                    references = [f"https://osv.dev/vulnerability/{quote(advisory_id, safe='')}" ]

                findings.append(
                    self._create_finding(
                        file_path=file_path,
                        start_line=dependency.line,
                        end_line=dependency.line,
                        evidence=f"{dependency.name}=={dependency.version}",
                        explanation=f"OSV advisory {advisory_id}: {summary}",
                        remediation="Upgrade to a version identified as fixed by this advisory, then regenerate and commit the dependency lock file.",
                        references=references[:10],
                        finding_title=f"{dependency.name} {dependency.version} has known advisory {advisory_id}",
                        finding_severity=self._severity(advisory),
                        finding_confidence="high",
                    )
                )
        return findings, parse_incomplete or service_unavailable, truncated

    @staticmethod
    def _severity(advisory: dict[str, Any]) -> str:
        database_specific = advisory.get("database_specific", {})
        label = str(database_specific.get("severity", "")).lower() if isinstance(database_specific, dict) else ""
        if label in {"critical", "high", "medium", "low"}:
            return label
        scores = advisory.get("severity", [])
        if isinstance(scores, list):
            for item in scores:
                if isinstance(item, dict):
                    score_text = str(item.get("score", ""))
                    numeric = re.search(r"(?:^|/)([0-9]+(?:\.[0-9]+)?)(?:$|/)", score_text)
                    if numeric:
                        score = float(numeric.group(1))
                        if score >= 9.0:
                            return "critical"
                        if score >= 7.0:
                            return "high"
                        if score >= 4.0:
                            return "medium"
                        return "low"
        return "medium"


class OutdatedDependencyRule(SecurityRule):
    """Keep the legacy rule id without guessing what "latest" means."""

    @property
    def rule_id(self) -> str:
        return "DEP_OUTDATED"

    @property
    def title(self) -> str:
        return "Outdated Dependency"

    @property
    def category(self) -> str:
        return "dependencies"

    @property
    def severity(self) -> str:
        return "low"

    @property
    def confidence(self) -> str:
        return "low"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        # OSV describes known vulnerabilities; it is not a package-currentness feed.
        return []


registry.register(DependencyVulnerabilityRule())
registry.register(OutdatedDependencyRule())
