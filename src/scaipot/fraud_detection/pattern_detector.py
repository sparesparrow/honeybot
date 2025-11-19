"""
Main fraud detection engine - orchestrates indicator extraction and risk scoring
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .indicators import IndicatorExtractor, ScamIndicators
from .risk_scorer import RiskScorer, RiskAssessment

logger = logging.getLogger(__name__)


class PatternDetector:
    """
    Main fraud detection engine that coordinates indicator extraction
    and risk assessment for scammer conversations
    """

    def __init__(self):
        """Initialize pattern detector with extractor and scorer"""
        self.extractor = IndicatorExtractor()
        self.scorer = RiskScorer()
        self.analysis_count = 0

        logger.info("Initialized PatternDetector")

    async def analyze_message(
        self, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single message for scam patterns

        Args:
            message: Message text to analyze
            metadata: Optional metadata about the message

        Returns:
            Analysis result with indicators and risk assessment
        """
        try:
            logger.debug(f"Analyzing message: {message[:50]}...")

            # Extract indicators
            indicators = await self.extractor.extract(message)

            # Score risk
            risk_assessment = await self.scorer.score_message(message, indicators)

            # Track analysis
            self.analysis_count += 1

            result = {
                "analyzed_at": datetime.utcnow().isoformat(),
                "message_preview": message[:100],
                "indicators": {
                    "btc_addresses": indicators.btc_addresses,
                    "eth_addresses": indicators.eth_addresses,
                    "urls": indicators.urls,
                    "phone_numbers": indicators.phone_numbers,
                    "email_addresses": indicators.email_addresses,
                    "iban_numbers": indicators.iban_numbers,
                    "suspicious_keywords": indicators.suspicious_keywords,
                    "financial_amounts": indicators.financial_amounts,
                    "total_count": indicators.indicator_count(),
                },
                "risk_assessment": {
                    "risk_score": risk_assessment.risk_score,
                    "risk_level": risk_assessment.risk_level.value,
                    "confidence": risk_assessment.confidence,
                    "risk_factors": risk_assessment.risk_factors,
                    "recommendations": risk_assessment.recommendations,
                    "should_alert": risk_assessment.should_alert(),
                },
                "metadata": metadata or {},
            }

            logger.info(
                f"Analysis complete: {risk_assessment.risk_level.value} risk "
                f"({indicators.indicator_count()} indicators)"
            )

            return result

        except Exception as e:
            logger.error(f"Error analyzing message: {e}", exc_info=True)
            return {
                "error": str(e),
                "analyzed_at": datetime.utcnow().isoformat(),
            }

    async def analyze_conversation(
        self,
        messages: List[str],
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze entire conversation for scam patterns

        Args:
            messages: List of message texts
            session_id: Session identifier
            metadata: Optional metadata about the conversation

        Returns:
            Comprehensive analysis result
        """
        try:
            logger.info(
                f"Analyzing conversation {session_id} ({len(messages)} messages)"
            )

            # Extract indicators from all messages
            conversation_indicators = await self.extractor.extract_from_conversation(
                messages
            )

            # Score conversation risk
            risk_assessment = await self.scorer.score_conversation(
                messages, conversation_indicators
            )

            # Track analysis
            self.analysis_count += 1

            result = {
                "analyzed_at": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "message_count": len(messages),
                "indicators": {
                    "btc_addresses": conversation_indicators.btc_addresses,
                    "eth_addresses": conversation_indicators.eth_addresses,
                    "urls": conversation_indicators.urls,
                    "phone_numbers": conversation_indicators.phone_numbers,
                    "email_addresses": conversation_indicators.email_addresses,
                    "iban_numbers": conversation_indicators.iban_numbers,
                    "suspicious_keywords": list(
                        set(conversation_indicators.suspicious_keywords)
                    ),
                    "financial_amounts": conversation_indicators.financial_amounts,
                    "total_count": conversation_indicators.indicator_count(),
                },
                "risk_assessment": {
                    "risk_score": risk_assessment.risk_score,
                    "risk_level": risk_assessment.risk_level.value,
                    "confidence": risk_assessment.confidence,
                    "risk_factors": risk_assessment.risk_factors,
                    "recommendations": risk_assessment.recommendations,
                    "should_alert": risk_assessment.should_alert(),
                },
                "metadata": metadata or {},
            }

            logger.info(
                f"Conversation analysis complete: {risk_assessment.risk_level.value} "
                f"risk ({conversation_indicators.indicator_count()} total indicators)"
            )

            return result

        except Exception as e:
            logger.error(f"Error analyzing conversation: {e}", exc_info=True)
            return {
                "error": str(e),
                "analyzed_at": datetime.utcnow().isoformat(),
                "session_id": session_id,
            }

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get pattern detector statistics

        Returns:
            Statistics dictionary
        """
        return {
            "total_analyses": self.analysis_count,
            "extractor_initialized": self.extractor is not None,
            "scorer_initialized": self.scorer is not None,
        }

    async def health_check(self) -> bool:
        """
        Health check for pattern detector

        Returns:
            True if healthy
        """
        try:
            # Simple health check - verify components initialized
            return (
                self.extractor is not None
                and self.scorer is not None
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
