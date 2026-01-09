from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.mail import EmailMessage
from django.conf import settings
from .models import Ticket
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