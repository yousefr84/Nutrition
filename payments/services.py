from dataclasses import dataclass

import requests
from django.conf import settings


class PaymentGatewayError(Exception):
    """Base class for errors returned by or while calling the gateway."""


class PaymentGatewayConfigurationError(PaymentGatewayError):
    pass


class PaymentGatewayTimeout(PaymentGatewayError):
    pass


@dataclass(frozen=True)
class GatewayResult:
    code: int
    authority: str | None = None


def _merchant_id() -> str:
    merchant_id = settings.ZARINPAL_MERCHANT_ID.strip()
    if not merchant_id:
        raise PaymentGatewayConfigurationError('Payment gateway is not configured')
    return merchant_id


def _parse_response(response: requests.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise PaymentGatewayError('Payment gateway returned an invalid response') from exc

    if response.status_code >= 500:
        raise PaymentGatewayError('Payment gateway is temporarily unavailable')
    if response.status_code >= 400:
        errors = payload.get('errors') if isinstance(payload, dict) else None
        raise PaymentGatewayError(f'Payment gateway rejected the request: {errors or response.status_code}')

    return payload


def _extract_gateway_data(payload: dict) -> dict:
    # Zarinpal v4 wraps successful fields in `data`; the fallback keeps this
    # adapter compatible with legacy-shaped responses during migration.
    data = payload.get('data', payload)
    if not isinstance(data, dict):
        raise PaymentGatewayError('Payment gateway returned malformed data')
    return data


def create_gateway_payment(*, amount: int, description: str, phone: str) -> GatewayResult:
    body = {
        'merchant_id': _merchant_id(),
        'amount': amount,
        'callback_url': settings.ZARINPAL_CALLBACK_URL,
        'description': description,
        'metadata': {'mobile': phone},
    }

    try:
        response = requests.post(
            settings.ZARINPAL_REQUEST_URL,
            json=body,
            timeout=settings.ZARINPAL_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise PaymentGatewayTimeout('Payment gateway timed out') from exc
    except requests.RequestException as exc:
        raise PaymentGatewayError('Could not connect to payment gateway') from exc

    data = _extract_gateway_data(_parse_response(response))
    code = int(data.get('code', data.get('Status', 0)))
    authority = data.get('authority', data.get('Authority'))
    if code != 100 or not authority:
        raise PaymentGatewayError(f'Payment gateway rejected the request with code {code}')

    return GatewayResult(code=code, authority=str(authority))


def verify_gateway_payment(*, amount: int, authority: str) -> GatewayResult:
    body = {
        'merchant_id': _merchant_id(),
        'amount': amount,
        'authority': authority,
    }

    try:
        response = requests.post(
            settings.ZARINPAL_VERIFY_URL,
            json=body,
            timeout=settings.ZARINPAL_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise PaymentGatewayTimeout('Payment verification timed out') from exc
    except requests.RequestException as exc:
        raise PaymentGatewayError('Could not connect to payment gateway') from exc

    data = _extract_gateway_data(_parse_response(response))
    return GatewayResult(code=int(data.get('code', data.get('Status', 0))))
