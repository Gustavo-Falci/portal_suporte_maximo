from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views, forms

urlpatterns = [

    # A URL raiz agora aponta para a página de boas-vindas
    path("", views.pagina_inicial, name="pagina_inicial"),

    # URL para a página de login (usando seu form customizado)
    path("login/", LoginView.as_view(
        template_name="tickets/login.html", 
        authentication_form=forms.EmailAuthenticationForm
    ), name="login"),

    # URL para a página de logout
    path("logout/", LogoutView.as_view(), name="logout"),

    # URL para a página de criação de ticket
    path("criar/", views.criar_ticket, name="criar_ticket"),

    # Página de Sucesso (Onde o usuário cai após enviar o ticket)
    path("sucesso/", views.ticket_sucesso, name="ticket_sucesso"),

    path("meus-tickets/", views.meus_tickets, name="meus_tickets"),
    path("ticket/<int:pk>/", views.detalhe_ticket, name="detalhe_ticket"),

    path("fila-atendimento/", views.fila_atendimento, name="fila_atendimento"),

    path("interacao/anexo/<int:interacao_id>/", views.download_anexo_interacao, name="download_anexo"),
]