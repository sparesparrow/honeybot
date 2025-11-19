"""
Risk scoring engine for scammer conversations
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .indicators import ScamIndicators

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAssessment:
    """Risk assessment result for a conversation"""

    risk_score: float  # 0.0 to 1.0
    risk_level: RiskLevel
    confidence: float  # 0.0 to 1.0
    indicators_found: int
    risk_factors: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any]

    def should_alert(self) -> bool:
        """Determine if this risk level warrants an admin alert"""
        return self.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]


class RiskScorer:
    """
    Score conversation risk based on detected indicators and patterns

    Uses heuristic-based scoring model (v1).
    Future: ML-based classification model (v2)
    """

    # Risk weights for different indicator types
    WEIGHTS = {
        "btc_address": 0.25,
        "eth_address": 0.25,
        "url": 0.15,
        "phone_number": 0.10,
        "email": 0.05,
        "iban": 0.20,
        "suspicious_keyword": 0.02,  # Per keyword
        "financial_amount": 0.05,
    }

    # Risk thresholds
    THRESHOLDS = {
        RiskLevel.LOW: 0.0,
        RiskLevel.MEDIUM: 0.3,
        RiskLevel.HIGH: 0.6,
        RiskLevel.CRITICAL: 0.85,
    }

    # High-risk URL domains (common scam sites)
    HIGH_RISK_DOMAINS = [
        "bit.ly",
        "tinyurl.com",
        "t.me",  # Telegram channels often used for scams
        ".tk",  # Free TLD
        ".ml",  # Free TLD
        ".ga",  # Free TLD
        ".cf",  # Free TLD
    ]

    # Critical keywords (instant high risk)
    CRITICAL_KEYWORDS = [
        "send bitcoin",
        "send btc",
        "deposit now",
        "withdrawal fee",
        "verify your wallet",
        "connect wallet",
        "seed phrase",
        "private key",
        "recovery phrase",
        "12 word",
        "24 word",
    ]

    def __init__(self):
        """Initialize risk scorer"""
        logger.info("Initialized RiskScorer")

    async def score_message(
        self, message: str, indicators: ScamIndicators
    ) -> RiskAssessment:
        """
        Score a single message for scam risk

        Args:
            message: Message text
            indicators: Extracted indicators

        Returns:
            RiskAssessment with score and recommendations
        """
        risk_score = 0.0
        risk_factors = []
        metadata = {}

        # Score cryptocurrency addresses
        if indicators.btc_addresses:
            score = len(indicators.btc_addresses) * self.WEIGHTS["btc_address"]
            risk_score += min(score, 0.5)  # Cap at 0.5
            risk_factors.append(
                f"Found {len(indicators.btc_addresses)} Bitcoin address(es)"
            )
            metadata["btc_addresses"] = indicators.btc_addresses

        if indicators.eth_addresses:
            score = len(indicators.eth_addresses) * self.WEIGHTS["eth_address"]
            risk_score += min(score, 0.5)
            risk_factors.append(
                f"Found {len(indicators.eth_addresses)} Ethereum address(es)"
            )
            metadata["eth_addresses"] = indicators.eth_addresses

        # Score URLs
        if indicators.urls:
            url_risk = self._score_urls(indicators.urls)
            risk_score += url_risk
            risk_factors.append(f"Found {len(indicators.urls)} URL(s)")
            metadata["urls"] = indicators.urls

        # Score contact information
        if indicators.phone_numbers:
            score = len(indicators.phone_numbers) * self.WEIGHTS["phone_number"]
            risk_score += min(score, 0.3)
            risk_factors.append(
                f"Found {len(indicators.phone_numbers)} phone number(s)"
            )

        if indicators.email_addresses:
            score = len(indicators.email_addresses) * self.WEIGHTS["email"]
            risk_score += min(score, 0.2)
            risk_factors.append(
                f"Found {len(indicators.email_addresses)} email address(es)"
            )

        if indicators.iban_numbers:
            score = len(indicators.iban_numbers) * self.WEIGHTS["iban"]
            risk_score += min(score, 0.4)
            risk_factors.append(f"Found {len(indicators.iban_numbers)} IBAN(s)")
            metadata["iban_numbers"] = indicators.iban_numbers

        # Score suspicious keywords
        if indicators.suspicious_keywords:
            keyword_score = len(indicators.suspicious_keywords) * self.WEIGHTS[
                "suspicious_keyword"
            ]
            risk_score += min(keyword_score, 0.3)
            risk_factors.append(
                f"Found {len(indicators.suspicious_keywords)} suspicious keyword(s)"
            )
            metadata["keywords"] = indicators.suspicious_keywords

        # Score financial amounts
        if indicators.financial_amounts:
            score = len(indicators.financial_amounts) * self.WEIGHTS[
                "financial_amount"
            ]
            risk_score += min(score, 0.2)
            risk_factors.append(
                f"Found {len(indicators.financial_amounts)} financial amount(s)"
            )

        # Check for critical keywords (instant high risk)
        message_lower = message.lower()
        for critical_keyword in self.CRITICAL_KEYWORDS:
            if critical_keyword in message_lower:
                risk_score += 0.4
                risk_factors.append(f"CRITICAL: Contains '{critical_keyword}'")

        # Cap score at 1.0
        risk_score = min(risk_score, 1.0)

        # Determine risk level
        risk_level = self._determine_risk_level(risk_score)

        # Calculate confidence (higher with more indicators)
        confidence = self._calculate_confidence(indicators)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            risk_level, indicators, message
        )

        assessment = RiskAssessment(
            risk_score=round(risk_score, 3),
            risk_level=risk_level,
            confidence=round(confidence, 3),
            indicators_found=indicators.indicator_count(),
            risk_factors=risk_factors,
            recommendations=recommendations,
            metadata=metadata,
        )

        logger.info(
            f"Risk assessment: {risk_level.value} (score: {assessment.risk_score})"
        )

        return assessment

    async def score_conversation(
        self,
        messages: List[str],
        conversation_indicators: ScamIndicators,
    ) -> RiskAssessment:
        """
        Score entire conversation for scam risk

        Args:
            messages: List of message texts
            conversation_indicators: Aggregated indicators

        Returns:
            RiskAssessment for the conversation
        """
        # For conversation scoring, we combine the full conversation text
        full_conversation = " ".join(messages)

        assessment = await self.score_message(
            full_conversation, conversation_indicators
        )

        # Adjust confidence based on conversation length
        message_count = len(messages)
        if message_count > 5:
            assessment.confidence = min(assessment.confidence * 1.2, 1.0)
        elif message_count < 3:
            assessment.confidence *= 0.8

        assessment.metadata["message_count"] = message_count

        return assessment

    def _score_urls(self, urls: List[str]) -> float:
        """Score URLs for risk (shortened URLs, suspicious domains)"""
        base_score = len(urls) * self.WEIGHTS["url"]

        # Additional risk for high-risk domains
        high_risk_count = 0
        for url in urls:
            url_lower = url.lower()
            for risky_domain in self.HIGH_RISK_DOMAINS:
                if risky_domain in url_lower:
                    high_risk_count += 1
                    break

        # Add extra weight for high-risk domains
        if high_risk_count > 0:
            base_score += high_risk_count * 0.15

        return min(base_score, 0.5)

    def _determine_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level from score"""
        if score >= self.THRESHOLDS[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif score >= self.THRESHOLDS[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif score >= self.THRESHOLDS[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _calculate_confidence(self, indicators: ScamIndicators) -> float:
        """
        Calculate confidence in risk assessment

        More indicators = higher confidence
        """
        indicator_count = indicators.indicator_count()

        if indicator_count == 0:
            return 0.3  # Low confidence with no indicators

        # Confidence increases with more diverse indicators
        diverse_types = 0
        if indicators.btc_addresses:
            diverse_types += 1
        if indicators.eth_addresses:
            diverse_types += 1
        if indicators.urls:
            diverse_types += 1
        if indicators.phone_numbers:
            diverse_types += 1
        if indicators.email_addresses:
            diverse_types += 1
        if indicators.iban_numbers:
            diverse_types += 1
        if indicators.suspicious_keywords:
            diverse_types += 1

        # Base confidence on diversity and count
        confidence = 0.5 + (diverse_types * 0.1) + (min(indicator_count, 10) * 0.02)

        return min(confidence, 1.0)

    def _generate_recommendations(
        self, risk_level: RiskLevel, indicators: ScamIndicators, message: str
    ) -> List[str]:
        """Generate action recommendations based on risk"""
        recommendations = []

        if risk_level == RiskLevel.CRITICAL:
            recommendations.append("ALERT ADMIN IMMEDIATELY")
            recommendations.append("Log all interaction details")
            recommendations.append("Capture screenshots if URLs present")
            recommendations.append("Report crypto addresses to threat databases")

        elif risk_level == RiskLevel.HIGH:
            recommendations.append("Monitor conversation closely")
            recommendations.append("Alert admin if pattern continues")
            recommendations.append("Log crypto addresses and URLs")

        elif risk_level == RiskLevel.MEDIUM:
            recommendations.append("Continue engagement")
            recommendations.append("Track for escalating indicators")
            recommendations.append("Log extracted indicators")

        else:  # LOW
            recommendations.append("Continue normal engagement")
            recommendations.append("Watch for future indicators")

        # Specific recommendations based on indicators
        if indicators.btc_addresses or indicators.eth_addresses:
            recommendations.append("Track blockchain addresses for transactions")

        if indicators.urls:
            recommendations.append("Click URLs in isolated sandbox")

        if indicators.phone_numbers or indicators.email_addresses:
            recommendations.append("Cross-reference contact info with known scammers")

        return recommendations
