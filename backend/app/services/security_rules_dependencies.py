import json
import re
import subprocess
from pathlib import Path
from typing import Optional

from app.services.security_rules import SecurityRule, Finding, registry


class DependencyVulnerabilityRule(SecurityRule):
    """Check dependencies for known vulnerabilities using OSV or similar."""

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
        return "medium"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []

        # Only check manifest files
        filename = Path(file_path).name.lower()
        if filename not in ('requirements.txt', 'pyproject.toml', 'package.json', 'pom.xml', 'build.gradle', 'go.mod', 'cargo.toml'):
            return findings

        # For now, just check for known vulnerable patterns
        # In production, integrate with OSV, GitHub Advisory, etc.
        lines = content.splitlines()

        # Known vulnerable packages (examples - would come from advisory DB)
        vulnerable_patterns = {
            "requirements.txt": [
                (r'django==([0-9]+\.[0-9]+\.[0-9]+)', self._check_django_version),
                (r'requests==([0-9]+\.[0-9]+\.[0-9]+)', self._check_requests_version),
                (r'urllib3==([0-9]+\.[0-9]+\.[0-9]+)', self._check_urllib3_version),
            ],
            "package.json": [
                (r'"lodash"\s*:\s*"([^"]+)"', self._check_lodash_version),
                (r'"axios"\s*:\s*"([^"]+)"', self._check_axios_version),
            ],
        }

        patterns = vulnerable_patterns.get(filename, [])
        for i, line in enumerate(lines):
            line_num = i + 1
            for pattern, checker in patterns:
                match = re.search(pattern, line)
                if match:
                    version = match.group(1)
                    result = checker(version)
                    if result:
                        findings.append(self._create_finding(
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            evidence=line.strip()[:200],
                            explanation=result['explanation'],
                            remediation=result['remediation'],
                            references=result.get('references', []),
                        ))

        return findings

    def _check_django_version(self, version: str) -> Optional[dict]:
        # Django < 4.2 has known issues
        try:
            major, minor, patch = map(int, version.split('.')[:3])
            if major < 4 or (major == 4 and minor < 2):
                return {
                    'explanation': f'Django {version} is outdated. Versions before 4.2.x may have unpatched vulnerabilities.',
                    'remediation': 'Upgrade Django to 4.2.x or later.',
                    'references': ['https://www.djangoproject.com/download/'],
                }
        except ValueError:
            pass
        return None

    def _check_requests_version(self, version: str) -> Optional[dict]:
        try:
            major, minor, patch = map(int, version.split('.')[:3])
            if major < 2 or (major == 2 and minor < 28):
                return {
                    'explanation': f'requests {version} may have vulnerabilities. Version 2.28+ recommended.',
                    'remediation': 'Upgrade requests to 2.28.1 or later.',
                }
        except ValueError:
            pass
        return None

    def _check_urllib3_version(self, version: str) -> Optional[dict]:
        try:
            major, minor, patch = map(int, version.split('.')[:3])
            if major < 1 or (major == 1 and minor < 26):
                return {
                    'explanation': f'urllib3 {version} may have vulnerabilities. Version 1.26+ recommended.',
                    'remediation': 'Upgrade urllib3 to 1.26.15 or later.',
                }
        except ValueError:
            pass
        return None

    def _check_lodash_version(self, version: str) -> Optional[dict]:
        # Remove ^, ~, etc.
        clean_version = version.lstrip('^~')
        try:
            major, minor, patch = map(int, clean_version.split('.')[:3])
            if major < 4 or (major == 4 and minor < 17):
                return {
                    'explanation': f'lodash {version} has known prototype pollution vulnerabilities.',
                    'remediation': 'Upgrade lodash to 4.17.21 or later.',
                    'references': ['https://github.com/lodash/lodash/wiki/Changelog'],
                }
        except ValueError:
            pass
        return None

    def _check_axios_version(self, version: str) -> Optional[dict]:
        clean_version = version.lstrip('^~')
        try:
            major, minor, patch = map(int, clean_version.split('.')[:3])
            if major < 1 or (major == 1 and minor < 6):
                return {
                    'explanation': f'axios {version} may have vulnerabilities.',
                    'remediation': 'Upgrade axios to 1.6.0 or later.',
                }
        except ValueError:
            pass
        return None


class OutdatedDependencyRule(SecurityRule):
    """Flag significantly outdated dependencies."""

    @property
    def rule_id(self) -> str:
        return "DEP_OUTDATED"

    @property
    def title(self) -> str:
        return "Significantly Outdated Dependency"

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
        # This would ideally check against a package index
        # For now, return empty - requires external API
        return []


# Register dependency rules
registry.register(DependencyVulnerabilityRule())
registry.register(OutdatedDependencyRule())