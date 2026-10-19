"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()

# Ensure all database migrations (such as stock field and product specs sync) are applied on Render startup
try:
    from django.core.management import call_command
    call_command('migrate', interactive=False)
except Exception as exc:
    import sys
    print(f"WSGI auto-migrate warning: {exc}", file=sys.stderr)

