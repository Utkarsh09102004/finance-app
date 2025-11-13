from django.apps import AppConfig


class FinsyncbillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'FinSyncBilling'
    
    def ready(self):
        import FinSyncBilling.signals