"""
Bitcoin Who's Who API integration for reporting scammer BTC addresses
"""
import logging
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BitcoinWhosWhoReporter:
    """
    Reporter for submitting Bitcoin addresses to Bitcoin Who's Who database

    API: https://www.bitcoinwhoswho.com/api/
    """

    API_BASE_URL = "https://www.bitcoinwhoswho.com/api/scam"

    def __init__(
        self,
        api_key: Optional[str] = None,
        enabled: bool = False,
    ):
        """
        Initialize Bitcoin Who's Who reporter

        Args:
            api_key: API key for Bitcoin Who's Who (optional)
            enabled: Enable/disable reporting
        """
        self.api_key = api_key
        self.enabled = enabled and api_key is not None

        self.reports_submitted = 0
        self.failed_reports = 0

        if not self.enabled:
            logger.info(
                "BitcoinWhosWhoReporter disabled (no API key or explicitly disabled)"
            )
        else:
            logger.info("Initialized BitcoinWhosWhoReporter")

    async def report_scammer_addresses(
        self,
        btc_addresses: List[str],
        scam_type: str = "investment_fraud",
        description: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Report Bitcoin addresses to Bitcoin Who's Who

        Args:
            btc_addresses: List of Bitcoin addresses to report
            scam_type: Type of scam (investment_fraud, romance_scam, etc.)
            description: Description of scam interaction
            session_id: Session ID for tracking

        Returns:
            Report result dictionary
        """
        if not self.enabled:
            logger.debug("Reporting disabled, skipping Bitcoin Who's Who report")
            return {
                "success": False,
                "reason": "reporting_disabled",
                "addresses_reported": 0,
            }

        if not btc_addresses:
            logger.debug("No BTC addresses to report")
            return {
                "success": False,
                "reason": "no_addresses",
                "addresses_reported": 0,
            }

        try:
            results = []

            for address in btc_addresses:
                result = await self._submit_single_address(
                    address=address,
                    scam_type=scam_type,
                    description=description,
                    session_id=session_id,
                )
                results.append(result)

            successful = sum(1 for r in results if r.get("success"))
            failed = len(results) - successful

            self.reports_submitted += successful
            self.failed_reports += failed

            logger.info(
                f"Reported {successful}/{len(btc_addresses)} BTC addresses to "
                f"Bitcoin Who's Who (session: {session_id})"
            )

            return {
                "success": successful > 0,
                "addresses_reported": successful,
                "addresses_failed": failed,
                "total_addresses": len(btc_addresses),
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error reporting to Bitcoin Who's Who: {e}", exc_info=True)
            self.failed_reports += len(btc_addresses)
            return {
                "success": False,
                "error": str(e),
                "addresses_reported": 0,
            }

    async def _submit_single_address(
        self,
        address: str,
        scam_type: str,
        description: Optional[str],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Submit a single Bitcoin address to the API

        Args:
            address: Bitcoin address
            scam_type: Scam type
            description: Description
            session_id: Session ID

        Returns:
            Submission result
        """
        try:
            # Build description
            full_description = self._build_description(
                scam_type=scam_type,
                description=description,
                session_id=session_id,
            )

            # Prepare payload
            payload = {
                "address": address,
                "type": scam_type,
                "description": full_description,
                "reported_at": datetime.utcnow().isoformat(),
            }

            # Add API key if available
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Submit to API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.API_BASE_URL,
                    json=payload,
                    headers=headers,
                )

                if response.status_code in [200, 201]:
                    logger.debug(f"Successfully reported address: {address}")
                    return {
                        "success": True,
                        "address": address,
                        "response_code": response.status_code,
                    }
                else:
                    logger.warning(
                        f"Failed to report address {address}: "
                        f"HTTP {response.status_code}"
                    )
                    return {
                        "success": False,
                        "address": address,
                        "response_code": response.status_code,
                        "error": response.text[:200],
                    }

        except httpx.TimeoutException:
            logger.error(f"Timeout reporting address {address}")
            return {
                "success": False,
                "address": address,
                "error": "timeout",
            }
        except Exception as e:
            logger.error(f"Error reporting address {address}: {e}")
            return {
                "success": False,
                "address": address,
                "error": str(e),
            }

    def _build_description(
        self,
        scam_type: str,
        description: Optional[str],
        session_id: Optional[str],
    ) -> str:
        """Build report description"""
        parts = [
            f"Detected via SCAIPOT honeypot system ({scam_type})",
        ]

        if session_id:
            parts.append(f"Session: {session_id}")

        if description:
            parts.append(description)

        parts.append(
            "This address was extracted from a conversation with a suspected scammer."
        )

        return " | ".join(parts)

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get reporter statistics

        Returns:
            Statistics dictionary
        """
        return {
            "enabled": self.enabled,
            "reports_submitted": self.reports_submitted,
            "failed_reports": self.failed_reports,
            "api_configured": self.api_key is not None,
        }

    async def health_check(self) -> bool:
        """
        Health check

        Returns:
            True if configured and enabled
        """
        return self.enabled
