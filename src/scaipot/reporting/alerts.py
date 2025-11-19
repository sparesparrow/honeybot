"""
Alert manager for sending notifications to admin channels (Slack, Discord)
"""
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AlertChannel(str, Enum):
    """Alert notification channels"""

    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"  # Future implementation


class AlertManager:
    """
    Manages admin alerts for high-risk scammer interactions

    Sends notifications to Slack/Discord when critical patterns detected
    """

    def __init__(
        self,
        slack_webhook_url: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        enabled: bool = True,
    ):
        """
        Initialize alert manager

        Args:
            slack_webhook_url: Slack webhook URL for alerts
            discord_webhook_url: Discord webhook URL for alerts
            enabled: Enable/disable alerting system
        """
        self.slack_webhook_url = slack_webhook_url
        self.discord_webhook_url = discord_webhook_url
        self.enabled = enabled

        self.alerts_sent = 0
        self.failed_alerts = 0

        # Validate configuration
        if enabled and not (slack_webhook_url or discord_webhook_url):
            logger.warning(
                "AlertManager enabled but no webhook URLs configured. "
                "Alerts will be logged only."
            )

        logger.info(
            f"Initialized AlertManager (enabled={enabled}, "
            f"slack={'configured' if slack_webhook_url else 'not configured'}, "
            f"discord={'configured' if discord_webhook_url else 'not configured'})"
        )

    async def send_high_risk_alert(
        self,
        session_id: str,
        risk_level: str,
        risk_score: float,
        indicators: Dict[str, Any],
        message_preview: str,
        platform: str,
        recommendations: List[str],
    ) -> bool:
        """
        Send alert for high-risk scammer interaction

        Args:
            session_id: Session identifier
            risk_level: Risk level (high, critical)
            risk_score: Numerical risk score (0-1)
            indicators: Dict of extracted indicators
            message_preview: Preview of scammer message
            platform: Platform name (telegram, signal, etc.)
            recommendations: List of recommended actions

        Returns:
            True if alert sent successfully to at least one channel
        """
        if not self.enabled:
            logger.debug("Alerting disabled, skipping alert")
            return False

        try:
            # Build alert message
            alert_data = self._build_alert_message(
                session_id=session_id,
                risk_level=risk_level,
                risk_score=risk_score,
                indicators=indicators,
                message_preview=message_preview,
                platform=platform,
                recommendations=recommendations,
            )

            # Send to configured channels
            success = False

            if self.slack_webhook_url:
                slack_sent = await self._send_slack_alert(alert_data)
                success = success or slack_sent

            if self.discord_webhook_url:
                discord_sent = await self._send_discord_alert(alert_data)
                success = success or discord_sent

            if success:
                self.alerts_sent += 1
                logger.info(f"Alert sent for session {session_id} ({risk_level})")
            else:
                self.failed_alerts += 1
                logger.error(f"Failed to send alert for session {session_id}")

            return success

        except Exception as e:
            logger.error(f"Error sending alert: {e}", exc_info=True)
            self.failed_alerts += 1
            return False

    async def _send_slack_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Send alert to Slack via webhook

        Args:
            alert_data: Alert data dictionary

        Returns:
            True if sent successfully
        """
        try:
            # Format for Slack
            color = self._get_alert_color(alert_data["risk_level"])

            payload = {
                "text": f"🚨 *{alert_data['title']}*",
                "attachments": [
                    {
                        "color": color,
                        "fields": [
                            {
                                "title": "Risk Level",
                                "value": alert_data["risk_level"].upper(),
                                "short": True,
                            },
                            {
                                "title": "Risk Score",
                                "value": f"{alert_data['risk_score']:.2f}",
                                "short": True,
                            },
                            {
                                "title": "Platform",
                                "value": alert_data["platform"],
                                "short": True,
                            },
                            {
                                "title": "Session ID",
                                "value": alert_data["session_id"],
                                "short": True,
                            },
                            {
                                "title": "Message Preview",
                                "value": f"```{alert_data['message_preview']}```",
                                "short": False,
                            },
                            {
                                "title": "Indicators Found",
                                "value": self._format_indicators_slack(
                                    alert_data["indicators"]
                                ),
                                "short": False,
                            },
                            {
                                "title": "Recommendations",
                                "value": "\n".join(
                                    f"• {rec}" for rec in alert_data["recommendations"]
                                ),
                                "short": False,
                            },
                        ],
                        "footer": "SCAIPOT Honeypot System",
                        "ts": int(datetime.utcnow().timestamp()),
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.slack_webhook_url, json=payload)
                response.raise_for_status()

            logger.debug("Slack alert sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    async def _send_discord_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Send alert to Discord via webhook

        Args:
            alert_data: Alert data dictionary

        Returns:
            True if sent successfully
        """
        try:
            # Format for Discord
            color = self._get_alert_color_code(alert_data["risk_level"])

            embed = {
                "title": f"🚨 {alert_data['title']}",
                "color": color,
                "fields": [
                    {
                        "name": "Risk Level",
                        "value": alert_data["risk_level"].upper(),
                        "inline": True,
                    },
                    {
                        "name": "Risk Score",
                        "value": f"{alert_data['risk_score']:.2f}",
                        "inline": True,
                    },
                    {
                        "name": "Platform",
                        "value": alert_data["platform"],
                        "inline": True,
                    },
                    {
                        "name": "Session ID",
                        "value": f"`{alert_data['session_id']}`",
                        "inline": False,
                    },
                    {
                        "name": "Message Preview",
                        "value": f"```{alert_data['message_preview']}```",
                        "inline": False,
                    },
                    {
                        "name": "Indicators Found",
                        "value": self._format_indicators_discord(
                            alert_data["indicators"]
                        ),
                        "inline": False,
                    },
                    {
                        "name": "Recommendations",
                        "value": "\n".join(
                            f"• {rec}" for rec in alert_data["recommendations"]
                        ),
                        "inline": False,
                    },
                ],
                "footer": {
                    "text": "SCAIPOT Honeypot System",
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            payload = {"embeds": [embed]}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.discord_webhook_url, json=payload)
                response.raise_for_status()

            logger.debug("Discord alert sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False

    def _build_alert_message(
        self,
        session_id: str,
        risk_level: str,
        risk_score: float,
        indicators: Dict[str, Any],
        message_preview: str,
        platform: str,
        recommendations: List[str],
    ) -> Dict[str, Any]:
        """Build alert message data structure"""
        return {
            "title": f"High-Risk Scammer Detected ({risk_level.upper()})",
            "session_id": session_id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "indicators": indicators,
            "message_preview": message_preview[:200],  # Limit length
            "platform": platform,
            "recommendations": recommendations[:5],  # Top 5 recommendations
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _format_indicators_slack(self, indicators: Dict[str, Any]) -> str:
        """Format indicators for Slack display"""
        parts = []

        if indicators.get("btc_addresses"):
            parts.append(f"₿ BTC: {len(indicators['btc_addresses'])} address(es)")

        if indicators.get("eth_addresses"):
            parts.append(f"Ξ ETH: {len(indicators['eth_addresses'])} address(es)")

        if indicators.get("urls"):
            parts.append(f"🔗 URLs: {len(indicators['urls'])}")

        if indicators.get("phone_numbers"):
            parts.append(f"📞 Phones: {len(indicators['phone_numbers'])}")

        if indicators.get("email_addresses"):
            parts.append(f"✉️ Emails: {len(indicators['email_addresses'])}")

        if indicators.get("iban_numbers"):
            parts.append(f"💳 IBANs: {len(indicators['iban_numbers'])}")

        if indicators.get("suspicious_keywords"):
            parts.append(f"⚠️ Keywords: {len(indicators['suspicious_keywords'])}")

        return " | ".join(parts) if parts else "None"

    def _format_indicators_discord(self, indicators: Dict[str, Any]) -> str:
        """Format indicators for Discord display"""
        return self._format_indicators_slack(indicators)  # Same format works

    def _get_alert_color(self, risk_level: str) -> str:
        """Get Slack color for risk level"""
        colors = {
            "low": "#36a64f",  # Green
            "medium": "#ff9800",  # Orange
            "high": "#ff5722",  # Red
            "critical": "#b71c1c",  # Dark red
        }
        return colors.get(risk_level.lower(), "#808080")

    def _get_alert_color_code(self, risk_level: str) -> int:
        """Get Discord color code for risk level"""
        colors = {
            "low": 0x36A64F,  # Green
            "medium": 0xFF9800,  # Orange
            "high": 0xFF5722,  # Red
            "critical": 0xB71C1C,  # Dark red
        }
        return colors.get(risk_level.lower(), 0x808080)

    async def send_test_alert(self) -> bool:
        """
        Send a test alert to verify configuration

        Returns:
            True if test alert sent successfully
        """
        test_data = {
            "title": "Test Alert - SCAIPOT System Check",
            "session_id": "test_session_123",
            "risk_level": "high",
            "risk_score": 0.85,
            "indicators": {
                "btc_addresses": ["bc1qtest123"],
                "urls": ["https://test-scam.com"],
                "suspicious_keywords": ["test", "guaranteed profit"],
            },
            "message_preview": "This is a test alert from SCAIPOT honeypot system.",
            "platform": "test",
            "recommendations": ["Verify webhook configuration", "Check alert formatting"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        success = False

        if self.slack_webhook_url:
            success = await self._send_slack_alert(test_data) or success

        if self.discord_webhook_url:
            success = await self._send_discord_alert(test_data) or success

        return success

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get alert manager statistics

        Returns:
            Statistics dictionary
        """
        return {
            "enabled": self.enabled,
            "alerts_sent": self.alerts_sent,
            "failed_alerts": self.failed_alerts,
            "slack_configured": self.slack_webhook_url is not None,
            "discord_configured": self.discord_webhook_url is not None,
        }

    async def health_check(self) -> bool:
        """
        Health check for alert manager

        Returns:
            True if healthy
        """
        return self.enabled and (
            self.slack_webhook_url is not None or self.discord_webhook_url is not None
        )
