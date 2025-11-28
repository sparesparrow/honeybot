"""
Unit tests for fraud detection module
"""
from typing import List

import pytest
import pytest_asyncio

from scaipot.fraud_detection import (
    IndicatorExtractor,
    PatternDetector,
    RiskAssessment,
    RiskScorer,
    ScamIndicators,
)
from scaipot.fraud_detection.risk_scorer import RiskLevel

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def indicator_extractor():
    """Create indicator extractor instance"""
    return IndicatorExtractor()


@pytest.fixture
def risk_scorer():
    """Create risk scorer instance"""
    return RiskScorer()


@pytest.fixture
def pattern_detector():
    """Create pattern detector instance"""
    return PatternDetector()


@pytest.fixture
def sample_scam_messages() -> List[str]:
    """Sample scam messages for testing"""
    return [
        "Send Bitcoin to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh for guaranteed 200% profit!",
        "Double your investment! Visit https://crypto-invest-pro.tk now!",
        "Contact me at +1-555-0123 or scammer@example.com for this exclusive opportunity",
        "Limited time offer! Send $5000 to IBAN GB82WEST12345698765432 today!",
    ]


# ============================================================================
# IndicatorExtractor Tests
# ============================================================================


class TestIndicatorExtractor:
    """Test indicator extraction functionality"""

    @pytest.mark.asyncio
    async def test_extract_bitcoin_addresses(self, indicator_extractor):
        """Test extraction of Bitcoin addresses"""
        # Test Bech32 address
        text = "Send BTC to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh please"
        indicators = await indicator_extractor.extract(text)

        assert len(indicators.btc_addresses) == 1
        assert indicators.btc_addresses[0].startswith("bc1")

        # Test Legacy P2PKH address
        text2 = "My wallet is 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        indicators2 = await indicator_extractor.extract(text2)

        assert len(indicators2.btc_addresses) == 1
        assert indicators2.btc_addresses[0].startswith("1")

    @pytest.mark.asyncio
    async def test_extract_ethereum_addresses(self, indicator_extractor):
        """Test extraction of Ethereum addresses"""
        text = "Send ETH to 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        indicators = await indicator_extractor.extract(text)

        assert len(indicators.eth_addresses) == 1
        assert indicators.eth_addresses[0].startswith("0x")
        assert len(indicators.eth_addresses[0]) == 42

    @pytest.mark.asyncio
    async def test_extract_urls(self, indicator_extractor):
        """Test extraction of URLs"""
        text = "Visit https://scam-site.com and www.another-scam.tk for details"
        indicators = await indicator_extractor.extract(text)

        assert len(indicators.urls) >= 2
        assert any("scam-site.com" in url for url in indicators.urls)

    @pytest.mark.asyncio
    async def test_extract_phone_numbers(self, indicator_extractor):
        """Test extraction of phone numbers"""
        text = "Call me at +1-555-123-4567 or 555-987-6543"
        indicators = await indicator_extractor.extract(text)

        assert len(indicators.phone_numbers) >= 1

    @pytest.mark.asyncio
    async def test_extract_emails(self, indicator_extractor):
        """Test extraction of email addresses"""
        text = "Contact scammer@fraud.com or fake.person@scam.net"
        indicators = await indicator_extractor.extract(text)

        assert len(indicators.email_addresses) == 2
        assert "scammer@fraud.com" in indicators.email_addresses

    @pytest.mark.asyncio
    async def test_extract_iban(self, indicator_extractor):
        """Test extraction of IBAN numbers"""
        text = "Transfer to IBAN: GB82WEST12345698765432"
        indicators = await indicator_extractor.extract(text)

        assert len(indicators.iban_numbers) == 1
        assert indicators.iban_numbers[0].startswith("GB")

    @pytest.mark.asyncio
    async def test_extract_suspicious_keywords(self, indicator_extractor):
        """Test extraction of suspicious keywords"""
        text = "Guaranteed profit! Risk-free investment! Double your money now!"
        indicators = await indicator_extractor.extract(text)

        assert len(indicators.suspicious_keywords) >= 3
        assert "guaranteed profit" in indicators.suspicious_keywords
        assert "risk-free" in indicators.suspicious_keywords

    @pytest.mark.asyncio
    async def test_extract_financial_amounts(self, indicator_extractor):
        """Test extraction of financial amounts"""
        text = "Send $5,000 or 1.5 BTC for this opportunity worth €10,000"
        indicators = await indicator_extractor.extract(text)

        assert len(indicators.financial_amounts) >= 2

    @pytest.mark.asyncio
    async def test_extract_empty_string(self, indicator_extractor):
        """Test extraction from empty string"""
        indicators = await indicator_extractor.extract("")

        assert not indicators.has_indicators()
        assert indicators.indicator_count() == 0

    @pytest.mark.asyncio
    async def test_extract_clean_message(self, indicator_extractor):
        """Test extraction from clean message"""
        text = "Hello, how are you today? Nice weather we're having."
        indicators = await indicator_extractor.extract(text)

        # Should have no crypto/financial indicators
        assert len(indicators.btc_addresses) == 0
        assert len(indicators.eth_addresses) == 0
        assert len(indicators.iban_numbers) == 0

    @pytest.mark.asyncio
    async def test_extract_from_conversation(
        self, indicator_extractor, sample_scam_messages
    ):
        """Test extraction from multiple messages"""
        indicators = await indicator_extractor.extract_from_conversation(
            sample_scam_messages
        )

        # Should find indicators from all messages combined
        assert len(indicators.btc_addresses) >= 1
        assert len(indicators.urls) >= 1
        assert len(indicators.phone_numbers) >= 1
        assert len(indicators.email_addresses) >= 1

    @pytest.mark.asyncio
    async def test_duplicate_removal(self, indicator_extractor):
        """Test that duplicate indicators are removed"""
        text = """
        Send to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh
        Again: bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh
        """
        indicators = await indicator_extractor.extract(text)

        # Should only have one unique address
        assert len(indicators.btc_addresses) == 1

    @pytest.mark.asyncio
    async def test_indicator_count(self, indicator_extractor):
        """Test indicator_count method"""
        text = "Send BTC to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh and visit https://scam.com"
        indicators = await indicator_extractor.extract(text)

        assert indicators.indicator_count() >= 2
        assert indicators.has_indicators()


# ============================================================================
# RiskScorer Tests
# ============================================================================


class TestRiskScorer:
    """Test risk scoring functionality"""

    @pytest.mark.asyncio
    async def test_score_high_risk_message(self, risk_scorer):
        """Test scoring of high-risk message"""
        message = "Send Bitcoin to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh NOW! Guaranteed profit!"
        indicators = ScamIndicators(
            btc_addresses=["bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"],
            suspicious_keywords=["guaranteed profit"],
        )

        assessment = await risk_scorer.score_message(message, indicators)

        assert assessment.risk_score > 0.2
        assert assessment.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
        assert assessment.should_alert() or assessment.risk_level == RiskLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_score_critical_message(self, risk_scorer):
        """Test scoring of critical risk message"""
        message = "Send bitcoin now! Deposit required. Send your seed phrase for verification."
        indicators = ScamIndicators(
            btc_addresses=["bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"],
            urls=["https://phishing.tk"],
            suspicious_keywords=["deposit required", "seed phrase"],
        )

        assessment = await risk_scorer.score_message(message, indicators)

        assert assessment.risk_score > 0.6
        assert assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert assessment.should_alert()

    @pytest.mark.asyncio
    async def test_score_low_risk_message(self, risk_scorer):
        """Test scoring of low-risk message"""
        message = "Hello, how are you? I'm interested in learning about crypto."
        indicators = ScamIndicators()

        assessment = await risk_scorer.score_message(message, indicators)

        assert assessment.risk_score < 0.3
        assert assessment.risk_level == RiskLevel.LOW
        assert not assessment.should_alert()

    @pytest.mark.asyncio
    async def test_risk_level_thresholds(self, risk_scorer):
        """Test risk level threshold classification"""
        # Test each threshold
        assert risk_scorer._determine_risk_level(0.1) == RiskLevel.LOW
        assert risk_scorer._determine_risk_level(0.4) == RiskLevel.MEDIUM
        assert risk_scorer._determine_risk_level(0.7) == RiskLevel.HIGH
        assert risk_scorer._determine_risk_level(0.9) == RiskLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_confidence_calculation(self, risk_scorer):
        """Test confidence calculation"""
        # More diverse indicators = higher confidence
        diverse_indicators = ScamIndicators(
            btc_addresses=["bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"],
            urls=["https://scam.com"],
            phone_numbers=["+1-555-0123"],
            email_addresses=["scam@fraud.com"],
        )

        confidence = risk_scorer._calculate_confidence(diverse_indicators)
        assert confidence > 0.5

        # No indicators = low confidence
        empty_indicators = ScamIndicators()
        confidence_low = risk_scorer._calculate_confidence(empty_indicators)
        assert confidence_low < 0.5

    @pytest.mark.asyncio
    async def test_score_conversation(self, risk_scorer, sample_scam_messages):
        """Test scoring entire conversation"""
        indicators = ScamIndicators(
            btc_addresses=["bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"],
            urls=["https://scam.tk"],
            phone_numbers=["+1-555-0123"],
            suspicious_keywords=["guaranteed profit", "double your money"],
        )

        assessment = await risk_scorer.score_conversation(
            sample_scam_messages, indicators
        )

        assert assessment.risk_score > 0
        assert assessment.metadata["message_count"] == len(sample_scam_messages)

    @pytest.mark.asyncio
    async def test_recommendations_generation(self, risk_scorer):
        """Test recommendation generation"""
        # Critical risk
        critical_indicators = ScamIndicators(
            btc_addresses=["bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"],
            urls=["https://phishing.tk"],
        )
        message = "Send bitcoin now! Deposit required."
        assessment = await risk_scorer.score_message(message, critical_indicators)

        if assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            assert len(assessment.recommendations) > 0
            assert any("admin" in rec.lower() for rec in assessment.recommendations)

    @pytest.mark.asyncio
    async def test_url_risk_scoring(self, risk_scorer):
        """Test high-risk URL domain detection"""
        risky_urls = ["https://bit.ly/scam123", "https://fake-exchange.tk"]
        score = risk_scorer._score_urls(risky_urls)

        assert score > risk_scorer.WEIGHTS["url"] * len(risky_urls)

    @pytest.mark.asyncio
    async def test_critical_keyword_detection(self, risk_scorer):
        """Test critical keyword instant high risk"""
        message = "Please send your seed phrase for wallet verification"
        indicators = ScamIndicators(
            suspicious_keywords=["seed phrase", "wallet verification"]
        )

        assessment = await risk_scorer.score_message(message, indicators)

        # Should boost risk significantly
        assert assessment.risk_score > 0.4


# ============================================================================
# PatternDetector Tests
# ============================================================================


class TestPatternDetector:
    """Test main pattern detector orchestration"""

    @pytest.mark.asyncio
    async def test_analyze_message_basic(self, pattern_detector):
        """Test basic message analysis"""
        message = "Send BTC to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"

        result = await pattern_detector.analyze_message(message)

        assert "analyzed_at" in result
        assert "indicators" in result
        assert "risk_assessment" in result
        assert result["indicators"]["total_count"] > 0

    @pytest.mark.asyncio
    async def test_analyze_message_with_metadata(self, pattern_detector):
        """Test message analysis with metadata"""
        message = "Guaranteed profit!"
        metadata = {"session_id": "test_123", "platform": "telegram"}

        result = await pattern_detector.analyze_message(message, metadata)

        assert result["metadata"]["session_id"] == "test_123"
        assert result["metadata"]["platform"] == "telegram"

    @pytest.mark.asyncio
    async def test_analyze_high_risk_message(self, pattern_detector):
        """Test high-risk message detection"""
        message = """
        URGENT! Send Bitcoin to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh
        Visit https://fake-exchange.tk for guaranteed 500% returns!
        Contact +1-555-SCAMMER for more info.
        """

        result = await pattern_detector.analyze_message(message)

        assert result["risk_assessment"]["risk_level"] in ["medium", "high", "critical"]
        assert result["indicators"]["total_count"] >= 3

    @pytest.mark.asyncio
    async def test_analyze_clean_message(self, pattern_detector):
        """Test clean message analysis"""
        message = "Hello! How are you doing today?"

        result = await pattern_detector.analyze_message(message)

        assert result["risk_assessment"]["risk_level"] == "low"
        assert result["indicators"]["total_count"] == 0

    @pytest.mark.asyncio
    async def test_analyze_conversation(
        self, pattern_detector, sample_scam_messages
    ):
        """Test full conversation analysis"""
        result = await pattern_detector.analyze_conversation(
            messages=sample_scam_messages,
            session_id="test_session_123",
        )

        assert result["session_id"] == "test_session_123"
        assert result["message_count"] == len(sample_scam_messages)
        assert result["indicators"]["total_count"] > 0

    @pytest.mark.asyncio
    async def test_alert_triggering(self, pattern_detector):
        """Test that high-risk messages trigger alert flag"""
        message = "Send bitcoin now! Deposit required for withdrawal. Send seed phrase."

        result = await pattern_detector.analyze_message(message)

        # Should trigger alert for critical keywords
        if result["risk_assessment"]["risk_level"] in ["high", "critical"]:
            assert result["risk_assessment"]["should_alert"]

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, pattern_detector):
        """Test statistics tracking"""
        # Analyze a few messages
        await pattern_detector.analyze_message("Test message 1")
        await pattern_detector.analyze_message("Test message 2")

        stats = await pattern_detector.get_statistics()

        assert stats["total_analyses"] >= 2
        assert stats["extractor_initialized"]
        assert stats["scorer_initialized"]

    @pytest.mark.asyncio
    async def test_health_check(self, pattern_detector):
        """Test health check"""
        health = await pattern_detector.health_check()

        assert health is True

    @pytest.mark.asyncio
    async def test_error_handling(self, pattern_detector):
        """Test error handling for invalid input"""
        # Should handle None gracefully
        result = await pattern_detector.analyze_message(None)

        # Should still return a result structure
        assert "analyzed_at" in result or "error" in result


# ============================================================================
# Integration Tests
# ============================================================================


class TestFraudDetectionIntegration:
    """Test integration of all fraud detection components"""

    @pytest.mark.asyncio
    async def test_end_to_end_detection(self):
        """Test complete fraud detection pipeline"""
        detector = PatternDetector()

        # Simulate scammer message
        scam_message = """
        Great news! I can help you make 10x profit on Bitcoin.
        Just send 0.5 BTC to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh
        Visit https://crypto-guaranteed-profit.tk for proof.
        Limited time offer! Act now or miss out on financial freedom!
        """

        result = await detector.analyze_message(scam_message)

        # Verify complete analysis
        assert result["indicators"]["btc_addresses"]
        assert result["indicators"]["urls"]
        assert result["indicators"]["suspicious_keywords"]
        assert result["risk_assessment"]["risk_score"] > 0.3
        assert len(result["risk_assessment"]["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_conversation_risk_progression(self):
        """Test risk score progression over conversation"""
        detector = PatternDetector()

        messages = [
            "Hello, interested in crypto?",
            "I can show you guaranteed profits",
            "Send BTC to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
        ]

        results = []
        for msg in messages:
            result = await detector.analyze_message(msg)
            results.append(result["risk_assessment"]["risk_score"])

        # Risk should generally increase
        assert results[2] > results[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
