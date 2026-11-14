from contextvars import ContextVar
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import AuditEvent

current_request = ContextVar('audit_request', default=None)

class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        token = current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            current_request.reset(token)

def record(sender, instance, action):
    if sender._meta.app_label != 'core' or sender == AuditEvent:
        return
    request = current_request.get()
    actor = getattr(request, 'user', None)
    if not actor or not actor.is_authenticated:
        actor = None
    # Never store passwords, tokens or full request payloads.
    detail = f'{sender._meta.verbose_name} #{instance.pk}'
    if hasattr(instance, 'status'):
        detail += f' · {instance.status}'
    AuditEvent.objects.create(actor=actor, action=action, entity=sender.__name__, entity_id=instance.pk, detail=detail)

@receiver(post_save)
def saved(sender, instance, created, raw=False, **kwargs):
    if not raw:
        record(sender, instance, 'created' if created else 'updated')

@receiver(post_delete)
def deleted(sender, instance, **kwargs):
    record(sender, instance, 'deleted')
