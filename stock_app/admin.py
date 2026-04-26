from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur

class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'role', 'telephone', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'telephone')}),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'telephone')}),
    )

admin.site.register(Utilisateur, CustomUserAdmin)