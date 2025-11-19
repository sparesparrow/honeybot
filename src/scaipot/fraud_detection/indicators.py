"""
Extract scam indicators from messages (crypto addresses, URLs, IBANs, phones)
"""
import re
import logging
from typing import List, Optional
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class ScamIndicators:
    """Container for extracted scam indicators from a message"""

    btc_addresses: List[str] = field(default_factory=list)
    eth_addresses: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    phone_numbers: List[str] = field(default_factory=list)
    email_addresses: List[str] = field(default_factory=list)
    iban_numbers: List[str] = field(default_factory=list)
    suspicious_keywords: List[str] = field(default_factory=list)
    financial_amounts: List[str] = field(default_factory=list)

    def has_indicators(self) -> bool:
        """Check if any indicators were found"""
        return any([
            self.btc_addresses,
            self.eth_addresses,
            self.urls,
            self.phone_numbers,
            self.email_addresses,
            self.iban_numbers,
            self.suspicious_keywords,
            self.financial_amounts,
        ])

    def indicator_count(self) -> int:
        """Total count of all indicators"""
        return (
            len(self.btc_addresses)
            + len(self.eth_addresses)
            + len(self.urls)
            + len(self.phone_numbers)
            + len(self.email_addresses)
            + len(self.iban_numbers)
            + len(self.suspicious_keywords)
            + len(self.financial_amounts)
        )


class IndicatorExtractor:
    """Extract scam indicators from text messages"""

    # Bitcoin address patterns (Legacy, SegWit, Native SegWit)
    BTC_PATTERNS = [
        r"bc1[a-z0-9]{39,59}",  # Bech32 (bc1) - lowercase only
        r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}",  # Legacy P2PKH/P2SH
    ]

    # Ethereum address pattern
    ETH_PATTERN = r"\b0x[a-fA-F0-9]{40}\b"

    # URL pattern (comprehensive)
    URL_PATTERN = r"https?://[^\s<>\"]+|www\.[^\s<>\"]+"

    # Phone number patterns (international formats)
    PHONE_PATTERNS = [
        r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}",
        r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",  # US format
    ]

    # Email pattern
    EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    # IBAN pattern (simplified)
    IBAN_PATTERN = r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b"

    # Suspicious keywords commonly used in scams
    SUSPICIOUS_KEYWORDS = [
        # Investment scams
        "guaranteed profit",
        "guaranteed return",
        "risk-free",
        "double your money",
        "triple your investment",
        "instant profit",
        "get rich quick",
        "financial freedom",
        "passive income guaranteed",
        # Urgency tactics
        "limited time",
        "act now",
        "hurry up",
        "don't miss out",
        "exclusive opportunity",
        "urgent",
        "time sensitive",
        "expires soon",
        # Trust manipulation
        "100% legit",
        "totally safe",
        "government approved",
        "licensed broker",
        "registered company",
        "trust me",
        "you can trust",
        # Recovery scams
        "recover your funds",
        "get your money back",
        "refund guaranteed",
        "money recovery",
        # Romance/pig butchering
        "my love",
        "my dear",
        "my darling",
        "investment opportunity for us",
        "build our future together",
        # Airdrop/giveaway scams
        "free tokens",
        "airdrop",
        "claim your crypto",
        "bonus coins",
        "verify wallet",
        "connect wallet",
        # Pyramid scheme indicators
        "recruit members",
        "referral bonus",
        "downline",
        "upline",
        "multi-level",
        "network marketing",
        # Fake exchange
        "new exchange",
        "trading platform",
        "withdrawal fee",
        "deposit required",
        "minimum deposit",
    ]

    # Financial amount patterns
    FINANCIAL_PATTERNS = [
        r"\$\s?\d+(?:,\d{3})*(?:\.\d{2})?",  # USD
        r"€\s?\d+(?:,\d{3})*(?:\.\d{2})?",  # EUR
        r"£\s?\d+(?:,\d{3})*(?:\.\d{2})?",  # GBP
        r"\d+(?:,\d{3})*(?:\.\d{2})?\s?(?:USD|EUR|GBP|BTC|ETH)",
        r"\d+(?:\.\d+)?\s?(?:bitcoin|BTC|ethereum|ETH|USDT|crypto)",
    ]

    def __init__(self):
        """Initialize indicator extractor with compiled regex patterns"""
        self.btc_regex = [re.compile(p, re.IGNORECASE) for p in self.BTC_PATTERNS]
        self.eth_regex = re.compile(self.ETH_PATTERN)
        self.url_regex = re.compile(self.URL_PATTERN, re.IGNORECASE)
        self.phone_regex = [re.compile(p) for p in self.PHONE_PATTERNS]
        self.email_regex = re.compile(self.EMAIL_PATTERN)
        self.iban_regex = re.compile(self.IBAN_PATTERN)
        self.financial_regex = [re.compile(p, re.IGNORECASE) for p in self.FINANCIAL_PATTERNS]

        logger.info("Initialized IndicatorExtractor")

    async def extract(self, text: str) -> ScamIndicators:
        """
        Extract all scam indicators from text

        Args:
            text: Message text to analyze

        Returns:
            ScamIndicators object with all found indicators
        """
        if not text:
            return ScamIndicators()

        indicators = ScamIndicators()

        # Extract crypto addresses
        indicators.btc_addresses = self._extract_btc_addresses(text)
        indicators.eth_addresses = self._extract_eth_addresses(text)

        # Extract contact info
        indicators.urls = self._extract_urls(text)
        indicators.phone_numbers = self._extract_phone_numbers(text)
        indicators.email_addresses = self._extract_emails(text)
        indicators.iban_numbers = self._extract_ibans(text)

        # Extract keywords and amounts
        indicators.suspicious_keywords = self._extract_keywords(text)
        indicators.financial_amounts = self._extract_financial_amounts(text)

        if indicators.has_indicators():
            logger.info(
                f"Extracted {indicators.indicator_count()} indicators from message"
            )

        return indicators

    def _extract_btc_addresses(self, text: str) -> List[str]:
        """Extract Bitcoin addresses"""
        addresses = []
        for regex in self.btc_regex:
            matches = regex.findall(text)
            if isinstance(matches, list):
                addresses.extend(matches)

        # Validate BTC addresses (basic check)
        validated = []
        for addr in addresses:
            # Ensure it's a string (not tuple from group capture)
            if isinstance(addr, tuple):
                addr = addr[0] if addr else ""
            if addr and self._is_valid_btc_address(addr):
                validated.append(addr)

        return list(set(validated))  # Remove duplicates

    def _extract_eth_addresses(self, text: str) -> List[str]:
        """Extract Ethereum addresses"""
        matches = self.eth_regex.findall(text)
        return list(set(matches))

    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs"""
        matches = self.url_regex.findall(text)

        # Clean and validate URLs
        cleaned = []
        for url in matches:
            if not url.startswith("http"):
                url = "http://" + url

            # Basic validation
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    cleaned.append(url)
            except Exception:
                continue

        return list(set(cleaned))

    def _extract_phone_numbers(self, text: str) -> List[str]:
        """Extract phone numbers"""
        numbers = []
        for regex in self.phone_regex:
            matches = regex.findall(text)
            numbers.extend(matches)

        # Basic cleanup
        cleaned = []
        for num in numbers:
            # Remove common separators
            clean_num = re.sub(r"[-.\s()]", "", num)
            # Only keep if it looks like a valid phone (7-15 digits)
            if 7 <= len(clean_num) <= 15:
                cleaned.append(num)

        return list(set(cleaned))

    def _extract_emails(self, text: str) -> List[str]:
        """Extract email addresses"""
        matches = self.email_regex.findall(text)
        return list(set(matches))

    def _extract_ibans(self, text: str) -> List[str]:
        """Extract IBAN numbers"""
        matches = self.iban_regex.findall(text)

        # Basic validation (length check)
        validated = []
        for iban in matches:
            if 15 <= len(iban) <= 34:
                validated.append(iban)

        return list(set(validated))

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract suspicious keywords"""
        text_lower = text.lower()
        found_keywords = []

        for keyword in self.SUSPICIOUS_KEYWORDS:
            if keyword in text_lower:
                found_keywords.append(keyword)

        return found_keywords

    def _extract_financial_amounts(self, text: str) -> List[str]:
        """Extract financial amounts"""
        amounts = []
        for regex in self.financial_regex:
            matches = regex.findall(text)
            amounts.extend(matches)

        return list(set(amounts))

    def _is_valid_btc_address(self, address: str) -> bool:
        """
        Basic Bitcoin address validation

        Args:
            address: Potential BTC address

        Returns:
            True if address looks valid
        """
        # Length checks
        if address.startswith("bc1"):
            # Bech32: 42-62 characters
            return 42 <= len(address) <= 62
        elif address.startswith(("1", "3")):
            # Legacy: 26-35 characters
            return 26 <= len(address) <= 35

        return False

    async def extract_from_conversation(
        self, messages: List[str]
    ) -> ScamIndicators:
        """
        Extract indicators from entire conversation

        Args:
            messages: List of message texts

        Returns:
            Aggregated ScamIndicators
        """
        combined_indicators = ScamIndicators()

        for message in messages:
            indicators = await self.extract(message)

            # Aggregate all indicators
            combined_indicators.btc_addresses.extend(indicators.btc_addresses)
            combined_indicators.eth_addresses.extend(indicators.eth_addresses)
            combined_indicators.urls.extend(indicators.urls)
            combined_indicators.phone_numbers.extend(indicators.phone_numbers)
            combined_indicators.email_addresses.extend(indicators.email_addresses)
            combined_indicators.iban_numbers.extend(indicators.iban_numbers)
            combined_indicators.suspicious_keywords.extend(
                indicators.suspicious_keywords
            )
            combined_indicators.financial_amounts.extend(
                indicators.financial_amounts
            )

        # Remove duplicates from aggregated lists
        combined_indicators.btc_addresses = list(
            set(combined_indicators.btc_addresses)
        )
        combined_indicators.eth_addresses = list(
            set(combined_indicators.eth_addresses)
        )
        combined_indicators.urls = list(set(combined_indicators.urls))
        combined_indicators.phone_numbers = list(
            set(combined_indicators.phone_numbers)
        )
        combined_indicators.email_addresses = list(
            set(combined_indicators.email_addresses)
        )
        combined_indicators.iban_numbers = list(set(combined_indicators.iban_numbers))
        combined_indicators.financial_amounts = list(
            set(combined_indicators.financial_amounts)
        )

        return combined_indicators
