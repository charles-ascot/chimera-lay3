"""
CHIMERA v2 Betfair REST API Client
Handles authentication, market data, orders, and account operations.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

import httpx

from config import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Betfair Error Code Mapping
# ─────────────────────────────────────────────────────────────────

BETFAIR_ERROR_MESSAGES = {
    "INVALID_USERNAME_OR_PASSWORD": "Invalid username or password",
    "ACCOUNT_NOW_LOCKED": "Account has been locked",
    "ACCOUNT_ALREADY_LOCKED": "Account is already locked",
    "PENDING_AUTH": "Pending authentication required",
    "SUSPENDED": "Account is suspended",
    "CLOSED": "Account is closed",
    "SELF_EXCLUDED": "Account is self-excluded",
    "SECURITY_RESTRICTED_LOCATION": "Access restricted from your location",
    "BETTING_RESTRICTED_LOCATION": "Betting restricted from your location",
    "TEMPORARY_BAN_TOO_MANY_REQUESTS": "Too many login attempts. Banned for 20 minutes",
    "ACTIONS_REQUIRED": "Please login to betfair.com to complete required actions",
    "CERT_AUTH_REQUIRED": "Certificate authentication required",
    "CHANGE_PASSWORD_REQUIRED": "Password change required",
    "INTERNATIONAL_TERMS_ACCEPTANCE_REQUIRED": "International terms must be accepted",
}


class BetfairAPIError(Exception):
    """Custom exception for Betfair API errors."""
    def __init__(self, message: str, status_code: int = 400, error_code: str = ""):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


class BetfairClient:
    """Async client for Betfair Exchange REST API."""

    def __init__(self):
        self.app_key = config.BETFAIR_APP_KEY
        self._client: Optional[httpx.AsyncClient] = None
        self._session_token: Optional[str] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Accept-Encoding": "gzip"}
            )
        return self._client

    @property
    def session_token(self) -> Optional[str]:
        return self._session_token

    @session_token.setter
    def session_token(self, token: Optional[str]):
        self._session_token = token

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self, session_token: Optional[str] = None) -> Dict[str, str]:
        """Build headers for Betfair API requests."""
        token = session_token or self._session_token
        headers = {
            "X-Application": self.app_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        }
        if token:
            headers["X-Authentication"] = token
        return headers

    # ─────────────────────────────────────────────────────────────
    # Authentication
    # ─────────────────────────────────────────────────────────────

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate with Betfair using interactive login."""
        body = urlencode({"username": username, "password": password})
        headers = {
            "Accept": "application/json",
            "X-Application": self.app_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        logger.info(f"Attempting login for user: {username}")

        try:
            response = await self.client.post(
                config.BETFAIR_LOGIN_URL, content=body, headers=headers
            )

            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                logger.error(f"Non-JSON response: {content_type}")
                raise BetfairAPIError(
                    "Betfair returned non-JSON response. May be geo-blocked.",
                    status_code=502,
                )

            result = response.json()

            if result.get("status") == "SUCCESS":
                self._session_token = result.get("token")
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(hours=config.SESSION_TIMEOUT_HOURS)
                ).isoformat()
                return {
                    "session_token": self._session_token,
                    "status": "SUCCESS",
                    "expires_at": expires_at,
                }
            elif result.get("status") == "LIMITED_ACCESS":
                self._session_token = result.get("token")
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(hours=config.SESSION_TIMEOUT_HOURS)
                ).isoformat()
                return {
                    "session_token": self._session_token,
                    "status": "LIMITED_ACCESS",
                    "expires_at": expires_at,
                    "warning": "Account has limited access",
                }
            else:
                error_code = result.get("error", "UNKNOWN_ERROR")
                error_message = BETFAIR_ERROR_MESSAGES.get(
                    error_code, f"Authentication failed: {error_code}"
                )
                raise BetfairAPIError(error_message, status_code=401, error_code=error_code)

        except httpx.RequestError as e:
            raise BetfairAPIError(f"Failed to connect to Betfair: {e}", status_code=503)

    async def keep_alive(self, session_token: Optional[str] = None) -> Dict[str, Any]:
        """Extend session lifetime."""
        token = session_token or self._session_token
        headers = {
            "Accept": "application/json",
            "X-Application": self.app_key,
            "X-Authentication": token,
        }

        try:
            response = await self.client.get(config.BETFAIR_KEEPALIVE_URL, headers=headers)
            result = response.json()

            if result.get("status") == "SUCCESS":
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(hours=config.SESSION_TIMEOUT_HOURS)
                ).isoformat()
                return {"status": "SUCCESS", "token": result.get("token"), "expires_at": expires_at}
            else:
                raise BetfairAPIError("Session expired or invalid", status_code=401)

        except httpx.RequestError as e:
            raise BetfairAPIError(str(e), status_code=503)

    async def logout(self, session_token: Optional[str] = None) -> Dict[str, Any]:
        """Terminate session."""
        token = session_token or self._session_token
        headers = {
            "Accept": "application/json",
            "X-Application": self.app_key,
            "X-Authentication": token,
        }

        try:
            response = await self.client.get(config.BETFAIR_LOGOUT_URL, headers=headers)
            self._session_token = None
            return response.json()
        except httpx.RequestError as e:
            self._session_token = None
            return {"status": "ERROR", "error": str(e)}

    # ─────────────────────────────────────────────────────────────
    # JSON-RPC API Request
    # ─────────────────────────────────────────────────────────────

    async def _api_request(
        self,
        method: str,
        params: Dict[str, Any],
        session_token: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ) -> Any:
        """Make JSON-RPC request to Betfair API."""
        token = session_token or self._session_token
        if not token:
            raise BetfairAPIError("Not authenticated", status_code=401)

        payload = {
            "jsonrpc": "2.0",
            "method": f"SportsAPING/v1.0/{method}",
            "params": params,
            "id": 1,
        }

        url = endpoint_url or config.BETFAIR_API_URL

        try:
            response = await self.client.post(
                url, json=payload, headers=self._get_headers(token)
            )
            result = response.json()

            if "error" in result:
                error = result["error"]
                error_data = error.get("data", {})

                if error_data.get("exceptionname") == "INVALID_SESSION_INFORMATION":
                    raise BetfairAPIError("Session expired", status_code=401)

                raise BetfairAPIError(
                    error.get("message", str(error)), status_code=400
                )

            return result.get("result", {})

        except httpx.RequestError as e:
            raise BetfairAPIError(str(e), status_code=503)

    async def _account_request(
        self, method: str, params: Dict[str, Any], session_token: Optional[str] = None
    ) -> Any:
        """Make JSON-RPC request to Betfair Account API."""
        token = session_token or self._session_token
        if not token:
            raise BetfairAPIError("Not authenticated", status_code=401)

        payload = {
            "jsonrpc": "2.0",
            "method": f"AccountAPING/v1.0/{method}",
            "params": params,
            "id": 1,
        }

        try:
            response = await self.client.post(
                config.BETFAIR_ACCOUNT_URL,
                json=payload,
                headers=self._get_headers(token),
            )
            result = response.json()

            if "error" in result:
                error = result["error"]
                raise BetfairAPIError(
                    error.get("message", str(error)), status_code=400
                )

            return result.get("result", {})

        except httpx.RequestError as e:
            raise BetfairAPIError(str(e), status_code=503)

    # ─────────────────────────────────────────────────────────────
    # Markets
    # ─────────────────────────────────────────────────────────────

    async def list_market_catalogue(
        self,
        event_type_ids: List[str] = None,
        market_type_codes: List[str] = None,
        country_codes: List[str] = None,
        max_results: int = 500,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve market catalogue for horse racing."""
        now = datetime.now(timezone.utc)

        params = {
            "filter": {
                "eventTypeIds": event_type_ids or config.EVENT_TYPE_IDS,
                "marketTypeCodes": market_type_codes or config.MARKET_TYPES,
                "marketCountries": country_codes or config.COUNTRY_CODES,
                "marketStartTime": {
                    "from": from_time or now.isoformat(),
                    "to": to_time
                    or (now + timedelta(days=1))
                    .replace(hour=23, minute=59, second=59)
                    .isoformat(),
                },
            },
            "marketProjection": [
                "RUNNER_DESCRIPTION",
                "MARKET_START_TIME",
                "EVENT",
                "COMPETITION",
            ],
            "sort": "FIRST_TO_START",
            "maxResults": max_results,
        }

        return await self._api_request("listMarketCatalogue", params)

    async def list_market_book(
        self,
        market_ids: List[str],
        price_projection: List[str] = None,
        virtualise: bool = True,
    ) -> List[Dict[str, Any]]:
        """Retrieve real-time market book with prices."""
        params = {
            "marketIds": market_ids,
            "priceProjection": {
                "priceData": price_projection or ["EX_BEST_OFFERS"],
                "virtualise": virtualise,
            },
        }
        return await self._api_request("listMarketBook", params)

    # ─────────────────────────────────────────────────────────────
    # Orders
    # ─────────────────────────────────────────────────────────────

    async def place_orders(
        self,
        market_id: str,
        selection_id: int,
        odds: float,
        stake: float,
        side: str = "LAY",
        persistence_type: str = "LAPSE",
    ) -> Dict[str, Any]:
        """Place a bet on the exchange."""
        params = {
            "marketId": market_id,
            "instructions": [
                {
                    "selectionId": selection_id,
                    "side": side,
                    "orderType": "LIMIT",
                    "limitOrder": {
                        "size": round(stake, 2),
                        "price": round(odds, 2),
                        "persistenceType": persistence_type,
                    },
                }
            ],
        }
        return await self._api_request("placeOrders", params)

    async def cancel_orders(
        self, market_id: str, bet_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel unmatched orders."""
        params = {"marketId": market_id}
        if bet_id:
            params["instructions"] = [{"betId": bet_id}]
        return await self._api_request("cancelOrders", params)

    async def list_current_orders(
        self, market_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """List current unmatched/matched orders."""
        params = {}
        if market_ids:
            params["marketIds"] = market_ids
        return await self._api_request("listCurrentOrders", params)

    # ─────────────────────────────────────────────────────────────
    # Account
    # ─────────────────────────────────────────────────────────────

    async def get_account_funds(self) -> Dict[str, Any]:
        """Get account balance and funds."""
        return await self._account_request("getAccountFunds", {})

    async def get_account_statement(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        record_count: int = 100,
    ) -> Dict[str, Any]:
        """Get account statement."""
        params = {"recordCount": record_count}

        item_date_range = {}
        if from_date:
            item_date_range["from"] = from_date
        if to_date:
            item_date_range["to"] = to_date
        if item_date_range:
            params["itemDateRange"] = item_date_range

        return await self._account_request("getAccountStatement", params)


# Singleton instance
betfair_client = BetfairClient()
