# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
MerchantOne Payment Processor
Implementation for MerchantOne payment gateway
"""
from typing import Dict, Any, Optional
import requests
import logging
from .base_processor import BasePaymentProcessor, PaymentResponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class MerchantOneProcessor(BasePaymentProcessor):
    """
    MerchantOne payment processor implementation
    Handles payment processing through MerchantOne gateway
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize MerchantOne processor"""
        super().__init__(config)
        
        # MerchantOne-specific configuration
        self.api_key = config.get('api_key')
        self.merchant_id = config.get('merchant_id')
        self.endpoint_url = config.get(
            'endpoint_url',
            'https://api.merchantone.com/v1' if not self.is_test_mode
            else 'https://sandbox.merchantone.com/v1'
        )
        
        if not self.api_key or not self.merchant_id:
            raise ValueError("api_key and merchant_id are required for MerchantOne")
        
        logger.info(f"MerchantOne processor initialized: {self.endpoint_url}")
    
    def _make_request(
        self,
        endpoint: str,
        method: str = 'POST',
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make API request to MerchantOne
        
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
            'Authorization': f"Bearer {self.api_key}",
            'Content-Type': 'application/json',
            'X-Merchant-ID': self.merchant_id
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
            logger.error("MerchantOne API request timeout")
            raise Exception("Payment gateway timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"MerchantOne API error: {str(e)}")
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
        Process payment through MerchantOne
        
        Args:
            amount: Payment amount
            currency: Currency code
            payment_method: Payment method details (card info)
            customer_info: Customer information
            metadata: Additional metadata
        
        Returns:
            PaymentResponse with transaction result
        """
        logger.info(f"MerchantOne processing payment: {amount} {currency}")
        
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
            'amount': amount,
            'currency': currency,
            'payment_method': {
                'type': payment_method.get('type', 'card'),
                'card_number': payment_method.get('card_number'),
                'exp_month': payment_method.get('exp_month'),
                'exp_year': payment_method.get('exp_year'),
                'cvv': payment_method.get('cvv')
            }
        }
        
        if customer_info:
            payload['customer'] = {
                'name': customer_info.get('name'),
                'email': customer_info.get('email'),
                'phone': customer_info.get('phone'),
                'address': customer_info.get('address')
            }
        
        if metadata:
            payload['metadata'] = metadata
        
        try:
            # Make API call
            result = self._make_request('transactions', 'POST', payload)
            
            # Parse response
            if result.get('status') == 'approved':
                response = PaymentResponse(
                    success=True,
                    transaction_id=result.get('transaction_id'),
                    amount=amount,
                    currency=currency,
                    status='completed',
                    message='Payment processed successfully',
                    raw_response=result
                )
                
                logger.info(f"MerchantOne payment successful: {response.transaction_id}")
            else:
                response = PaymentResponse(
                    success=False,
                    amount=amount,
                    currency=currency,
                    status='declined',
                    message=result.get('message', 'Payment declined'),
                    error_code=result.get('error_code', 'DECLINED'),
                    error_details=result.get('error_details'),
                    raw_response=result
                )
                
                logger.warning(f"MerchantOne payment declined: {response.message}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Payment processing error: {str(e)}",
                "PROCESSING_ERROR"
            )
            logger.error(f"MerchantOne payment error: {str(e)}")
        
        self.log_transaction('payment', payload, response)
        return response
    
    def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Refund payment through MerchantOne
        
        Args:
            transaction_id: Original transaction ID
            amount: Refund amount (None for full refund)
            reason: Refund reason
        
        Returns:
            PaymentResponse with refund result
        """
        logger.info(f"MerchantOne refunding transaction: {transaction_id}")
        
        payload = {
            'transaction_id': transaction_id,
            'reason': reason
        }
        
        if amount is not None:
            payload['amount'] = amount
        
        try:
            result = self._make_request('refunds', 'POST', payload)
            
            if result.get('status') == 'approved':
                response = PaymentResponse(
                    success=True,
                    transaction_id=result.get('refund_id'),
                    amount=result.get('amount'),
                    currency=result.get('currency', 'USD'),
                    status='refunded',
                    message='Refund processed successfully',
                    raw_response=result
                )
                
                logger.info(f"MerchantOne refund successful: {response.transaction_id}")
            else:
                response = self.create_error_response(
                    result.get('message', 'Refund failed'),
                    result.get('error_code', 'REFUND_FAILED')
                )
                
                logger.warning(f"MerchantOne refund failed: {response.message}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Refund error: {str(e)}",
                "REFUND_ERROR"
            )
            logger.error(f"MerchantOne refund error: {str(e)}")
        
        self.log_transaction('refund', payload, response)
        return response
    
    def void_payment(
        self,
        transaction_id: str,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Void payment through MerchantOne
        
        Args:
            transaction_id: Transaction ID to void
            reason: Void reason
        
        Returns:
            PaymentResponse with void result
        """
        logger.info(f"MerchantOne voiding transaction: {transaction_id}")
        
        payload = {
            'transaction_id': transaction_id,
            'reason': reason
        }
        
        try:
            result = self._make_request('voids', 'POST', payload)
            
            if result.get('status') == 'voided':
                response = PaymentResponse(
                    success=True,
                    transaction_id=result.get('void_id'),
                    status='voided',
                    message='Transaction voided successfully',
                    raw_response=result
                )
                
                logger.info(f"MerchantOne void successful: {response.transaction_id}")
            else:
                response = self.create_error_response(
                    result.get('message', 'Void failed'),
                    result.get('error_code', 'VOID_FAILED')
                )
                
                logger.warning(f"MerchantOne void failed: {response.message}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Void error: {str(e)}",
                "VOID_ERROR"
            )
            logger.error(f"MerchantOne void error: {str(e)}")
        
        self.log_transaction('void', payload, response)
        return response
    
    def get_transaction_status(
        self,
        transaction_id: str
    ) -> PaymentResponse:
        """
        Get transaction status from MerchantOne
        
        Args:
            transaction_id: Transaction ID to check
        
        Returns:
            PaymentResponse with current status
        """
        logger.info(f"MerchantOne checking transaction: {transaction_id}")
        
        try:
            result = self._make_request(f'transactions/{transaction_id}', 'GET')
            
            response = PaymentResponse(
                success=True,
                transaction_id=transaction_id,
                amount=result.get('amount'),
                currency=result.get('currency'),
                status=result.get('status'),
                message=f"Transaction status: {result.get('status')}",
                raw_response=result
            )
            
            logger.info(f"MerchantOne status: {response.status}")
            
        except Exception as e:
            response = self.create_error_response(
                f"Status check error: {str(e)}",
                "STATUS_CHECK_ERROR"
            )
            logger.error(f"MerchantOne status check error: {str(e)}")
        
        return response
    
    def validate_credentials(self) -> bool:
        """
        Validate MerchantOne credentials
        
        Returns:
            True if credentials are valid
        """
        logger.info("Validating MerchantOne credentials")
        
        try:
            # Make a test API call
            result = self._make_request('validate', 'GET')
            
            if result.get('valid'):
                logger.info("MerchantOne credentials valid")
                return True
            else:
                logger.warning("MerchantOne credentials invalid")
                return False
                
        except Exception as e:
            logger.error(f"MerchantOne credential validation error: {str(e)}")
            return False
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get MerchantOne processor capabilities
        
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
