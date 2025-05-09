#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv
import secrets

# Load .env file
load_dotenv()

# Get current key
current_key = os.getenv("INTERNAL_API_KEY")
print("Current INTERNAL_API_KEY in environment: {}".format(current_key))

if not current_key:
    # Generate a new key
    new_key = secrets.token_urlsafe(32)
    print("Generated new key: {}".format(new_key))
    print("\nPlease add the following line to your .env file:")
    print("INTERNAL_API_KEY={}".format(new_key))
else:
    # Show first 4 characters for verification
    key_prefix = current_key[:4] + "***" if current_key else "Not set"
    print("Current key prefix: {}".format(key_prefix))
    print("\nCheck if backend and Celery workers are using the same environment file.")
    print("To reset the key, add or modify INTERNAL_API_KEY in your .env file") 