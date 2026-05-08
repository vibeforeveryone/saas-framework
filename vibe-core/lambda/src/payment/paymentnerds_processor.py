# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
PaymentNerds Payment Processor
Implementation for PaymentNerds payment gateway
"""
from typing import Dict, Any, Optional
import requests
import hashlib
import logging
from .base_processor import BasePaymentProcessor, PaymentResponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PaymentNerdsProcessor(BasePaymentProcessor):
    """
    PaymentNerds payment processor implementation
    Handles payment processing through PaymentNerds gateway
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize PaymentNerds processor"""
        super().__init__(config)
        
        # PaymentNerds-specific configuration
        self.api_key = config.get('api_key')
        self.merchant_id = config.get('merchant_id')
        self.api_secret = config.get('api_secret')  # For signature generation
        self.endpoint_url = config.get(
            'endpoint_url',
            'https://api.paymentnerds.com/v2' if not self.is_test_mode
            else 'https://sandbox.paymentnerds.com/v2'
        )
        
        if not self.api_key or not self.merchant_id:
            raise ValueError("api_key and merchant_id are required for PaymentNerds")
        
        logger.info(f"PaymentNerds processor initialized: {self.endpoint_url}")
    
    def _generate_signature(self, data: Dict[str, Any]) -> str:
        """
        Generate signature for PaymentNerds API request
        
        Args:
            data: Request data
        
        Returns:
            HMAC signature
        """
        if not self.api_secret:
            return ""
        
        # Create signature string from sorted keys
        sorted_data = sorted(data.items())
        signature_string = '&'.join([f"{k}={v}" for k, v in sorted_data])
        signature_string += self.api_secret
        
        # Generate SHA256 hash
        signature = hashlib.sha256(signature_string.encode()).hexdigest()
        return signature
    
    def _make_request(
        self,
        endpoint: str,
        method: str = 'POST',
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make API request to PaymentNerds
        
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
        
        # Add authentication to data
        if data is None:
            data = {}
        
        data['api_key'] = self.api_key
        data['merchant_id'] = self.merchant_id
        
        # Generate signature if secret is available
        if self.api_secret:
            data['signature'] = self._generate_signature(data)
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'GET':
                response = requests.get(url, params=data, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error("PaymentNerds API request timeout")
            raise Exception("Payment gateway timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"PaymentNerds API error: {str(e)}")
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
        Process payment through PaymentNerds
        
        Args:
            amount: Payment amount
            currency: Currency code
            payment_method: Payment method details
            customer_info: Customer information
            metadata: Additional metadata
        
        Returns:
            PaymentResponse with transaction result
        """
        logger.info(f"PaymentNerds processing payment: {amount} {currency}")
        
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
        
        # Build request payload
        payload = {
            'transaction_type': 'sale',
            'amount': f"{amount:.2f}",
            'currency': currency,
            'ccnumber': payment_method.get('card_number'),
            'ccexp': f"{payment_method.get('exp_month'):02d}{payment_method.get('exp_year', 0) % 100:02d}",
            'cvv': payment_method.get('cvv')
        }
        
        if customer_info:
            payload.update({
                'first_name': customer_info.get('name', '').split()[0] if customer_info.get('name') else '',
                'last_name': ' '.join(customer_info.get('name', '').split()[1:]) if customer_info.get('name') else '',
                'email': customer_info.get('email'),
                'phone': customer_info.get('phone'),
                'address1': customer_info.get('address', {}).get('street'),
                'city': customer_info.get('address', {}).get('city'),
                'state': customer_info.get('address', {}).get('state'),
                'zip': customer_info.get('address', {}).get('zip'),
                'country': customer_info.get('address', {}).get('country')
            })
        
        if metadata:
            payload['order_id'] = metadata.get('order_id')
            payload['order_description'] = metadata.get('description')
        
        try:
            # Make API call
            result = self._make_request('transactions', 'POST', payload)
            
            # Parse response
            if result.get('response') == '1':  # PaymentNerds success code
                response = PaymentResponse(
                    success=True,
                    transaction_id=result.get('transactionid'),
                    amount=amount,
                    currency=currency,
                    status='completed',
                    message=result.get('responsetext', 'Payment processed successfully'),
                    raw_response=result
                )
                
                logger.info(f"PaymentNerds payment successful: {response.transaction_id}")
            else:
                response = PaymentResponse(
                    success=False,
                    amount=amount,
                    currency=currency,
                    status='declined',
                    message=result.get('responsetext', 'Payment declined'),
                    error_code=result.get('response_code', 'DECLINED'),
                    error_details=result.get('responsetext'),
                    raw_response=result
                )
                
                logger.warning(f"PaymentNerds payment declined: {response.message}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Payment processing error: {str(e)}",
                "PROCESSING_ERROR"
            )
            logger.error(f"PaymentNerds payment error: {str(e)}")
        
        self.log_transaction('payment', payload, response)
        return response
    
    def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Refund payment through PaymentNerds
        
        Args:
            transaction_id: Original transaction ID
            amount: Refund amount (None for full refund)
            reason: Refund reason
        
        Returns:
            PaymentResponse with refund result
        """
        logger.info(f"PaymentNerds refunding transaction: {transaction_id}")
        
        payload = {
            'transaction_type': 'refund',
            'transactionid': transaction_id
        }
        
        if amount is not None:
            payload['amount'] = f"{amount:.2f}"
        
        try:
            result = self._make_request('transactions', 'POST', payload)
            
            if result.get('response') == '1':
                response = PaymentResponse(
                    success=True,
                    transaction_id=result.get('transactionid'),
                    amount=float(result.get('amount', amount or 0)),
                    currency='USD',
                    status='refunded',
                    message=result.get('responsetext', 'Refund processed successfully'),
                    raw_response=result
                )
                
                logger.info(f"PaymentNerds refund successful: {response.transaction_id}")
            else:
                response = self.create_error_response(
                    result.get('responsetext', 'Refund failed'),
                    result.get('response_code', 'REFUND_FAILED')
                )
                
                logger.warning(f"PaymentNerds refund failed: {response.message}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Refund error: {str(e)}",
                "REFUND_ERROR"
            )
            logger.error(f"PaymentNerds refund error: {str(e)}")
        
        self.log_transaction('refund', payload, response)
        return response
    
    def void_payment(
        self,
        transaction_id: str,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Void payment through PaymentNerds
        
        Args:
            transaction_id: Transaction ID to void
            reason: Void reason
        
        Returns:
            PaymentResponse with void result
        """
        logger.info(f"PaymentNerds voiding transaction: {transaction_id}")
        
        payload = {
            'transaction_type': 'void',
            'transactionid': transaction_id
        }
        
        try:
            result = self._make_request('transactions', 'POST', payload)
            
            if result.get('response') == '1':
                response = PaymentResponse(
                    success=True,
                    transaction_id=result.get('transactionid'),
                    status='voided',
                    message=result.get('responsetext', 'Transaction voided successfully'),
                    raw_response=result
                )
                
                logger.info(f"PaymentNerds void successful: {response.transaction_id}")
            else:
                response = self.create_error_response(
                    result.get('responsetext', 'Void failed'),
                    result.get('response_code', 'VOID_FAILED')
                )
                
                logger.warning(f"PaymentNerds void failed: {response.message}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Void error: {str(e)}",
                "VOID_ERROR"
            )
            logger.error(f"PaymentNerds void error: {str(e)}")
        
        self.log_transaction('void', payload, response)
        return response
    
    def get_transaction_status(
        self,
        transaction_id: str
    ) -> PaymentResponse:
        """
        Get transaction status from PaymentNerds
        
        Args:
            transaction_id: Transaction ID to check
        
        Returns:
            PaymentResponse with current status
        """
        logger.info(f"PaymentNerds checking transaction: {transaction_id}")
        
        payload = {
            'transactionid': transaction_id
        }
        
        try:
            result = self._make_request('query', 'GET', payload)
            
            response = PaymentResponse(
                success=True,
                transaction_id=transaction_id,
                amount=float(result.get('amount', 0)),
                currency=result.get('currency', 'USD'),
                status=result.get('transaction_type'),
                message=f"Transaction status: {result.get('transaction_type')}",
                raw_response=result
            )
            
            logger.info(f"PaymentNerds status: {response.status}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Status check error: {str(e)}",
                "STATUS_CHECK_ERROR"
            )
            logger.error(f"PaymentNerds status check error: {str(e)}")
        
        return response
    
    def validate_credentials(self) -> bool:
        """
        Validate PaymentNerds credentials
        
        Returns:
            True if credentials are valid
        """
        logger.info("Validating PaymentNerds credentials")
        
        try:
            # Make a test API call with minimal data
            result = self._make_request('validate', 'GET', {})
            
            if result.get('response') in ['1', '100']:  # Success codes
                logger.info("PaymentNerds credentials valid")
                return True
            else:
                logger.warning("PaymentNerds credentials invalid")
                return False
                
        except Exception as e:
            logger.error(f"PaymentNerds credential validation error: {str(e)}")
            return False
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get PaymentNerds processor capabilities
        
        Returns:
            Dictionary of supported features
        """
        return {
            'process_payment': True,
            'refund_payment': True,
            'void_payment': True,
            'get_transaction_status': True,
            'recurring_payments': True,
            'tokenization': False,
            'fraud_detection': True
        }
