from django.conf import settings
from .models import Ticket, Cliente
from typing import Optional

class MaximoEmailService:
    @staticmethod
    def gerar_corpo_email(ticket: Ticket, usuario: Cliente) -> str:
        """
        Gera o corpo do e-mail formatado estritamente para o Email Listener do Maximo.
        """
        # Dados básicos
        descricao_problema = ticket.descricao
        sumario = ticket.sumario
        prioridade = ticket.prioridade # Certifique-se que o Ticket tem este campo ou mapeie
        
        # Lógica de Ambiente/Ativo
        asset_num = ticket.ambiente.numero_ativo if ticket.ambiente else ""
        
        # Formatação do Header (HTML Display para o analista ler antes das tags)
        corpo = f"Descrição do problema: {descricao_problema}<br><br>"
        
        # INÍCIO DO BLOCO DE TAGS MAXIMO
        corpo += "#MAXIMO_EMAIL_BEGIN<br>"
        corpo += f"SR#DESCRIPTION={sumario}<br>;<br>"
        corpo += f"SR#ASSETNUM={asset_num}<br>;<br>"
        corpo += f"SR#REPORTEDPRIORITY={prioridade}<br>;<br>"

        # Lógica Condicional: Área (Apenas PAMPA/ABL)
        if ticket.area:
            corpo += f"SR#ITC_AREA={ticket.area.nome_area}<br>;<br>"

        # Lógica Condicional: Location (Vem do Cliente)
        location = getattr(usuario, 'location', None)
        if location:
            corpo += f"SR#LOCATION={location}<br>;<br>"

        # Lógica Condicional: Person ID (Vem do Cliente)
        person_id = getattr(usuario, 'person_id', None)
        if person_id:
            corpo += f"SR#AFFECTEDPERSONID={person_id}<br>;<br>"

        # TAGS FIXAS OBRIGATÓRIAS
        corpo += (
            "SR#SITEID=ITCBR<br>;<br>"
            "LSNRACTION=CREATE<br>;<br>"
            "LSNRAPPLIESTO=SR<br>;<br>"
            "SR#CLASS=SR<br>;<br>"
            "SR#TICKETID=&AUTOKEY&<br>;<br>"
            "#MAXIMO_EMAIL_END<br><br>"
        )
        
        return corpo