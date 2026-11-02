import re
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Finding:
    """A security finding."""
    rule_id: str
    title: str
    category: str  # secrets, dangerous_code, dependencies, infrastructure, configuration
    severity: str  # critical, high, medium, low, info
    confidence: str  # high, medium, low
    file_path: str
    start_line: int
    end_line: int
    evidence: str
    explanation: str
    remediation: str
    references: list[str] = field(default_factory=list)


class SecurityRule(ABC):
    """Abstract base class for security rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        pass

    @property
    @abstractmethod
    def title(self) -> str:
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        pass

    @property
    @abstractmethod
    def severity(self) -> str:
        pass

    @property
    @abstractmethod
    def confidence(self) -> str:
        pass

    @abstractmethod
    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        """Check a file for violations. Return list of findings."""
        pass

    def _create_finding(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        evidence: str,
        explanation: str = None,
        remediation: str = None,
        references: list[str] = None,
    ) -> Finding:
        """Create a finding with standard fields."""
        # Redact sensitive evidence
        redacted_evidence = self._redact_secrets(evidence)

        return Finding(
            rule_id=self.rule_id,
            title=self.title,
            category=self.category,
            severity=self.severity,
            confidence=self.confidence,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            evidence=redacted_evidence,
            explanation=explanation or f"Violation of {self.rule_id}: {self.title}",
            remediation=remediation or "Review and remediate the identified issue.",
            references=references or [],
        )

    def _redact_secrets(self, text: str) -> str:
        """Redact potential secrets from evidence."""
        # Redact common secret patterns
        patterns = [
            (r'(?i)(api[_-]?key|secret|password|token|credential)[\s:=]+["\']?([a-zA-Z0-9_\-+=/\.]{8,})["\']?', r'\1=***REDACTED***'),
            (r'(?i)(aws[_-]?access[_-]?key[_-]?id)[\s:=]+["\']?([A-Z0-9]{16,})["\']?', r'\1=***REDACTED***'),
            (r'(?i)(aws[_-]?secret[_-]?access[_-]?key)[\s:=]+["\']?([a-zA-Z0-9/+]{40,})["\']?', r'\1=***REDACTED***'),
            (r'gh[pousr]_[a-zA-Z0-9]{36,}', 'gh*_***REDACTED***'),
            (r'sk-[a-zA-Z0-9]{48,}', 'sk-***REDACTED***'),
            (r'xox[baprs]-[a-zA-Z0-9-]{10,}', 'xox*_***REDACTED***'),
        ]

        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)

        return text


class RuleRegistry:
    """Registry for security rules."""

    def __init__(self):
        self._rules: list[SecurityRule] = []

    def register(self, rule: SecurityRule):
        self._rules.append(rule)
        logger.debug("rule_registered", rule_id=rule.rule_id)

    def get_all(self) -> list[SecurityRule]:
        return self._rules

    def get_by_category(self, category: str) -> list[SecurityRule]:
        return [r for r in self._rules if r.category == category]

    def get_by_id(self, rule_id: str) -> Optional[SecurityRule]:
        for rule in self._rules:
            if rule.rule_id == rule_id:
                return rule
        return None


# Global registry
registry = RuleRegistry()


def get_registry() -> RuleRegistry:
    return registry


# Import all rule modules to register them
from app.services import security_rules_secrets  # noqa: F401
from app.services import security_rules_dangerous  # noqa: F401
from app.services import security_rules_dependencies  # noqa: F401
from app.services import security_rules_infrastructure  # noqa: F401