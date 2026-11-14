from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class IsManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'manager'

class IsMechanic(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'mechanic'

class IsClient(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'client'

class IsAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('admin', 'manager')

class IsOrderParticipant(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        return user.is_authenticated and (user.role in ('admin', 'manager') or user.role == 'client' and obj.client_id == user.pk or user.role == 'mechanic' and obj.mechanic_id == user.pk)
