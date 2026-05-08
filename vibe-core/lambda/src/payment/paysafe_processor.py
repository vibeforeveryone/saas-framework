# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
PaySafe Payment Processor
Implementation for PaySafe (Paysafe) payment gateway
"""
from typing import Dict, Any, Optional
import requests
import base64
import logging
from .base_processor import BasePaymentProcessor, PaymentResponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PaySafeProcessor(BasePaymentProcessor):
    """
    PaySafe payment processor implementation
    Handles payment processing through PaySafe gateway
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize PaySafe processor"""
        super().__init__(config)
        
        # PaySafe-specific configuration
        self.api_key = config.get('api_key')
        self.api_secret = config.get('api_secret')
        self.account_number = config.get('merchant_id')  # PaySafe uses account number
        self.endpoint_url = config.get(
            'endpoint_url',
            'https://api.paysafe.com/cardpayments/v1' if not self.is_test_mode
            else 'https://api.test.paysafe.com/cardpayments/v1'
        )
        
        if not self.api_key or not self.api_secret:
            raise ValueError("api_key and api_secret are required for PaySafe")
        
        logger.info(f"PaySafe processor initialized: {self.endpoint_url}")
    
    def _get_auth_header(self) -> str:
        """
        Generate Basic Auth header for PaySafe API
        
        Returns:
            Base64 encoded auth string
        """
        credentials = f"{self.api_key}:{self.api_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    def _make_request(
        self,
        endpoint: str,
        method: str = 'POST',
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make API request to PaySafe
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            data: Request payload
        
        Returns:
            Response data
        
        Raises:
            Exception: On API error
        """
        url = f"{self.endpoint_url}/{endpoint}"
        headers = {
            'Authorization': self._get_auth_header(),
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error("PaySafe API request timeout")
            raise Exception("Payment gateway timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"PaySafe API error: {str(e)}")
            raise Exception(f"Payment gateway error: {str(e)}")
    
    def process_payment(
        self,
        amount: float,
        currency: str,
        payment_method: Dict[str, Any],
        customer_info: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentResponse:
        """
        Process payment through PaySafe
        
        Args:
            amount: Payment amount
            currency: Currency code
            payment_method: Payment method details
            customer_info: Customer information
            metadata: Additional metadata
        
        Returns:
            PaymentResponse with transaction result
        """
        logger.info(f"PaySafe processing payment: {amount} {currency}")
        
        # Validate inputs
        if not self.validate_amount(amount, currency):
            return self.create_error_response(
                "Invalid amount",
                "INVALID_AMOUNT"
            )
        
        if not self.validate_currency(currency):
            return self.create_error_response(
                f"Unsupported currency: {currency}",
                "INVALID_CURRENCY"
            )
        
        # Convert amount to cents (PaySafe uses smallest currency unit)
        amount_in_cents = int(amount * 100)
        
        # Build request payload (PaySafe format)
        payload = {
            'merchantRefNum': metadata.get('order_id', f'order_{int(amount * 1000)}') if metadata else f'order_{int(amount * 1000)}',
            'amount': amount_in_cents,
            'currencyCode': currency,
            'card': {
                'cardNum': payment_method.get('card_number'),
                'cardExpiry': {
                    'month': payment_method.get('exp_month'),
                    'year': payment_method.get('exp_year')
                },
                'cvv': payment_method.get('cvv')
            }
        }
        
        if customer_info:
            payload['billingDetails'] = {
                'street': customer_info.get('address', {}).get('street'),
                'city': customer_info.get('address', {}).get('city'),
                'state': customer_info.get('address', {}).get('state'),
                'country': customer_info.get('address', {}).get('country'),
                'zip': customer_info.get('address', {}).get('zip')
            }
        
        try:
            # Make API call
            result = self._make_request('accounts/' + (self.account_number or 'default') + '/auths', 'POST', payload)
            
            # Parse response
            if result.get('status') == 'COMPLETED':
                response = PaymentResponse(
                    success=True,
                    transaction_id=result.get('id'),
                    amount=amount,
                    currency=currency,
                    status='completed',
                    message='Payment processed successfully',
                    raw_response=result
                )
                
                logger.info(f"PaySafe payment successful: {response.transaction_id}")
            else:
                response = PaymentResponse(
                    success=False,
                    amount=amount,
                    currency=currency,
                    status=result.get('status', 'declined'),
                    message=result.get('authCode', 'Payment declined'),
                    error_code=result.get('error', {}).get('code', 'DECLINED'),
                    error_details=result.get('error', {}).get('message'),
                    raw_response=result
                )
                
                logger.warning(f"PaySafe payment declined: {response.message}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Payment processing error: {str(e)}",
                "PROCESSING_ERROR"
            )
            logger.error(f"PaySafe payment error: {str(e)}")
        
        self.log_transaction('payment', payload, response)
        return response
    
    def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Refund payment through PaySafe
        
        Args:
            transaction_id: Original transaction ID
            amount: Refund amount (None for full refund)
            reason: Refund reason
        
        Returns:
            PaymentResponse with refund result
        """
        logger.info(f"PaySafe refunding transaction: {transaction_id}")
        
        payload = {
            'merchantRefNum': f'refund_{transaction_id[:10]}'
        }
        
        if amount is not None:
            payload['amount'] = int(amount * 100)  # Convert to cents
        
        try:
            result = self._make_request(
                f'accounts/{self.account_number or "default"}/settlements/{transaction_id}/refunds',
                'POST',
                payload
            )
            
            if result.get('status') == 'COMPLETED':
                response = PaymentResponse(
                    success=True,
                    transaction_id=result.get('id'),
                    amount=result.get('amount', 0) / 100,  # Convert from cents
                    currency=result.get('currencyCode', 'USD'),
                    status='refunded',
                    message='Refund processed successfully',
                    raw_response=result
                )
                
                logger.info(f"PaySafe refund successful: {response.transaction_id}")
            else:
                response = self.create_error_response(
                    result.get('error', {}).get('message', 'Refund failed'),
                    result.get('error', {}).get('code', 'REFUND_FAILED')
                )
                
                logger.warning(f"PaySafe refund failed: {response.message}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Refund error: {str(e)}",
                "REFUND_ERROR"
            )
            logger.error(f"PaySafe refund error: {str(e)}")
        
        self.log_transaction('refund', payload, response)
        return response
    
    def void_payment(
        self,
        transaction_id: str,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Void payment through PaySafe
        
        Args:
            transaction_id: Transaction ID to void
            reason: Void reason
        
        Returns:
            PaymentResponse with void result
        """
        logger.info(f"PaySafe voiding transaction: {transaction_id}")
        
        payload = {
            'status': 'CANCELLED'
        }
        
        try:
            result = self._make_request(
                f'accounts/{self.account_number or "default"}/auths/{transaction_id}',
                'POST',
                payload
            )
            
            if result.get('status') == 'CANCELLED':
                response = PaymentResponse(
                    success=True,
                    transaction_id=transaction_id,
                    status='voided',
                    message='Transaction voided successfully',
                    raw_response=result
                )
                
                logger.info(f"PaySafe void successful: {transaction_id}")
            else:
                response = self.create_error_response(
                    result.get('error', {}).get('message', 'Void failed'),
                    result.get('error', {}).get('code', 'VOID_FAILED')
                )
                
                logger.warning(f"PaySafe void failed: {response.message}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Void error: {str(e)}",
                "VOID_ERROR"
            )
            logger.error(f"PaySafe void error: {str(e)}")
        
        self.log_transaction('void', payload, response)
        return response
    
    def get_transaction_status(
        self,
        transaction_id: str
    ) -> PaymentResponse:
        """
        Get transaction status from PaySafe
        
        Args:
            transaction_id: Transaction ID to check
        
        Returns:
            PaymentResponse with current status
        """
        logger.info(f"PaySafe checking transaction: {transaction_id}")
        
        try:
            result = self._make_request(
                f'accounts/{self.account_number or "default"}/auths/{transaction_id}',
                'GET'
            )
            
            response = PaymentResponse(
                success=True,
                transaction_id=transaction_id,
                amount=result.get('amount', 0) / 100,  # Convert from cents
                currency=result.get('currencyCode'),
                status=result.get('status'),
                message=f"Transaction status: {result.get('status')}",
                raw_response=result
            )
            
            logger.info(f"PaySafe status: {response.status}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Status check error: {str(e)}",
                "STATUS_CHECK_ERROR"
            )
            logger.error(f"PaySafe status check error: {str(e)}")
        
        return response
    
    def validate_credentials(self) -> bool:
        """
        Validate PaySafe credentials
        
        Returns:
            True if credentials are valid
        """
        logger.info("Validating PaySafe credentials")
        
        try:
            # Make a test API call to validate credentials
            self._make_request(f'accounts/{self.account_number or "default"}', 'GET')
            logger.info("PaySafe credentials valid")
            return True
                
        except Exception as e:
            logger.error(f"PaySafe credential validation error: {str(e)}")
            return False
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get PaySafe processor capabilities
        
        Returns:
            Dictionary of supported features
        """
        return {
            'process_payment': True,
            'refund_payment': True,
            'void_payment': True,
            'get_transaction_status': True,
            'recurring_payments': True,
            'tokenization': True,
            'fraud_detection': True
        }
