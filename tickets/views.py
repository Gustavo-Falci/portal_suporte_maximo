from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpRequest
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.contrib import messages
from .models import Ambiente, Area
from .forms import TicketForm


def pagina_inicial(request):
    return render(request, "tickets/bem_vindo.html")

@login_required(login_url="/login/")
def criar_ticket(request: HttpRequest) -> HttpResponse:
    
    # Lógica de exibição da Área (Frontend)
    username_lower = request.user.username.lower()
    mostrar_area = "pampa" in username_lower or "abl" in username_lower

    if request.method == "POST":
        # Passamos o 'user' para o form filtrar os Ambientes corretos
        form = TicketForm(request.POST, request.FILES, user=request.user)
        
        if form.is_valid():
            # Dados limpos e validados (Seguro!)
            data = form.cleaned_data
            
            sumario = data['sumario']
            descricao_problema = data['descricao_problema']
            ambiente_objeto = data['ambiente']
            prioridade = data['prioridade']
            area_objeto = data['area']
            anexo = data['anexo']

            # Dados do Maximo
            asset_num = ambiente_objeto.numero_ativo
            location = request.user.location or ""
            person_id = request.user.person_id or ""
            area_nome = area_objeto.nome_area if area_objeto else ""

            # --- Montagem do Corpo do E-mail (Igual ao anterior) ---
            corpo_email = f"""
Descrição do problema: {descricao_problema}<br><br> 
#MAXIMO_EMAIL_BEGIN<br>
SR#DESCRIPTION={sumario}<br>
;<br>
SR#ASSETNUM={asset_num}<br>
;<br>
SR#REPORTEDPRIORITY={prioridade}<br>
;<br> """
            if area_nome:
                 corpo_email += f"SR#ITC_AREA={area_nome}<br>;<br> "
                 
            corpo_email += f"SR#LOCATION={location}<br>;<br> "
            
            if person_id:
                 corpo_email += f"SR#AFFECTEDPERSONID={person_id}<br>;<br> "
                 
            corpo_email += """
SR#SITEID=ITCBR<br>
;<br>
LSNRACTION=CREATE<br>
;<br>
LSNRAPPLIESTO=SR<br>
;<br>
SR#CLASS=SR<br>
;<br>
SR#TICKETID=&AUTOKEY&<br>
;<br>
#MAXIMO_EMAIL_END<br><br>
"""
            # --- Envio ---
            try:
                email = EmailMessage(
                    subject=sumario,
                    body=corpo_email,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=["suportebr@itconsol.com"],
                    reply_to=[request.user.email],
                )
                if anexo:
                    email.attach(anexo.name, anexo.read(), anexo.content_type)
                
                email.send()
                messages.success(request, "Ticket enviado com sucesso!")
                return redirect("criar_ticket")
                
            except Exception as e:
                messages.error(request, f"Erro técnico ao enviar: {e}")
        else:
            # Se o form for inválido (ex: arquivo grande demais), mostra erros
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = TicketForm(user=request.user)

    context = {
        "form": form, # Passamos o form para o template (opcional se quiser renderizar campos automáticos)
        "ambientes": Ambiente.objects.filter(cliente=request.user), # Mantemos para compatibilidade com seu HTML atual
        "areas": Area.objects.filter(cliente=request.user),
        "mostrar_area": mostrar_area,
    }
    return render(request, "tickets/criar_ticket.html", context)