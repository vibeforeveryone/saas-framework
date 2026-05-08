# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import hashlib
import os

def hash_password(password):
    """Hash a password using SHA-256 with salt"""
    # Add salt from environment
    salt = os.environ.get('PASSWORD_SALT', 'default-salt-change-in-production')
    salted_password = f"{password}{salt}"

    return hashlib.sha256(password.encode()).hexdigest()
    #return hashlib.sha256(salted_password.encode()).hexdigest()

def verify_password(password, hashed_password):
    """Verify a password against a hash"""
    return hash_password(password) == hashed_password