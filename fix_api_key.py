#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import base64
import secrets

# Generate a secure API key
new_key = secrets.token_urlsafe(32)

print("Current environment variables:")
api_key = os.environ.get("INTERNAL_API_KEY")
print("INTERNAL_API_KEY: {}".format(api_key))

print("\nGenerated new API key: {}".format(new_key))
print("\nPlease add the following line to your .env file and ensure all services use it:")
print("INTERNAL_API_KEY={}".format(new_key))
print("\nAlso make sure to set this environment variable for both backend and Celery workers") 