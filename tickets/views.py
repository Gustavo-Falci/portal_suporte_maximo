from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpRequest, FileResponse, Http404
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from .models import Ticket, Ambiente, Area, TicketInteracao, Cliente
from .forms import TicketForm, TicketInteracaoForm
from django.db.models import Q
import logging
import os

logger = logging.getLogger(__name__)

# --- PÁGINA INICIAL ---
def pagina_inicial(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return render(request, "tickets/bem_vindo.html")
    else:
        return redirect("login")

# --- SUCESSO ---
@login_required(login_url="/login/")
def ticket_sucesso(request: HttpRequest) -> HttpResponse:
    return render(request, "tickets/sucesso.html")

# --- LISTAGEM DE TICKETS ---
@login_required(login_url="/login/")
def meus_tickets(request: HttpRequest) -> HttpResponse:
    """
    Exibe a lista de tickets abertos pelo usuário logado.
    """
    tickets = Ticket.objects.filter(cliente=request.user)
    return render(request, "tickets/meus_tickets.html", {"tickets": tickets})

# --- CRIAR TICKET ---
@login_required(login_url="/login/")
def criar_ticket(request: HttpRequest) -> HttpResponse:
    
    # Type hinting para garantir que estamos lidando com o modelo Cliente customizado
    cliente: Cliente = request.user
    
    # Normaliza a location para evitar erros de case (maiúscula/minúscula)
    location_str = str(cliente.location).upper() if cliente.location else ""
    
    # NOVA LÓGICA: Verifica se 'PAMPA' ou 'ABL' está contido no location
    mostrar_area = "PAMPA" in location_str or "ABL" in location_str

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

# --- DETALHE DO TICKET ---
@login_required(login_url="/login/")
def detalhe_ticket(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Exibe detalhes do ticket, processa o chat interno e controla a navegação de "Voltar".
    """
    # 1. Busca Ticket
    ticket = get_object_or_404(Ticket, pk=pk)
    
    # 2. Captura a origem da URL (ex: ?origin=fila)
    # Isso é essencial para o botão "Voltar" saber para onde ir
    origem = request.GET.get('origin')

    tem_permissao = False
    
    # Se for staff/consultor OU dono do ticket
    if request.user.is_support_team or ticket.cliente == request.user:
        tem_permissao = True

    if not tem_permissao:
        messages.error(request, "Você não tem permissão para visualizar este ticket.")
        return redirect("meus_tickets")

    # 4. Chat (POST)
    if request.method == "POST":
        form = TicketInteracaoForm(request.POST, request.FILES)
        if form.is_valid():
            interacao = form.save(commit=False)
            interacao.ticket = ticket
            interacao.autor = request.user
            interacao.save()

            # Notificação por E-mail 
            try:
                _enviar_notificacao_chat(ticket, interacao, request.user)
            except Exception as e:
                # Loga o erro mas não trava a tela do usuário
                logger.error(f"Erro ao enviar notificação de chat no ticket {ticket.maximo_id}: {e}")
            
            # Atualiza data de modificação do ticket (importante para ordenação)
            ticket.save() 
            
            # 5. Redirecionamento Inteligente (Mantém o ?origin=fila após o POST)
            # Sem isso, ao enviar uma mensagem, o botão voltar quebraria
            url_destino = reverse('detalhe_ticket', args=[pk])
            if origem:
                return redirect(f"{url_destino}?origin={origem}")
            return redirect(url_destino)
            
        else:
            messages.error(request, "Erro ao enviar mensagem. Verifique os campos.")
    else:
        form = TicketInteracaoForm()

    # 6. Busca as mensagens
    interacoes = ticket.interacoes.select_related('autor').all()

    # 7. Contexto
    context = {
        "ticket": ticket,
        "interacoes": interacoes,
        "form": form,
        "origem": origem 
    }
    return render(request, "tickets/detalhe_ticket.html", context)

@login_required(login_url="/login/")
def fila_atendimento(request: HttpRequest) -> HttpResponse:
    """
    Exibe TODOS os tickets com filtros avançados para a equipe de suporte.
    """
    # 1. Segurança
    if not request.user.is_support_team:
        messages.warning(request, "Acesso restrito à equipe de suporte.")
        return redirect("meus_tickets")

    # 2. Base da Query
    tickets = Ticket.objects.all().select_related('cliente', 'ambiente').order_by('-data_criacao')

    # 3. Captura dos Filtros via GET
    status_filter = request.GET.get('status')
    location_filter = request.GET.get('location')
    search_query = request.GET.get('q')

    # 4. Aplicação dos Filtros
    if status_filter:
        tickets = tickets.filter(status_maximo=status_filter)
    
    if location_filter:
        # Filtra tickets onde o 'location' do cliente é igual ao selecionado
        tickets = tickets.filter(cliente__location=location_filter)

    if search_query:
        # Busca por ID, Título, Descrição ou Nome do Cliente
        tickets = tickets.filter(
            Q(maximo_id__icontains=search_query) |
            Q(sumario__icontains=search_query) |
            Q(descricao__icontains=search_query) |
            Q(cliente__username__icontains=search_query) |
            Q(cliente__first_name__icontains=search_query) |
            Q(cliente__location__icontains=search_query)
        )

    # 5. Dados para popular os Dropdowns do Filtro
    # Pega apenas clientes que não são staff/suporte para limpar a lista
    lista_locations = Cliente.objects.values_list('location', flat=True)\
                                     .exclude(location__isnull=True)\
                                     .exclude(location__exact='')\
                                     .distinct()\
                                     .order_by('location')
    
    status_choices = Ticket.MAXIMO_STATUS_CHOICES

    # 6. Estatísticas Rápidas (Opcional, mas fica pro)
    stats = {
        'total': tickets.count(),
        'criticos': tickets.filter(prioridade=1).count(),
        'novos': tickets.filter(status_maximo='NEW').count()
    }

    context = {
        "tickets": tickets,
        "lista_locations": lista_locations,
        "status_choices": status_choices,
        "filtros_atuais": request.GET, # Para manter o form preenchido
        "stats": stats
    }
    return render(request, "tickets/fila_atendimento.html", context)

@login_required(login_url="/login/")
def download_anexo_interacao(request: HttpRequest, interacao_id: int) -> HttpResponse:
    """
    Serve o anexo de forma segura e trata erros caso o arquivo não exista.
    """
    # 1. Busca a interação ou retorna 404 se o ID não existir no banco
    interacao = get_object_or_404(TicketInteracao, pk=interacao_id)
    ticket = interacao.ticket

    # 2. Segurança: Verifica se o usuário é o dono do ticket OU da equipe de suporte
    # (Reaproveitando a lógica is_support_team do seu Model Cliente)
    if ticket.cliente != request.user and not request.user.is_support_team:
        messages.error(request, "Você não tem permissão para acessar este arquivo.")
        return redirect("detalhe_ticket", pk=ticket.id)

    # 3. Verifica se o campo anexo está preenchido
    if not interacao.anexo:
        messages.warning(request, "Esta interação não possui anexo.")
        return redirect("detalhe_ticket", pk=ticket.id)

    try:
        # 4. Tenta abrir o arquivo
        # O .path pode falhar dependendo do Storage (S3 vs Local), 
        # mas .open() é o método agnóstico do Django.
        arquivo = interacao.anexo.open()
        
        # Opcional: Definir o nome do arquivo no download
        filename = os.path.basename(interacao.anexo.name)
        
        # Retorna o arquivo como download (as_attachment=True) 
        # ou visualização no navegador (as_attachment=False)
        return FileResponse(arquivo, as_attachment=True, filename=filename)

    except FileNotFoundError:
        # 5. Tratamento de Erro: Arquivo consta no banco, mas não no disco
        messages.error(request, "Arquivo indisponivel, contate o suporte.")
        return redirect("detalhe_ticket", pk=ticket.id)
        
    except Exception as e:
        # 6. Erro genérico (ex: permissão de leitura no disco, erro de IO)
        messages.error(request, f"Erro ao tentar abrir o anexo: {str(e)}")
        return redirect("detalhe_ticket", pk=ticket.id)
    
def _enviar_notificacao_chat(ticket: Ticket, interacao: TicketInteracao, autor) -> None:
    """
    Envia e-mails de notificação de novas mensagens no chat.
    
    Lógica:
    - Se o Autor for do Time de Suporte -> Envia e-mail para o CLIENTE.
    - Se o Autor for o Cliente -> Envia e-mail para o SUPORTE.
    """
    
    # Configuração de E-mail de Suporte (Fallback seguro caso não esteja no settings)
    email_suporte_destino = getattr(settings, 'SUPPORT_EMAIL_ADDRESS', 'suportebr@itconsol.com')
    remetente = settings.DEFAULT_FROM_EMAIL
    
    assunto = ""
    corpo_email = ""
    destinatarios = []

    # Verifica se quem escreveu faz parte do time de suporte
    is_support_msg = autor.is_support_team

    if is_support_msg:
        # CENÁRIO 1: Suporte respondeu -> Avisar Cliente
        assunto = f"[Portal Suporte] Nova resposta no Ticket #{ticket.maximo_id} - {ticket.sumario}"
        destinatarios = [ticket.cliente.email]
        
        corpo_email = f"""
        Olá, {ticket.cliente.first_name or ticket.cliente.username}.<br><br>
        
        A equipe de suporte adicionou uma nova mensagem ao seu ticket <strong>#{ticket.maximo_id}</strong>.<br><br>
        
        <strong>Mensagem:</strong><br>
        <div style="background-color: #f4f4f4; padding: 10px; border-left: 4px solid #0f62fe;">
            {interacao.mensagem}
        </div><br><br>
        
        Acesse o portal para responder ou ver anexos.
        """
        
    else:
        # CENÁRIO 2: Cliente respondeu -> Avisar Suporte
        assunto = f"[Alerta] Cliente respondeu o Ticket #{ticket.maximo_id} - {ticket.sumario}"
        destinatarios = [email_suporte_destino]
        
        location_info = getattr(ticket.cliente, 'location', 'N/A')
        
        corpo_email = f"""
        Equipe,<br><br>
        
        O cliente <strong>{ticket.cliente.username}</strong> (Local: {location_info}) enviou uma nova mensagem.<br><br>
        
        <strong>Ticket:</strong> #{ticket.maximo_id}<br>
        <strong>Sumário:</strong> {ticket.sumario}<br><br>
        
        <strong>Mensagem:</strong><br>
        <div style="background-color: #f4f4f4; padding: 10px; border-left: 4px solid #198038;">
            {interacao.mensagem}
        </div>
        """

    # Envio efetivo
    if destinatarios:
        email = EmailMessage(
            subject=assunto,
            body=corpo_email,
            from_email=remetente,
            to=destinatarios
        )
        email.content_subtype = "html" # Permite usar HTML no corpo
        email.send()