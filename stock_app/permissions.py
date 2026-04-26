from rest_framework import permissions

class IsResponsableMagasin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Responsable_magasin'

class IsMagasinier(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'magasinier'

class IsResponsableAudit(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Responsable_Audit'

class IsAdminOrResponsableMagasin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['Responsable_magasin', 'admin']