from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Cliente, Ambiente, Area

# Cria uma classe administrativa para o seu modelo Cliente
# que herda do UserAdmin para incluir todos os campos de usuário.
class ClienteAdmin(UserAdmin):
    # Sobrescreve os campos padrão do UserAdmin para incluir o campo 'location'.
    # Note que 'fieldsets' é usado na página de edição.
    fieldsets = UserAdmin.fieldsets + (
        (None, {"fields": ("location", "person_id")}),
    )

    # 'add_fieldsets' é usado na página de criação de novo usuário.
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {"fields": ("location", "person_id")}),
    )


# Cancela o registro do modelo Cliente padrão para registrar o seu
# com a nova classe administrativa.
admin.site.register(Cliente, ClienteAdmin)
admin.site.register(Ambiente)
admin.site.register(Area)