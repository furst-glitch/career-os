"""
PIIScanner — detects and redacts PII from AI request messages.

Purpose: Ensure PII never reaches AI providers or audit logs.
Strategy: Regex-based pattern matching (not ML). Fast, deterministic, auditable.
Responsibility: Scan and redact only. Does not block requests (caller decides).
Dependencies: None (pure function, no I/O).
Limitations:
  - Regex cannot catch all PII — adversarial inputs may bypass patterns.
  - Context-free: does not understand semantic meaning of text.
  - CPR validation is format-only, not checksum-validated (for performance).

Redaction format: [REDACTED:TYPE] e.g. [REDACTED:CPR], [REDACTED:IBAN]

Privacy principle: sanitized_text in PIIScanResult may be logged.
                  Original text must NEVER be logged if has_pii=True.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.gateway.schemas import PIIScanResult


@dataclass(frozen=True)
class _Pattern:
    name: str
    regex: re.Pattern[str]
    redaction: str


class PIIScanner:
    """
    Stateless PII scanner. Thread-safe. Instantiate once, share freely.

    Scan order is deliberate:
      1. CPR        (10-digit Danish numbers — run before PHONE so the 8-digit
                     phone pattern does not partially consume a CPR).
      2. CREDIT_CARD (Luhn-validated — run before IBAN/PHONE to claim digit runs).
      3. IBAN       (2 letters + 2 digits + alphanumerics).
      4. EMAIL
      5. PHONE      (Danish 8-digit, optionally prefixed).
    """

    # Note: ordering of this list is significant. See class docstring.
    _PATTERNS: list[_Pattern] = [
        _Pattern("CPR", re.compile(r"\b\d{6}[-–]?\d{4}\b"), "[REDACTED:CPR]"),
        _Pattern("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b"), "[REDACTED:IBAN]"),
        _Pattern(
            "EMAIL",
            re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
            "[REDACTED:EMAIL]",
        ),
        _Pattern(
            "PHONE",
            re.compile(r"\b(?:\+45|0045)?[\s\-]?(?:\d{2}[\s\-]?){3}\d{2}\b"),
            "[REDACTED:PHONE]",
        ),
    ]

    # Credit card handled separately (needs Luhn validation).
    _CC_CANDIDATE = re.compile(r"\b[\d][\d\s\-]{11,21}[\d]\b")

    def scan(self, text: str, agent_name: str = "") -> PIIScanResult:
        """Scan text for PII and return sanitized version."""
        found_types: list[str] = []
        sanitized = text

        # CPR first (before credit-card / phone so 10-digit CPR is not split).
        cpr_pattern = self._PATTERNS[0]
        if cpr_pattern.regex.search(sanitized):
            sanitized = cpr_pattern.regex.sub(cpr_pattern.redaction, sanitized)
            found_types.append(cpr_pattern.name)

        # Credit card — Luhn validated. Run before IBAN/PHONE to claim digit runs.
        sanitized, cc_found = self._redact_credit_cards(sanitized)
        if cc_found:
            found_types.append("CREDIT_CARD")

        # Remaining patterns (IBAN, EMAIL, PHONE).
        for pattern in self._PATTERNS[1:]:
            if pattern.regex.search(sanitized):
                sanitized = pattern.regex.sub(pattern.redaction, sanitized)
                found_types.append(pattern.name)

        return PIIScanResult(
            has_pii=bool(found_types),
            scan_types_found=found_types,
            sanitized_text=sanitized,
        )

    def scan_messages(
        self,
        messages: list[dict[str, str]],
        agent_name: str = "",
    ) -> tuple[list[dict[str, str]], PIIScanResult]:
        """
        Scan all message contents and return sanitized messages + aggregate result.

        Returns (sanitized_messages, aggregate_result).
        The aggregate result reflects PII found across ALL messages.
        """
        all_types: list[str] = []
        sanitized_messages: list[dict[str, str]] = []

        for msg in messages:
            content = msg.get("content", "")
            result = self.scan(content, agent_name)
            sanitized_messages.append({**msg, "content": result.sanitized_text})
            all_types.extend(result.scan_types_found)

        unique_types = list(dict.fromkeys(all_types))  # deduplicate, preserve order
        return sanitized_messages, PIIScanResult(
            has_pii=bool(unique_types),
            scan_types_found=unique_types,
            sanitized_text="",  # Aggregate result has no single sanitized text
        )

    def _redact_credit_cards(self, text: str) -> tuple[str, bool]:
        """Find credit card numbers via Luhn check and redact them."""
        found = False

        def replace_if_cc(match: re.Match[str]) -> str:
            nonlocal found
            digits = re.sub(r"[\s\-]", "", match.group())
            if 13 <= len(digits) <= 19 and self._luhn_check(digits):
                found = True
                return "[REDACTED:CREDIT_CARD]"
            return match.group()

        result = self._CC_CANDIDATE.sub(replace_if_cc, text)
        return result, found

    @staticmethod
    def _luhn_check(digits: str) -> bool:
        """Validate card number using the Luhn algorithm."""
        if not digits.isdigit():
            return False
        total = 0
        for i, d in enumerate(reversed(digits)):
            n = int(d)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0
