# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Payment Processor Factory
Creates payment processor instances based on configuration
"""
from typing import Dict, Any, Optional
import logging
from .base_processor import BasePaymentProcessor
from .mock_processor import MockPaymentProcessor
from .merchantone_processor import MerchantOneProcessor
from .paysafe_processor import PaySafeProcessor
from .paymentnerds_processor import PaymentNerdsProcessor

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class ProcessorFactory:
    """Factory for creating payment processor instances"""
    
    # Registry of available processors
    _processors = {
        'mock': MockPaymentProcessor,
        'merchantone': MerchantOneProcessor,
        'paysafe': PaySafeProcessor,
        'paymentnerds': PaymentNerdsProcessor
    }
    
    @classmethod
    def create_processor(
        cls,
        processor_type: str,
        config: Dict[str, Any]
    ) -> BasePaymentProcessor:
        """
        Create a payment processor instance
        
        Args:
            processor_type: Type of processor (mock, merchantone, paysafe, paymentnerds)
            config: Processor configuration dictionary
        
        Returns:
            Instance of the requested payment processor
        
        Raises:
            ValueError: If processor type is not supported
        """
        processor_type_lower = processor_type.lower()
        
        if processor_type_lower not in cls._processors:
            available = ', '.join(cls._processors.keys())
            raise ValueError(
                f"Unknown processor type: {processor_type}. "
                f"Available processors: {available}"
            )
        
        processor_class = cls._processors[processor_type_lower]
        
        try:
            processor = processor_class(config)
            logger.info(f"Created processor: {processor_type}")
            return processor
        except Exception as e:
            logger.error(f"Failed to create processor {processor_type}: {str(e)}")
            raise
    
    @classmethod
    def get_available_processors(cls) -> list:
        """
        Get list of available processor types
        
        Returns:
            List of processor type names
        """
        return list(cls._processors.keys())
    
    @classmethod
    def register_processor(
        cls,
        processor_type: str,
        processor_class: type
    ):
        """
        Register a new processor type
        
        Args:
            processor_type: Name/identifier for the processor
            processor_class: Processor class (must inherit from BasePaymentProcessor)
        """
        if not issubclass(processor_class, BasePaymentProcessor):
            raise ValueError(
                f"Processor class must inherit from BasePaymentProcessor"
            )
        
        cls._processors[processor_type.lower()] = processor_class
        logger.info(f"Registered new processor type: {processor_type}")
    
    @classmethod
    def create_from_config_record(
        cls,
        config_record: Dict[str, Any]
    ) -> BasePaymentProcessor:
        """
        Create processor from a processor configuration record
        (typically from DynamoDB)
        
        Args:
            config_record: Configuration record from database
        
        Returns:
            Configured processor instance
        """
        processor_type = config_record.get('processor_type')
        if not processor_type:
            raise ValueError("processor_type is required in configuration")
        
        # Extract configuration details
        config = {
            'processor_name': config_record.get('processor_name'),
            'processor_type': processor_type,
            'is_test_mode': config_record.get('is_test_mode', True),
            'api_key': config_record.get('api_key'),
            'api_secret': config_record.get('api_secret'),
            'merchant_id': config_record.get('merchant_id'),
            'endpoint_url': config_record.get('endpoint_url'),
            'additional_config': config_record.get('additional_config', {})
        }
        
        return cls.create_processor(processor_type, config)
    
    @classmethod
    def validate_config(
        cls,
        processor_type: str,
        config: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate processor configuration
        
        Args:
            processor_type: Type of processor
            config: Configuration to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        processor_type_lower = processor_type.lower()
        
        if processor_type_lower not in cls._processors:
            return False, f"Unknown processor type: {processor_type}"
        
        # Common required fields
        required_fields = ['processor_name', 'processor_type']
        
        # Processor-specific required fields
        processor_requirements = {
            'merchantone': ['api_key', 'merchant_id'],
            'paysafe': ['api_key', 'api_secret'],
            'paymentnerds': ['api_key', 'merchant_id'],
            'mock': []  # Mock processor doesn't require credentials
        }
        
        required_fields.extend(
            processor_requirements.get(processor_type_lower, [])
        )
        
        missing_fields = [
            field for field in required_fields
            if not config.get(field)
        ]
        
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
        
        return True, None


def get_active_processor(
    dynamodb_table,
    company_name: str
) -> Optional[BasePaymentProcessor]:
    """
    Get the active payment processor for a company
    
    Args:
        dynamodb_table: DynamoDB table resource
        company_name: Company identifier
    
    Returns:
        Active processor instance or None if no active processor
    """
    try:
        # Query for active processor
        response = dynamodb_table.query(
            IndexName='CompanyActiveIndex',
            KeyConditionExpression='company_name = :company AND is_active = :active',
            ExpressionAttributeValues={
                ':company': company_name,
                ':active': True
            },
            Limit=1
        )
        
        items = response.get('Items', [])
        if not items:
            logger.warning(f"No active processor found for company: {company_name}")
            return None
        
        config_record = items[0]
        processor = ProcessorFactory.create_from_config_record(config_record)
        
        return processor
        
    except Exception as e:
        logger.error(f"Error getting active processor: {str(e)}")
        return None
