# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Mock Payment Processor
For testing and development - simulates payment processing without actual transactions
"""
from typing import Dict, Any, Optional
import uuid
import random
import logging
from .base_processor import BasePaymentProcessor, PaymentResponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class MockPaymentProcessor(BasePaymentProcessor):
    """
    Mock payment processor for testing
    Simulates payment processing with configurable success/failure rates
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize mock processor"""
        super().__init__(config)
        
        # Mock-specific configuration
        self.success_rate = config.get('success_rate', 0.95)  # 95% success rate
        self.processing_delay = config.get('processing_delay', 0)  # Simulated delay
        self.failure_reasons = [
            'Insufficient funds',
            'Card declined',
            'Invalid card number',
            'Expired card',
            'Processing error'
        ]
        
        logger.info(f"Mock processor initialized with {self.success_rate * 100}% success rate")
    
    def process_payment(
        self,
        amount: float,
        currency: str,
        payment_method: Dict[str, Any],
        customer_info: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentResponse:
        """
        Mock payment processing
        
        Args:
            amount: Payment amount
            currency: Currency code
            payment_method: Payment method details
            customer_info: Customer information
            metadata: Additional metadata
        
        Returns:
            PaymentResponse with simulated transaction
        """
        logger.info(f"Mock processing payment: {amount} {currency}")
        
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
        
        # Simulate success/failure based on success rate
        is_successful = random.random() < self.success_rate
        
        if is_successful:
            transaction_id = f"mock_{uuid.uuid4().hex[:16]}"
            
            response = PaymentResponse(
                success=True,
                transaction_id=transaction_id,
                amount=amount,
                currency=currency,
                status='completed',
                message='Payment processed successfully (mock)',
                raw_response={
                    'mock_processor': True,
                    'payment_method': payment_method.get('type', 'unknown'),
                    'customer_name': customer_info.get('name') if customer_info else None,
                    'metadata': metadata
                }
            )
            
            logger.info(f"Mock payment successful: {transaction_id}")
        else:
            # Simulate random failure
            failure_reason = random.choice(self.failure_reasons)
            
            response = PaymentResponse(
                success=False,
                amount=amount,
                currency=currency,
                status='failed',
                message=failure_reason,
                error_code='MOCK_FAILURE',
                error_details=f"Mock failure: {failure_reason}",
                raw_response={
                    'mock_processor': True,
                    'simulated_failure': True
                }
            )
            
            logger.warning(f"Mock payment failed: {failure_reason}")
        
        self.log_transaction('payment', {
            'amount': amount,
            'currency': currency,
            'payment_method': payment_method
        }, response)
        
        return response
    
    def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Mock refund processing
        
        Args:
            transaction_id: Original transaction ID
            amount: Refund amount
            reason: Refund reason
        
        Returns:
            PaymentResponse with simulated refund
        """
        logger.info(f"Mock refunding transaction: {transaction_id}")
        
        # Validate transaction ID format
        if not transaction_id.startswith('mock_'):
            return self.create_error_response(
                "Invalid transaction ID for mock processor",
                "INVALID_TRANSACTION_ID"
            )
        
        # Simulate success/failure
        is_successful = random.random() < self.success_rate
        
        if is_successful:
            refund_id = f"refund_{uuid.uuid4().hex[:16]}"
            
            response = PaymentResponse(
                success=True,
                transaction_id=refund_id,
                amount=amount,
                currency='USD',
                status='refunded',
                message='Refund processed successfully (mock)',
                raw_response={
                    'original_transaction_id': transaction_id,
                    'refund_reason': reason,
                    'mock_processor': True
                }
            )
            
            logger.info(f"Mock refund successful: {refund_id}")
        else:
            response = self.create_error_response(
                "Refund failed (mock)",
                "REFUND_FAILED"
            )
            
            logger.warning("Mock refund failed")
        
        self.log_transaction('refund', {
            'transaction_id': transaction_id,
            'amount': amount,
            'reason': reason
        }, response)
        
        return response
    
    def void_payment(
        self,
        transaction_id: str,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Mock void/cancellation
        
        Args:
            transaction_id: Transaction ID to void
            reason: Void reason
        
        Returns:
            PaymentResponse with simulated void
        """
        logger.info(f"Mock voiding transaction: {transaction_id}")
        
        # Validate transaction ID format
        if not transaction_id.startswith('mock_'):
            return self.create_error_response(
                "Invalid transaction ID for mock processor",
                "INVALID_TRANSACTION_ID"
            )
        
        # Simulate success
        void_id = f"void_{uuid.uuid4().hex[:16]}"
        
        response = PaymentResponse(
            success=True,
            transaction_id=void_id,
            status='voided',
            message='Transaction voided successfully (mock)',
            raw_response={
                'original_transaction_id': transaction_id,
                'void_reason': reason,
                'mock_processor': True
            }
        )
        
        logger.info(f"Mock void successful: {void_id}")
        
        self.log_transaction('void', {
            'transaction_id': transaction_id,
            'reason': reason
        }, response)
        
        return response
    
    def get_transaction_status(
        self,
        transaction_id: str
    ) -> PaymentResponse:
        """
        Mock transaction status check
        
        Args:
            transaction_id: Transaction ID to check
        
        Returns:
            PaymentResponse with simulated status
        """
        logger.info(f"Mock checking transaction status: {transaction_id}")
        
        # Validate transaction ID format
        if not transaction_id.startswith('mock_'):
            return self.create_error_response(
                "Invalid transaction ID for mock processor",
                "INVALID_TRANSACTION_ID"
            )
        
        # Simulate random status
        statuses = ['completed', 'pending', 'processing']
        status = random.choice(statuses)
        
        response = PaymentResponse(
            success=True,
            transaction_id=transaction_id,
            status=status,
            message=f'Transaction status: {status} (mock)',
            raw_response={
                'mock_processor': True,
                'status_check_time': 'simulated'
            }
        )
        
        logger.info(f"Mock status check: {status}")
        
        return response
    
    def validate_credentials(self) -> bool:
        """
        Mock credential validation (always succeeds)
        
        Returns:
            True (mock processor doesn't require real credentials)
        """
        logger.info("Mock credential validation (always successful)")
        return True
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get mock processor capabilities
        
        Returns:
            Dictionary of supported features
        """
        return {
            'process_payment': True,
            'refund_payment': True,
            'void_payment': True,
            'get_transaction_status': True,
            'recurring_payments': True,  # Mock supports everything
            'tokenization': True,
            'fraud_detection': True
        }
    
    def set_success_rate(self, success_rate: float):
        """
        Change the success rate for testing
        
        Args:
            success_rate: Success rate (0.0 to 1.0)
        """
        if 0.0 <= success_rate <= 1.0:
            self.success_rate = success_rate
            logger.info(f"Mock processor success rate changed to {success_rate * 100}%")
        else:
            logger.error(f"Invalid success rate: {success_rate}")
