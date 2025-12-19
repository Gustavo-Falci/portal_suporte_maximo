from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Cliente, Ambiente, Area, Ticket

# 1. Customização do Cabeçalho e Título do Admin (Visual Corporativo)
admin.site.site_header = "Portal de Suporte | Administração"
admin.site.site_title = "IT Consol Admin"
admin.site.index_title = "Gestão de Usuários e Ativos"

# ATENÇÃO: Removi as linhas 'admin.site.register(...)' que estavam soltas aqui.
# Usaremos apenas os decoradores (@admin.register) abaixo para evitar o erro de duplicidade.

@admin.register(Cliente)
class ClienteAdmin(UserAdmin):
    """
    Configuração avançada para o modelo de Usuário Customizado.
    Permite editar 'person_id' e 'location' e melhora a busca.
    """
    # Colunas que aparecem na lista de usuários
    list_display = ('username', 'email', 'get_full_name', 'location', 'person_id', 'is_staff', 'is_active')
    
    # Filtros laterais (Barra direita)
    list_filter = ('is_staff', 'is_active', 'location', 'groups')
    
    # Barra de pesquisa: Busca por nome, email ou pelo ID do Maximo
    search_fields = ('username', 'first_name', 'last_name', 'email', 'person_id')
    
    # Organização do Formulário de Edição
    # Adicionamos uma seção nova "Integração Maximo" com os campos extras
    fieldsets = UserAdmin.fieldsets + (
        ('Integração Maximo', {
            'fields': ('location', 'person_id'),
            'description': 'Dados críticos para o roteamento correto do ticket no IBM Maximo.'
        }),
    )

@admin.register(Ambiente)
class AmbienteAdmin(admin.ModelAdmin):
    """
    Gestão dos Ambientes/Ativos vinculados a cada cliente.
    """
    list_display = ('nome_ambiente', 'numero_ativo', 'get_cliente_info')
    search_fields = ('nome_ambiente', 'numero_ativo', 'cliente__username', 'cliente__email', 'cliente__person_id')
    list_filter = ('cliente__location',) # Filtra por localidade do cliente
    
    # Habilita um campo de busca com autocompletar para selecionar o Cliente
    # (Muito útil quando você tiver centenas de usuários)
    autocomplete_fields = ['cliente']

    # Mostra o email do cliente na listagem para facilitar identificação
    @admin.display(description='Cliente Proprietário', ordering='cliente__email')
    def get_cliente_info(self, obj):
        return f"{obj.cliente.get_full_name()} ({obj.cliente.email})"

@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    """
    Gestão das Áreas (ex: PAMPA, ABL) para lógica condicional.
    """
    list_display = ('nome_area', 'get_cliente_email')
    search_fields = ('nome_area', 'cliente__username', 'cliente__email')
    autocomplete_fields = ['cliente']
    
    @admin.display(description='Cliente', ordering='cliente__email')
    def get_cliente_email(self, obj):
        return obj.cliente.email
    
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """
    Gestão dos Tickets (Visualização e Auditoria)
    """
    # Adicionei 'prioridade' na visualização da lista
    list_display = ('id', 'sumario', 'cliente', 'prioridade', 'status_maximo', 'maximo_id', 'data_criacao')
    
    # Filtros úteis para relatórios rápidos
    list_filter = ('status_maximo', 'prioridade', 'data_criacao', 'area')
    
    # Busca expandida para encontrar tickets facilmente
    search_fields = ('sumario', 'descricao', 'cliente__username', 'cliente__email', 'maximo_id')
    
    # Datas não devem ser editadas manualmente
    readonly_fields = ('data_criacao', 'data_atualizacao')
    
    # Ordena do mais recente para o mais antigo
    ordering = ('-data_criacao',)