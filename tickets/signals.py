from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.mail import EmailMessage
from django.conf import settings
from .models import Ticket, TicketInteracao, Notificacao, Cliente
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Ticket)
def notificar_mudanca_status(sender, instance: Ticket, **kwargs):
    """
    Verifica se o status do ticket mudou antes de salvar no banco.
    Se mudou, envia um e-mail para o cliente.
    """
    # Se não tem PK (ID), é um ticket novo sendo criado, então ignoramos
    # (pois a notificação de criação já é tratada na view)
    if not instance.pk:
        return

    try:
        # Busca a versão atual do ticket no banco de dados
        old_instance = Ticket.objects.get(pk=instance.pk)
    except Ticket.DoesNotExist:
        return # Segurança caso algo estranho aconteça

    # Compara o status antigo com o novo
    if old_instance.status_maximo != instance.status_maximo:
        logger.info(f"Status do Ticket #{instance.id} alterado: {old_instance.status_maximo} -> {instance.status_maximo}")
        try:
            _enviar_email_status(instance, old_instance.get_status_maximo_display())
        except Exception as e:
            logger.error(f"Erro ao enviar email de status para Ticket #{instance.id}: {e}")

def _enviar_email_status(ticket: Ticket, status_anterior_display: str) -> None:
    """
    Monta e envia o e-mail de notificação de status.
    """
    status_novo_display = ticket.get_status_maximo_display()
    
    assunto = f"[Atualização] O status do Ticket #{ticket.maximo_id} mudou para {status_novo_display}"
    remetente = settings.DEFAULT_FROM_EMAIL
    destinatarios = [ticket.cliente.email]

    corpo_email = f"""
    Olá, {ticket.cliente.first_name or ticket.cliente.username}.<br><br>
    
    O status do seu chamado foi atualizado.<br><br>
    
    <strong>Ticket:</strong> #{ticket.maximo_id}<br>
    <strong>Assunto:</strong> {ticket.sumario}<br>
    <br>
    
    <div style="border: 1px solid #ccc; padding: 15px; background-color: #f4f4f4;">
        <p><strong>Status Anterior:</strong> <span style="color: #666;">{status_anterior_display}</span></p>
        <p><strong>Novo Status:</strong> <span style="color: #0f62fe; font-weight: bold; font-size: 1.1em;">{status_novo_display}</span></p>
    </div>
    <br>
    
    Acesse o portal para ver mais detalhes.
    """

    email = EmailMessage(
        subject=assunto,
        body=corpo_email,
        from_email=remetente,
        to=destinatarios
    )
    email.content_subtype = "html"
    email.send()

@receiver(post_save, sender=TicketInteracao)
def criar_notificacao_interacao(sender, instance, created, **kwargs):
    """
    Gera notificação interna quando há nova interação.
    """
    if created:
        ticket = instance.ticket
        autor = instance.autor

        # Define o título e tipo baseados na ação
        titulo_notif = "Nova Resposta"
        tipo_notif = "mensagem"
        
        # Se quem escreveu foi o SUPORTE (ou Admin) -> Notificar o CLIENTE
        if autor.is_support_team:
            Notificacao.objects.create(
                destinatario=ticket.cliente,
                ticket=ticket,
                titulo=titulo_notif, # Título Curto
                tipo=tipo_notif,
                mensagem=f"{autor.first_name or 'Suporte'}: {instance.mensagem[:60]}...", # Preview da mensagem
                link=reverse('detalhe_ticket', kwargs={'pk': ticket.pk})
            )
        
        # Se quem escreveu foi o CLIENTE -> Notificar o time de SUPORTE
        else:
            # Aqui notificamos todos os admins/consultores. 
            # Em sistemas grandes, seria melhor notificar apenas quem está atendendo.
            staff_users = Cliente.objects.filter(is_staff=True) | Cliente.objects.filter(groups__name='Consultores')
            
            notificacoes = []
            for staff in staff_users.distinct():
                notificacoes.append(Notificacao(
                    destinatario=staff,
                    ticket=ticket,
                    titulo="Cliente Respondeu", # Título Claro
                    tipo="mensagem",
                    mensagem=f"{autor.username}: {instance.mensagem[:60]}...",
                    link=reverse('detalhe_ticket', kwargs={'pk': ticket.pk}) + "?origin=fila"
                ))
            
            # Bulk create para performance
            Notificacao.objects.bulk_create(notificacoes)

@receiver(pre_save, sender=Ticket)
def criar_notificacao_status(sender, instance, **kwargs):
    """
    Gera notificação interna quando muda o status (Complementa o e-mail).
    """
    if not instance.pk:
        return

    try:
        old_instance = Ticket.objects.get(pk=instance.pk)
        if old_instance.status_maximo != instance.status_maximo:
            Notificacao.objects.create(
                destinatario=instance.cliente,
                ticket=instance,
                titulo="Status Atualizado", # Título Claro
                tipo="status",
                mensagem=f"O chamado agora está: {instance.get_status_maximo_display()}",
                link=reverse('detalhe_ticket', kwargs={'pk': instance.pk})
            )
    except Ticket.DoesNotExist:
        pass