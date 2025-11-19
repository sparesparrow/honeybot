"""
Intelligence report generator for scammer interactions
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generate intelligence reports from scammer interactions

    Formats conversation data into structured reports for analysis
    """

    def __init__(self):
        """Initialize report generator"""
        self.reports_generated = 0
        logger.info("Initialized ReportGenerator")

    async def generate_session_report(
        self,
        session_id: str,
        platform: str,
        messages: List[Dict[str, Any]],
        fraud_analysis: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive report for a session

        Args:
            session_id: Session identifier
            platform: Platform name
            messages: List of conversation messages
            fraud_analysis: Fraud detection analysis results
            metadata: Optional session metadata

        Returns:
            Report dictionary
        """
        try:
            report = {
                "report_id": f"SCAIPOT-{session_id}-{int(datetime.utcnow().timestamp())}",
                "generated_at": datetime.utcnow().isoformat(),
                "session_info": {
                    "session_id": session_id,
                    "platform": platform,
                    "message_count": len(messages),
                    "conversation_started": messages[0].get("timestamp") if messages else None,
                    "last_activity": messages[-1].get("timestamp") if messages else None,
                },
                "risk_assessment": fraud_analysis.get("risk_assessment", {}),
                "indicators": fraud_analysis.get("indicators", {}),
                "conversation_summary": self._summarize_conversation(messages),
                "key_extractions": self._extract_key_data(fraud_analysis),
                "timeline": self._build_timeline(messages),
                "metadata": metadata or {},
            }

            # Add recommendations section
            if fraud_analysis.get("risk_assessment", {}).get("recommendations"):
                report["recommendations"] = fraud_analysis["risk_assessment"][
                    "recommendations"
                ]

            self.reports_generated += 1

            logger.info(f"Generated session report for {session_id}")

            return report

        except Exception as e:
            logger.error(f"Error generating session report: {e}", exc_info=True)
            return {
                "error": str(e),
                "session_id": session_id,
                "generated_at": datetime.utcnow().isoformat(),
            }

    def _summarize_conversation(
        self, messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate conversation summary statistics"""
        if not messages:
            return {"total_messages": 0}

        scammer_messages = [m for m in messages if m.get("role") == "user"]
        honeypot_messages = [m for m in messages if m.get("role") == "assistant"]

        # Calculate average message length
        avg_scammer_length = (
            sum(len(m.get("content", "")) for m in scammer_messages)
            / len(scammer_messages)
            if scammer_messages
            else 0
        )

        return {
            "total_messages": len(messages),
            "scammer_messages": len(scammer_messages),
            "honeypot_messages": len(honeypot_messages),
            "avg_scammer_message_length": round(avg_scammer_length, 1),
            "first_message_preview": scammer_messages[0].get("content", "")[:100]
            if scammer_messages
            else None,
            "latest_message_preview": scammer_messages[-1].get("content", "")[:100]
            if scammer_messages
            else None,
        }

    def _extract_key_data(self, fraud_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key data from fraud analysis"""
        indicators = fraud_analysis.get("indicators", {})

        key_data = {}

        # Extract crypto addresses
        if indicators.get("btc_addresses"):
            key_data["bitcoin_addresses"] = indicators["btc_addresses"]

        if indicators.get("eth_addresses"):
            key_data["ethereum_addresses"] = indicators["eth_addresses"]

        # Extract contact info
        if indicators.get("urls"):
            key_data["urls"] = indicators["urls"]

        if indicators.get("phone_numbers"):
            key_data["phone_numbers"] = indicators["phone_numbers"]

        if indicators.get("email_addresses"):
            key_data["email_addresses"] = indicators["email_addresses"]

        # Extract financial data
        if indicators.get("iban_numbers"):
            key_data["iban_numbers"] = indicators["iban_numbers"]

        if indicators.get("financial_amounts"):
            key_data["financial_amounts"] = indicators["financial_amounts"]

        # Top suspicious keywords
        if indicators.get("suspicious_keywords"):
            key_data["top_keywords"] = indicators["suspicious_keywords"][:10]

        return key_data

    def _build_timeline(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build conversation timeline"""
        timeline = []

        for msg in messages:
            timeline.append({
                "timestamp": msg.get("timestamp", datetime.utcnow().isoformat()),
                "role": msg.get("role", "unknown"),
                "content_preview": msg.get("content", "")[:100],
                "message_length": len(msg.get("content", "")),
            })

        return timeline

    async def export_report_json(self, report: Dict[str, Any]) -> str:
        """
        Export report as JSON string

        Args:
            report: Report dictionary

        Returns:
            JSON string
        """
        try:
            return json.dumps(report, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error exporting report to JSON: {e}")
            return json.dumps({"error": str(e)})

    async def export_report_markdown(self, report: Dict[str, Any]) -> str:
        """
        Export report as Markdown format

        Args:
            report: Report dictionary

        Returns:
            Markdown string
        """
        try:
            md = f"""# SCAIPOT Intelligence Report

**Report ID:** `{report.get('report_id', 'N/A')}`
**Generated:** {report.get('generated_at', 'N/A')}

---

## Session Information

- **Session ID:** `{report.get('session_info', {}).get('session_id', 'N/A')}`
- **Platform:** {report.get('session_info', {}).get('platform', 'N/A').capitalize()}
- **Message Count:** {report.get('session_info', {}).get('message_count', 0)}
- **Started:** {report.get('session_info', {}).get('conversation_started', 'N/A')}
- **Last Activity:** {report.get('session_info', {}).get('last_activity', 'N/A')}

---

## Risk Assessment

- **Risk Level:** `{report.get('risk_assessment', {}).get('risk_level', 'N/A').upper()}`
- **Risk Score:** {report.get('risk_assessment', {}).get('risk_score', 0):.2f}
- **Confidence:** {report.get('risk_assessment', {}).get('confidence', 0):.2f}
- **Indicators Found:** {report.get('indicators', {}).get('total_count', 0)}

### Risk Factors

"""
            # Add risk factors
            risk_factors = report.get("risk_assessment", {}).get("risk_factors", [])
            if risk_factors:
                for factor in risk_factors:
                    md += f"- {factor}\n"
            else:
                md += "- None identified\n"

            md += "\n---\n\n## Extracted Indicators\n\n"

            # Add key extractions
            key_data = report.get("key_extractions", {})

            if key_data.get("bitcoin_addresses"):
                md += f"### Bitcoin Addresses ({len(key_data['bitcoin_addresses'])})\n\n"
                for addr in key_data["bitcoin_addresses"]:
                    md += f"- `{addr}`\n"
                md += "\n"

            if key_data.get("ethereum_addresses"):
                md += f"### Ethereum Addresses ({len(key_data['ethereum_addresses'])})\n\n"
                for addr in key_data["ethereum_addresses"]:
                    md += f"- `{addr}`\n"
                md += "\n"

            if key_data.get("urls"):
                md += f"### URLs ({len(key_data['urls'])})\n\n"
                for url in key_data["urls"]:
                    md += f"- {url}\n"
                md += "\n"

            if key_data.get("phone_numbers"):
                md += f"### Phone Numbers ({len(key_data['phone_numbers'])})\n\n"
                for phone in key_data["phone_numbers"]:
                    md += f"- {phone}\n"
                md += "\n"

            if key_data.get("email_addresses"):
                md += f"### Email Addresses ({len(key_data['email_addresses'])})\n\n"
                for email in key_data["email_addresses"]:
                    md += f"- {email}\n"
                md += "\n"

            # Add recommendations
            recommendations = report.get("recommendations", [])
            if recommendations:
                md += "---\n\n## Recommendations\n\n"
                for rec in recommendations:
                    md += f"- {rec}\n"

            md += "\n---\n\n*Generated by SCAIPOT Honeypot System*\n"

            return md

        except Exception as e:
            logger.error(f"Error exporting report to Markdown: {e}")
            return f"# Error Generating Report\n\n{str(e)}"

    async def get_statistics(self) -> Dict[str, Any]:
        """Get report generator statistics"""
        return {
            "reports_generated": self.reports_generated,
        }

    async def health_check(self) -> bool:
        """Health check"""
        return True
