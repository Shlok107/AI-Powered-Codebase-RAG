import re
from pathlib import Path
from typing import Optional

from app.services.security_rules import SecurityRule, Finding, registry


class HardcodedSecretRule(SecurityRule):
    """Detect hardcoded secrets, API keys, passwords, tokens."""

    @property
    def rule_id(self) -> str:
        return "SECRET_HARDCODED"

    @property
    def title(self) -> str:
        return "Hardcoded Secret Detected"

    @property
    def category(self) -> str:
        return "secrets"

    @property
    def severity(self) -> str:
        return "critical"

    @property
    def confidence(self) -> str:
        return "high"

    # Common secret patterns
    SECRET_PATTERNS = [
        # Generic API keys
        (r'(?i)(api[_-]?key|apikey)[\s:=]+["\']?([a-zA-Z0-9_\-+=/\.]{16,})["\']?', "API Key"),
        # AWS
        (r'(?i)(aws[_-]?access[_-]?key[_-]?id)[\s:=]+["\']?([A-Z0-9]{16,})["\']?', "AWS Access Key ID"),
        (r'(?i)(aws[_-]?secret[_-]?access[_-]?key)[\s:=]+["\']?([a-zA-Z0-9/+]{40,})["\']?', "AWS Secret Access Key"),
        # GitHub
        (r'gh[pousr]_[a-zA-Z0-9]{36,}', "GitHub Token"),
        # OpenAI
        (r'sk-[a-zA-Z0-9]{48,}', "OpenAI API Key"),
        # Slack
        (r'xox[baprs]-[a-zA-Z0-9-]{10,}', "Slack Token"),
        # Generic tokens
        (r'(?i)(access[_-]?token|auth[_-]?token|bearer[_-]?token)[\s:=]+["\']?([a-zA-Z0-9_\-+=/\.]{20,})["\']?', "Access Token"),
        # Database passwords
        (r'(?i)(database[_-]?password|db[_-]?password|dbpass)[\s:=]+["\']?([a-zA-Z0-9_\-+=/\.!@#$%^&*]{8,})["\']?', "Database Password"),
        # Private keys
        (r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', "Private Key"),
        # JWT
        (r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', "JWT Token"),
    ]

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            for pattern, secret_type in self.SECRET_PATTERNS:
                matches = list(re.finditer(pattern, line))
                for match in matches:
                    # Skip if it's in a comment that looks like an example
                    if self._is_example_or_test(line, file_path):
                        continue

                    evidence = line.strip()[:200]
                    finding = self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=evidence,
                        explanation=f"Hardcoded {secret_type} detected in source code. This secret could be exposed if the code is committed to a repository.",
                        remediation=f"Remove the {secret_type} from source code. Use environment variables or a secrets manager instead.",
                        references=[
                            "https://owasp.org/www-project-top-ten/2021/A07_2021-Identification_and_Authentication_Failures",
                            "https://cwe.mitre.org/data/definitions/798.html",
                        ],
                    )
                    findings.append(finding)

        return findings

    def _is_example_or_test(self, line: str, file_path: str) -> bool:
        """Check if line appears to be an example/test."""
        line_lower = line.lower()
        # Common test/example indicators
        if any(keyword in line_lower for keyword in [
            'example', 'mock', 'fake', 'dummy', 'placeholder',
            'your_key', 'your_token', 'your_secret', 'changeme', 'replace_me',
            'xxxx', '****', '*****', 'secret_here', 'token_here',
        ]):
            return True

        # Check if in test file (more specific check)
        if any(part in file_path.lower() for part in ['/test/', '/tests/', '__test__', '.test.', 'spec.', '_test.']):
            return True

        return False


class HardcodedPasswordRule(SecurityRule):
    """Detect hardcoded passwords in config/connection strings."""

    @property
    def rule_id(self) -> str:
        return "SECRET_PASSWORD"

    @property
    def title(self) -> str:
        return "Hardcoded Password in Configuration"

    @property
    def category(self) -> str:
        return "secrets"

    @property
    def severity(self) -> str:
        return "high"

    @property
    def confidence(self) -> str:
        return "medium"

    PASSWORD_PATTERNS = [
        (r'(?i)password[\s:=]+["\']([^"\']{4,})["\']', "Password"),
        (r'(?i)pwd[\s:=]+["\']([^"\']{4,})["\']', "Password"),
        (r'(?i)passwd[\s:=]+["\']([^"\']{4,})["\']', "Password"),
        # Connection strings
        (r'(?i)(mongodb|postgres|mysql|redis)://[^:]+:([^@]+)@', "Connection String Password"),
    ]

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            for pattern, secret_type in self.PASSWORD_PATTERNS:
                matches = list(re.finditer(pattern, line))
                for match in matches:
                    # Skip obvious placeholders
                    matched = match.group(1) if match.groups() else match.group(0)
                    if self._is_placeholder(matched):
                        continue

                    evidence = line.strip()[:200]
                    finding = self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=evidence,
                        explanation=f"Hardcoded {secret_type} detected in configuration. This password could be exposed if the config is committed.",
                        remediation=f"Remove the {secret_type} from config files. Use environment variables or a secrets manager.",
                        references=[
                            "https://cwe.mitre.org/data/definitions/798.html",
                        ],
                    )
                    findings.append(finding)

        return findings

    def _is_placeholder(self, text: str) -> bool:
        placeholders = ['changeme', 'password', 'secret', 'xxx', '***', 'replace', 'your_password', 'your_secret']
        return any(p in text.lower() for p in placeholders)


# Register secret rules
registry.register(HardcodedSecretRule())
registry.register(HardcodedPasswordRule())