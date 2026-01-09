from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Cliente, Ambiente, Area, Ticket, TicketInteracao

# Customização do Cabeçalho
admin.site.site_header = "Portal de Suporte | Administração"
admin.site.site_title = "IT Consol Admin"
admin.site.index_title = "Gestão de Usuários e Ativos"

#  INLINE: Chat dentro do Ticket 
class TicketInteracaoInline(admin.TabularInline):
    model = TicketInteracao
    extra = 0
    readonly_fields = ('data_criacao',)
    fields = ('autor', 'mensagem', 'anexo', 'data_criacao')
    can_delete = False 

@admin.register(Cliente)
class ClienteAdmin(UserAdmin):
    list_display = ('username', 'email', 'get_full_name', 'location', 'person_id', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'location', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'person_id')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Integração Maximo', {
            'fields': ('location', 'person_id'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Integração Maximo', {
            'fields': ('location', 'person_id'),
        }),
    )

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'sumario', 'cliente', 'prioridade', 'status_maximo', 'maximo_id', 'data_criacao')
    list_filter = ('status_maximo', 'prioridade', 'data_criacao', 'area')
    search_fields = ('sumario', 'descricao', 'cliente__username', 'cliente__email', 'maximo_id')
    
    readonly_fields = ('data_criacao', 'data_atualizacao')
    ordering = ('-data_criacao',)
    
    inlines = [TicketInteracaoInline]

    fieldsets = (
        ('Dados do Chamado', {
            'fields': ('sumario', 'descricao', 'cliente', 'status_maximo', 'prioridade')
        }),
        ('Classificação', {
            'fields': ('area', 'ambiente', 'arquivo')
        }),
        ('Integração Maximo', {
            'fields': ('maximo_id', 'data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Ambiente)
class AmbienteAdmin(admin.ModelAdmin):
    # Alterado de 'nome' para 'nome_ambiente'
    list_display = ('nome_ambiente', 'numero_ativo', 'cliente') 
    search_fields = ('nome_ambiente', 'numero_ativo', 'cliente__username')

@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    # Alterado de 'nome' para 'nome_area'
    list_display = ('nome_area', 'cliente') 
    search_fields = ('nome_area',)

@admin.register(TicketInteracao)
class TicketInteracaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'autor', 'data_criacao', 'tem_anexo')
    list_filter = ('data_criacao', 'autor__username')
    search_fields = ('mensagem', 'ticket__sumario')
    
    @admin.display(boolean=True, description='Anexo?')
    def tem_anexo(self, obj):
        return bool(obj.anexo)