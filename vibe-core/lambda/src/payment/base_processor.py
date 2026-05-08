# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Base Payment Processor Abstract Class
Defines the interface that all payment processors must implement
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PaymentResponse:
    """Standardized payment response object"""
    
    def __init__(
        self,
        success: bool,
        transaction_id: Optional[str] = None,
        amount: Optional[float] = None,
        currency: str = 'USD',
        status: Optional[str] = None,
        message: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_details: Optional[str] = None
    ):
        self.success = success
        self.transaction_id = transaction_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.message = message
        self.raw_response = raw_response or {}
        self.error_code = error_code
        self.error_details = error_details
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'success': self.success,
            'transaction_id': self.transaction_id,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'message': self.message,
            'error_code': self.error_code,
            'error_details': self.error_details,
            'timestamp': self.timestamp,
            'raw_response': self.raw_response
        }


class BasePaymentProcessor(ABC):
    """
    Abstract base class for all payment processors
    All payment processors must inherit from this class and implement required methods
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize payment processor with configuration
        
        Args:
            config: Dictionary containing processor configuration
                   (API keys, endpoints, etc.)
        """
        self.config = config
        self.processor_name = config.get('processor_name', 'Unknown')
        self.processor_type = config.get('processor_type', 'Unknown')
        self.is_test_mode = config.get('is_test_mode', True)
        
        logger.info(f"Initializing {self.processor_name} processor (test_mode={self.is_test_mode})")
    
    @abstractmethod
    def process_payment(
        self,
        amount: float,
        currency: str,
        payment_method: Dict[str, Any],
        customer_info: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentResponse:
        """
        Process a payment transaction
        
        Args:
            amount: Payment amount
            currency: Currency code (USD, EUR, etc.)
            payment_method: Payment method details (card, bank account, etc.)
            customer_info: Optional customer information
            metadata: Optional additional metadata
        
        Returns:
            PaymentResponse object with transaction details
        """
        pass
    
    @abstractmethod
    def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Refund a payment transaction
        
        Args:
            transaction_id: Original transaction ID
            amount: Refund amount (None for full refund)
            reason: Reason for refund
        
        Returns:
            PaymentResponse object with refund details
        """
        pass
    
    @abstractmethod
    def void_payment(
        self,
        transaction_id: str,
        reason: Optional[str] = None
    ) -> PaymentResponse:
        """
        Void/cancel a payment transaction
        
        Args:
            transaction_id: Transaction ID to void
            reason: Reason for voiding
        
        Returns:
            PaymentResponse object with void details
        """
        pass
    
    @abstractmethod
    def get_transaction_status(
        self,
        transaction_id: str
    ) -> PaymentResponse:
        """
        Get the status of a transaction
        
        Args:
            transaction_id: Transaction ID to check
        
        Returns:
            PaymentResponse object with current transaction status
        """
        pass
    
    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Validate processor credentials/configuration
        
        Returns:
            True if credentials are valid, False otherwise
        """
        pass
    
    def get_processor_info(self) -> Dict[str, Any]:
        """
        Get information about this processor
        
        Returns:
            Dictionary with processor information
        """
        return {
            'processor_name': self.processor_name,
            'processor_type': self.processor_type,
            'is_test_mode': self.is_test_mode,
            'capabilities': self.get_capabilities()
        }
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get processor capabilities
        
        Returns:
            Dictionary of supported features
        """
        return {
            'process_payment': True,
            'refund_payment': True,
            'void_payment': True,
            'get_transaction_status': True,
            'recurring_payments': False,
            'tokenization': False,
            'fraud_detection': False
        }
    
    def validate_amount(self, amount: float, currency: str = 'USD') -> bool:
        """
        Validate payment amount
        
        Args:
            amount: Amount to validate
            currency: Currency code
        
        Returns:
            True if valid, False otherwise
        """
        if amount <= 0:
            logger.error(f"Invalid amount: {amount}")
            return False
        
        # Maximum transaction limits
        max_amounts = {
            'USD': 999999.99,
            'EUR': 999999.99,
            'GBP': 999999.99
        }
        
        max_amount = max_amounts.get(currency, 999999.99)
        if amount > max_amount:
            logger.error(f"Amount {amount} exceeds maximum {max_amount} for {currency}")
            return False
        
        return True
    
    def validate_currency(self, currency: str) -> bool:
        """
        Validate currency code
        
        Args:
            currency: Currency code to validate
        
        Returns:
            True if valid, False otherwise
        """
        supported_currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD']
        
        if currency not in supported_currencies:
            logger.error(f"Unsupported currency: {currency}")
            return False
        
        return True
    
    def log_transaction(
        self,
        transaction_type: str,
        transaction_data: Dict[str, Any],
        response: PaymentResponse
    ):
        """
        Log transaction for audit trail
        
        Args:
            transaction_type: Type of transaction (payment, refund, void)
            transaction_data: Transaction request data
            response: Payment response
        """
        log_data = {
            'processor': self.processor_name,
            'transaction_type': transaction_type,
            'success': response.success,
            'transaction_id': response.transaction_id,
            'amount': response.amount,
            'currency': response.currency,
            'timestamp': response.timestamp
        }
        
        if response.success:
            logger.info(f"Transaction successful: {log_data}")
        else:
            logger.error(f"Transaction failed: {log_data} - {response.error_details}")
    
    def create_error_response(
        self,
        error_message: str,
        error_code: Optional[str] = None
    ) -> PaymentResponse:
        """
        Create a standardized error response
        
        Args:
            error_message: Error message
            error_code: Optional error code
        
        Returns:
            PaymentResponse object with error details
        """
        return PaymentResponse(
            success=False,
            status='error',
            message=error_message,
            error_code=error_code or 'PROCESSING_ERROR',
            error_details=error_message
        )
