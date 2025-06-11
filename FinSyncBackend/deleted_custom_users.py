# delete_all_users.py
import os
import django
import sys

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FinSyncBackend.settings')
django.setup()

from FinSyncAuth.models import CustomUser

# Get all users
all_users = CustomUser.objects.all()

# Print count before deletion
count = all_users.count()
print(f"Found {count} users to delete")

# Print users that will be deleted
for user in all_users:
    try:
        org_name = user.organization.name
    except Exception:
        org_name = "NO ORGANIZATION"
    print(f"Will delete: {user.email} (Organization: {org_name})")

