from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.contrib import messages
from .models import Ambiente, Area


def pagina_inicial(request):
    return render(request, "tickets/bem_vindo.html")

@login_required(login_url="/login/")
def criar_ticket(request):
    ambientes_do_cliente = Ambiente.objects.filter(cliente=request.user)
    area_do_cliente = Area.objects.filter(cliente=request.user)

    username_lower = request.user.username.lower()
    mostrar_area = "pampa" in username_lower or "abl" in username_lower
    mostrar_area_pampa = "pampa" in username_lower
    mostrar_area_abl = "abl" in username_lower
    
    if request.method == "POST":
        sumario = request.POST.get("sumario")
        descricao_problema = request.POST.get("descricao_problema")
        ambiente_selecionado = request.POST.get("ambiente")
        prioridade = request.POST.get("prioridade")
        area_selecionada = request.POST.get("area")
        anexo = request.FILES.get("anexo")

        if not sumario or not ambiente_selecionado or not prioridade or not descricao_problema:
            messages.error(request, "Por favor, preencha todos os campos obrigatórios.")
            return redirect("criar_ticket") # Redireciona para a mesma página
        
        try:
            ambiente_objeto = Ambiente.objects.get(cliente=request.user, nome_ambiente=ambiente_selecionado)
            asset_num = ambiente_objeto.numero_ativo
            
        except Ambiente.DoesNotExist:
            messages.error(request, "Ambiente selecionado é inválido. Tente novamente.")
            return redirect("criar_ticket")
        
        location = request.user.location
        person_id = request.user.person_id

        corpo_email = f"""

Descrição do problema: {descricao_problema}<br><br> 
        
#MAXIMO_EMAIL_BEGIN<br>
SR#DESCRIPTION={sumario}<br>
;<br>
SR#ASSETNUM={asset_num}<br>
;<br>
SR#REPORTEDPRIORITY={prioridade}<br>
;<br> """
        if area_do_cliente:
             corpo_email += f"""

SR#ITC_AREA={area_selecionada}<br>
;<br> """
             
        corpo_email += f"""
SR#LOCATION={location}<br>
;<br> """
        
        if person_id:
             corpo_email += f"""
SR#AFFECTEDPERSONID={person_id}<br>
;<br> """
             
        corpo_email += f"""
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
            
        try:
            email_do_cliente = request.user.email
            
            # Use EmailMessage para enviar o e-mail com anexo
            email = EmailMessage(
                subject=sumario,
                body=corpo_email,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=["suportebr@itconsol.com"],
                reply_to=[email_do_cliente],
            )
            
            # Verifica se um anexo foi enviado e o adiciona
            if anexo:
                email.attach(anexo.name, anexo.read(), anexo.content_type)
            
            email.send() # Envia o e-mail

            messages.success(request, "Ticket enviado com sucesso!")
            return redirect("criar_ticket")
        except Exception as e:
            messages.error(request, f"Erro ao enviar o ticket: {e}")
            return redirect("criar_ticket")

    context = {
        "ambientes": ambientes_do_cliente,
        "areas": area_do_cliente,
        "mostrar_area": mostrar_area,
        "mostrar_area_pampa": mostrar_area_pampa,
        "mostrar_area_abl": mostrar_area_abl
    }
    return render(request, "tickets/criar_ticket.html", context)