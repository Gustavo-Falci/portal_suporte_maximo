from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpRequest
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib import messages
from .models import Ticket, Ambiente, Area
from .forms import TicketForm
import logging

logger = logging.getLogger(__name__)

# --- PÁGINA INICIAL ---
def pagina_inicial(request):
    if request.user.is_authenticated:
        return redirect('meus_tickets')
    return render(request, "tickets/bem_vindo.html")

# --- SUCESSO ---
@login_required(login_url="/login/")
def ticket_sucesso(request: HttpRequest) -> HttpResponse:
    return render(request, "tickets/sucesso.html")

# --- LISTAGEM DE TICKETS (NOVO) ---
@login_required(login_url="/login/")
def meus_tickets(request: HttpRequest) -> HttpResponse:
    """
    Exibe a lista de tickets abertos pelo usuário logado.
    """
    tickets = Ticket.objects.filter(cliente=request.user)
    return render(request, "tickets/meus_tickets.html", {"tickets": tickets})

# --- DETALHE DO TICKET (NOVO) ---
@login_required(login_url="/login/")
def detalhe_ticket(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Exibe os detalhes de um ticket específico.
    """
    # Garante que o usuário só veja seus próprios tickets
    ticket = get_object_or_404(Ticket, pk=pk, cliente=request.user)
    return render(request, "tickets/detalhe_ticket.html", {"ticket": ticket})

# --- CRIAR TICKET (ATUALIZADO FASE 2) ---
@login_required(login_url="/login/")
def criar_ticket(request: HttpRequest) -> HttpResponse:
    
    # Lógica visual (quem pode ver o campo Area)
    username_lower = request.user.username.lower()
    mostrar_area = "pampa" in username_lower or "abl" in username_lower

    if request.method == "POST":
        form = TicketForm(request.POST, request.FILES, user=request.user)
        
        if form.is_valid():
            try:
                # 1. SALVAR NO BANCO DE DADOS (PostgreSQL)
                # commit=False cria o objeto na memória mas não salva ainda
                ticket = form.save(commit=False)
                ticket.cliente = request.user # Atribui o dono do ticket
                ticket.save() # Agora sim, salva e gera o ID (ticket.id)

                logger.info(f"Ticket #{ticket.id} salvo no banco por {request.user.email}")

                # 2. PREPARAR DADOS PARA O MAXIMO (Usando o objeto ticket salvo)
                descricao_problema = ticket.descricao
                sumario = ticket.sumario
                prioridade = ticket.prioridade # Pegando do banco
                
                # Tratamento seguro de campos opcionais (Ambiente e Area são ForeignKeys)
                asset_num = ticket.ambiente.numero_ativo if ticket.ambiente else ""
                area_selecionada = ticket.area.nome_area if ticket.area else ""
                
                # Dados do Usuário
                location = getattr(request.user, 'location', '')
                person_id = getattr(request.user, 'person_id', '')

                # 3. MONTAGEM DO CORPO DO E-MAIL (REGRAS DE NEGÓCIO)
                corpo_email = f"""
Descrição do problema: {descricao_problema}<br><br>
#MAXIMO_EMAIL_BEGIN<br>
SR#DESCRIPTION={sumario}<br>
;<br>
SR#ASSETNUM={asset_num}<br>
;<br>
SR#REPORTEDPRIORITY={prioridade}<br>
;<br>"""

                if area_selecionada:
                    corpo_email += f"""SR#ITC_AREA={area_selecionada}<br>
;<br>"""

                corpo_email += f"""SR#LOCATION={location}<br>
;<br>"""

                if person_id:
                    corpo_email += f"""SR#AFFECTEDPERSONID={person_id}<br>
;<br>"""

                # Tags fixas do Maximo
                corpo_email += """SR#SITEID=ITCBR<br>
;<br>
LSNRACTION=CREATE<br>
;<br>
LSNRAPPLIESTO=SR<br>
;<br>
SR#CLASS=SR<br>
;<br>
SR#TICKETID=&AUTOKEY&<br>
;<br>
#MAXIMO_EMAIL_END<br><br>"""

                # 4. ENVIO DO E-MAIL
                email = EmailMessage(
                    subject=f"Novo Ticket - {sumario}", 
                    body=corpo_email,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[settings.EMAIL_DESTINATION],
                    reply_to=[request.user.email],
                )
                
                # Anexa o arquivo se existir (usando o campo do Model)
                if ticket.arquivo:
                    # ticket.arquivo.read() lê o arquivo do storage
                    email.attach(ticket.arquivo.name, ticket.arquivo.read(), "application/octet-stream")
                
                email.content_subtype = "html" # Importante para as tags <br> funcionarem
                email.send()

                logger.info(f"Ticket #{ticket.id} enviado por e-mail.")
                return redirect("ticket_sucesso")

            except Exception as e:
                logger.error(f"Erro no processo de ticket: {str(e)}")
                messages.error(request, "Ocorreu um erro ao processar sua solicitação. Tente novamente.")
                # Opcional: Se o e-mail falhar, você pode querer deletar o ticket do banco ou marcá-lo como 'erro_envio'
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = TicketForm(user=request.user)

    context = {
        "form": form,
        "ambientes": Ambiente.objects.filter(cliente=request.user), 
        "areas": Area.objects.filter(cliente=request.user),
        "mostrar_area": mostrar_area
    }
    return render(request, "tickets/criar_ticket.html", context)