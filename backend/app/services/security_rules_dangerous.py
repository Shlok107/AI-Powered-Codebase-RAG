import re
from pathlib import Path
from typing import Optional

from app.services.security_rules import SecurityRule, Finding, registry


class PythonEvalExecRule(SecurityRule):
    """Detect dangerous use of eval/exec in Python."""

    @property
    def rule_id(self) -> str:
        return "DANGEROUS_EVAL_EXEC"

    @property
    def title(self) -> str:
        return "Use of eval() or exec()"

    @property
    def category(self) -> str:
        return "dangerous_code"

    @property
    def severity(self) -> str:
        return "high"

    @property
    def confidence(self) -> str:
        return "high"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        if language != "python":
            return []

        findings = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            # Check for eval()
            if re.search(r'\beval\s*\(', stripped) and not self._is_comment(stripped):
                findings.append(self._create_finding(
                    file_path=file_path,
                    start_line=line_num,
                    end_line=line_num,
                    evidence=line.strip()[:200],
                    explanation="Use of eval() can execute arbitrary code. If input is user-controlled, this leads to code injection.",
                    remediation="Avoid eval(). Use ast.literal_eval() for safe evaluation of literals, or refactor to avoid dynamic code execution.",
                    references=[
                        "https://cwe.mitre.org/data/definitions/94.html",
                        "https://docs.python.org/3/library/ast.html#ast.literal_eval",
                    ],
                ))

            # Check for exec()
            if re.search(r'\bexec\s*\(', stripped) and not self._is_comment(stripped):
                findings.append(self._create_finding(
                    file_path=file_path,
                    start_line=line_num,
                    end_line=line_num,
                    evidence=line.strip()[:200],
                    explanation="Use of exec() can execute arbitrary code. If input is user-controlled, this leads to code injection.",
                    remediation="Avoid exec(). Refactor to use explicit code or import mechanisms.",
                    references=[
                        "https://cwe.mitre.org/data/definitions/94.html",
                    ],
                ))

        return findings

    def _is_comment(self, line: str) -> bool:
        return line.strip().startswith("#")


class PythonPickleRule(SecurityRule):
    """Detect unsafe pickle usage in Python."""

    @property
    def rule_id(self) -> str:
        return "DANGEROUS_PICKLE"

    @property
    def title(self) -> str:
        return "Unsafe Deserialization with pickle"

    @property
    def category(self) -> str:
        return "dangerous_code"

    @property
    def severity(self) -> str:
        return "critical"

    @property
    def confidence(self) -> str:
        return "high"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        if language != "python":
            return []

        findings = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            # Check for pickle.load(s)
            if re.search(r'\bpickle\.(load|loads)\s*\(', stripped) and not self._is_comment(stripped):
                findings.append(self._create_finding(
                    file_path=file_path,
                    start_line=line_num,
                    end_line=line_num,
                    evidence=line.strip()[:200],
                    explanation="pickle.load() and pickle.loads() can execute arbitrary code during deserialization. Never unpickle untrusted data.",
                    remediation="Use safer serialization formats like JSON. If pickle is required, validate and sign the data before deserialization.",
                    references=[
                        "https://cwe.mitre.org/data/definitions/502.html",
                        "https://docs.python.org/3/library/pickle.html#security",
                    ],
                ))

        return findings

    def _is_comment(self, line: str) -> bool:
        return line.strip().startswith("#")


class PythonSubprocessShellRule(SecurityRule):
    """Detect subprocess with shell=True in Python."""

    @property
    def rule_id(self) -> str:
        return "DANGEROUS_SUBPROCESS_SHELL"

    @property
    def title(self) -> str:
        return "Subprocess with shell=True"

    @property
    def category(self) -> str:
        return "dangerous_code"

    @property
    def severity(self) -> str:
        return "high"

    @property
    def confidence(self) -> str:
        return "medium"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        if language != "python":
            return []

        findings = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            # Check for subprocess.run/call/Popen with shell=True
            if re.search(r'\b(subprocess\.(run|call|Popen))\s*\([^)]*\bshell\s*=\s*True', stripped):
                if not self._is_comment(stripped):
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation="Using shell=True with subprocess allows shell injection if any arguments are user-controlled.",
                        remediation="Avoid shell=True. Pass arguments as a list: subprocess.run(['cmd', 'arg1', 'arg2']).",
                        references=[
                            "https://cwe.mitre.org/data/definitions/78.html",
                            "https://docs.python.org/3/library/subprocess.html#security-considerations",
                        ],
                    ))

        return findings

    def _is_comment(self, line: str) -> bool:
        return line.strip().startswith("#")


class SQLInjectionRule(SecurityRule):
    """Detect potential SQL injection via string concatenation."""

    @property
    def rule_id(self) -> str:
        return "DANGEROUS_SQL_INJECTION"

    @property
    def title(self) -> str:
        return "Potential SQL Injection via String Concatenation"

    @property
    def category(self) -> str:
        return "dangerous_code"

    @property
    def severity(self) -> str:
        return "high"

    @property
    def confidence(self) -> str:
        return "medium"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            if language == "python":
                # Check for string formatting with % (not parameterized query placeholders)
                # Pattern: cursor.execute("... %s ..." % var) or cursor.execute("... %s ..." % (var,))
                if re.search(r'(?i)\.execute\s*\(\s*["\'].*%s.*["\']\s*%', stripped) and not self._is_comment(stripped, language):
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation="SQL query uses string formatting (%) with execute(). This is not parameterized and enables SQL injection.",
                        remediation="Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,)).",
                        references=[
                            "https://cwe.mitre.org/data/definitions/89.html",
                            "https://owasp.org/www-community/attacks/SQL_Injection",
                        ],
                    ))

                # Check for string concatenation with +
                if re.search(r'(?i)\.execute\s*\(\s*["\'].*\+.*["\']', stripped) and not self._is_comment(stripped, language):
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation="SQL query built via string concatenation (+). If variables are user-controlled, this enables SQL injection.",
                        remediation="Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,)).",
                        references=[
                            "https://cwe.mitre.org/data/definitions/89.html",
                            "https://owasp.org/www-community/attacks/SQL_Injection",
                        ],
                    ))

                # Check for executemany with string formatting
                if re.search(r'(?i)\.executemany\s*\(\s*["\'].*%s.*["\']\s*%', stripped) and not self._is_comment(stripped, language):
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation="SQL query uses string formatting (%) with executemany(). This is not parameterized and enables SQL injection.",
                        remediation="Use parameterized queries with executemany().",
                        references=[
                            "https://cwe.mitre.org/data/definitions/89.html",
                        ],
                    ))

            elif language in ("javascript", "typescript"):
                # Template literals
                if re.search(r'(?i)\.query\s*\(\s*[`"\'].*\$\{.*\}', stripped) and not self._is_comment(stripped, language):
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation="SQL query uses template literal interpolation. This enables SQL injection if variables are user-controlled.",
                        remediation="Use parameterized queries with placeholders.",
                        references=[
                            "https://cwe.mitre.org/data/definitions/89.html",
                        ],
                    ))
                # String concatenation
                if re.search(r'(?i)\.query\s*\(\s*[`"\'].*\+.*', stripped) and not self._is_comment(stripped, language):
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation="SQL query uses string concatenation. This enables SQL injection.",
                        remediation="Use parameterized queries.",
                        references=[
                            "https://cwe.mitre.org/data/definitions/89.html",
                        ],
                    ))

        return findings

    def _is_comment(self, line: str, language: str) -> bool:
        stripped = line.strip()
        if language == "python":
            return stripped.startswith("#")
        elif language in ("javascript", "typescript", "java", "c", "cpp", "go"):
            return stripped.startswith("//") or stripped.startswith("/*")
        return False


class PathTraversalRule(SecurityRule):
    """Detect potential path traversal vulnerabilities."""

    @property
    def rule_id(self) -> str:
        return "DANGEROUS_PATH_TRAVERSAL"

    @property
    def title(self) -> str:
        return "Potential Path Traversal"

    @property
    def category(self) -> str:
        return "dangerous_code"

    @property
    def severity(self) -> str:
        return "high"

    @property
    def confidence(self) -> str:
        return "medium"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        lines = content.splitlines()

        # Patterns for path traversal
        if language == "python":
            patterns = [
                r'\bopen\s*\(\s*[^)]*\.\./',  # open with ../
                r'os\.path\.join\s*\([^)]*\.\./',  # os.path.join with ../
                r'pathlib.*\.joinpath\s*\([^)]*\.\./',  # pathlib with ../
            ]
        elif language in ("javascript", "typescript"):
            patterns = [
                r'(?i)(fs\.(read|write)File|path\.join).*\.\./',
            ]
        else:
            patterns = []

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            for pattern in patterns:
                if re.search(pattern, stripped) and not self._is_comment(stripped, language):
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation="File path construction uses '../' sequences which could allow directory traversal if user input influences the path.",
                        remediation="Validate and sanitize file paths. Use os.path.normpath() or pathlib.Path.resolve() and verify the result is within the allowed directory.",
                        references=[
                            "https://cwe.mitre.org/data/definitions/22.html",
                        ],
                    ))

        return findings

    def _is_comment(self, line: str, language: str) -> bool:
        stripped = line.strip()
        if language == "python":
            return stripped.startswith("#")
        elif language in ("javascript", "typescript", "java", "c", "cpp", "go"):
            return stripped.startswith("//") or stripped.startswith("/*")
        return False


class WeakCryptoRule(SecurityRule):
    """Detect weak cryptographic algorithms."""

    @property
    def rule_id(self) -> str:
        return "DANGEROUS_WEAK_CRYPTO"

    @property
    def title(self) -> str:
        return "Use of Weak Cryptographic Algorithm"

    @property
    def category(self) -> str:
        return "dangerous_code"

    @property
    def severity(self) -> str:
        return "medium"

    @property
    def confidence(self) -> str:
        return "high"

    WEAK_ALGORITHMS = {
        "md5": "MD5 is cryptographically broken",
        "sha1": "SHA-1 is cryptographically broken",
        "des": "DES is obsolete",
        "3des": "3DES is deprecated",
        "rc4": "RC4 is broken",
        "ecb": "ECB mode is insecure",
    }

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.lower().strip()

            for algo, reason in self.WEAK_ALGORITHMS.items():
                if algo in stripped and not self._is_comment(line):
                    # Check for actual usage, not just comments
                    if re.search(rf'(hashlib|Crypto|hash|digest).*{algo}', stripped):
                        findings.append(self._create_finding(
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            evidence=line.strip()[:200],
                            explanation=f"Use of {algo.upper()}: {reason}. This algorithm should not be used for security-sensitive operations.",
                            remediation=f"Replace {algo.upper()} with a strong alternative like SHA-256, SHA-3, or AES-GCM.",
                            references=[
                                "https://cwe.mitre.org/data/definitions/327.html",
                                "https://www.nist.gov/publications/transitioning-use-cryptographic-algorithms-and-key-lengths",
                            ],
                        ))

        return findings

    def _is_comment(self, line: str) -> bool:
        return line.strip().startswith("#") or line.strip().startswith("//")


# Register dangerous code rules
registry.register(PythonEvalExecRule())
registry.register(PythonPickleRule())
registry.register(PythonSubprocessShellRule())
registry.register(SQLInjectionRule())
registry.register(PathTraversalRule())
registry.register(WeakCryptoRule())