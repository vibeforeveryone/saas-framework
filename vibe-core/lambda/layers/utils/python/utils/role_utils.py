# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
role_utils.py
Shared utilities for default role assignment.

Used by:
  - create_customer.py
  - complete_public_signup.py

Keeps the Role table lookup and UserRole write logic in one place so
both entry points stay consistent with each other.
"""
import boto3
import logging
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()

dynamodb        = boto3.resource('dynamodb')
role_table      = dynamodb.Table('Role')
user_role_table = dynamodb.Table('UserRole')

# Names of the two default roles that every first user receives.
DEFAULT_ROLE_NAMES = ('Admin', 'Invoicing')


def get_default_role_keys() -> dict:
    """
    Look up Admin and Invoicing roles by role_desc via the role_desc-index GSI.

    Returns a dict of { role_name: role_key } for each role found.
    Missing roles are omitted and a warning is logged — the caller
    should handle an empty or partial result gracefully.

    Example return value:
      { 'Admin': 'uuid-1', 'Invoicing': 'uuid-2' }
    """
    result = {}
    for role_name in DEFAULT_ROLE_NAMES:
        try:
            response = role_table.query(
                IndexName='role_desc-index',
                KeyConditionExpression=Key('role_desc').eq(role_name)
            )
            items = response.get('Items', [])
            if items:
                result[role_name] = items[0]['role_key']
                logger.info(f"Found role '{role_name}': {items[0]['role_key']}")
            else:
                logger.warning(
                    f"Default role '{role_name}' not found in Role table. "
                    "Ensure seed_roles has been run."
                )
        except Exception as e:
            logger.error(f"Error looking up role '{role_name}': {str(e)}")
    return result


def assign_default_roles(user_key: str, customer_id: str,
                         role_keys: dict, timestamp: str,
                         assigned_by: str) -> list:
    """
    Write one UserRole record per role in role_keys.

    Parameters:
      user_key     — the user receiving the roles
      customer_id  — the customer the user belongs to
      role_keys    — dict of { role_name: role_key } from get_default_role_keys()
      timestamp    — ISO timestamp string (use the same one as the user record)
      assigned_by  — user_key or process name to record in assigned_by field

    Returns:
      List of role names that were successfully written, e.g. ['Admin', 'Invoicing'].
      Partial success is possible — each role write is individually try/caught.
      An empty list means all writes failed (check CloudWatch logs).

    This function is intentionally non-fatal. A failure here must never
    prevent the customer or user from being created.
    """
    assigned = []
    for role_name, role_key in role_keys.items():
        try:
            user_role_table.put_item(Item={
                'user_key':    user_key,
                'role_key':    role_key,
                'customer_id': customer_id,
                'assigned_at': timestamp,
                'assigned_by': assigned_by,
            })
            assigned.append(role_name)
            logger.info(
                f"Assigned role '{role_name}' ({role_key}) "
                f"to user {user_key} (customer {customer_id})"
            )
        except Exception as e:
            logger.error(
                f"Error assigning role '{role_name}' to user {user_key}: {str(e)}"
            )
    return assigned


def assign_all_default_roles(user_key: str, customer_id: str,
                             timestamp: str, assigned_by: str) -> list:
    """
    Convenience wrapper: looks up default roles then assigns them in one call.

    Returns the list of role names successfully assigned.
    Logs a warning if the Role table is not yet seeded.
    """
    role_keys = get_default_role_keys()

    if not role_keys:
        logger.warning(
            f"No default roles found for assignment to user {user_key}. "
            "Run seed_roles, then assign roles manually via UserManager."
        )
        return []

    assigned = assign_default_roles(
        user_key=user_key,
        customer_id=customer_id,
        role_keys=role_keys,
        timestamp=timestamp,
        assigned_by=assigned_by,
    )

    if len(assigned) < len(DEFAULT_ROLE_NAMES):
        missing = set(DEFAULT_ROLE_NAMES) - set(assigned)
        logger.warning(
            f"Some default roles were not assigned to user {user_key}: {missing}. "
            "Assign them manually via UserManager."
        )

    return assigned
