import requests
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from tickets.models import Ticket

# Configuração de Log
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sincroniza status, ID e descrição dos tickets com o IBM Maximo'

    def handle(self, *args, **options):
        # API Config
        API_URL = "https://itc.manage.masti.apps-crc.testing/maximo/api/os/ITC_PORTAL_API"
        API_KEY = "roqvr60ie0tihjqqvs8gprj591cueca7265r3of7"
        
        params = {
            "_dropnulls": 0,
            "lean": 1,
            "oslc.select": "ticketid,description,status", # Selecionando campos específicos
        }

        headers = {
            "apikey": API_KEY,
            "Content-Type": "application/json"
        }

        self.stdout.write("--- Iniciando Sincronização com Maximo ---")

        try:
            # verify=False é usado apenas em ambiente de teste (testing)
            response = requests.get(API_URL, params=params, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('member', [])
            
            if not items:
                self.stdout.write("Nenhum ticket retornado pela API.")
                return

            self.processar_tickets(items)

        except Exception as e:
            logger.error(f"Erro na sincronização: {e}")
            self.stdout.write(self.style.ERROR(f"Erro: {e}"))

    def processar_tickets(self, items: list):
        atualizados = 0
        
        # 1. Carrega tickets locais que ainda não foram finalizados (para otimizar)
        # Excluímos CLOSED e CANCELLED da busca local para não reprocessar histórico antigo desnecessariamente
        tickets_locais = Ticket.objects.exclude(status_maximo__in=['CLOSED', 'CANCELLED'])
        
        # 2. Indexação para busca rápida (Hash Map)
        # Pelo ID do Maximo (se já tivermos vinculado antes)
        tickets_por_id = {t.maximo_id: t for t in tickets_locais if t.maximo_id}
        
        # Pelo Sumário/Descrição (normalizando texto: sem espaços nas pontas e minúsculo)
        tickets_por_sumario = {t.sumario.strip().lower(): t for t in tickets_locais if not t.maximo_id}

        for item in items:
            # Maximo retorna chaves em minúsculo conforme seu log
            mx_id = str(item.get('ticketid', ''))
            mx_status = item.get('status', '')
            mx_desc = item.get('description', '').strip()

            if not mx_id:
                continue

            ticket_encontrado = None

            # Estratégia 1: Tenta encontrar pelo ID do Maximo (Link Forte)
            if mx_id in tickets_por_id:
                ticket_encontrado = tickets_por_id[mx_id]
            
            # Estratégia 2: Tenta encontrar pelo texto/sumário (Link Fraco - Primeiro Vínculo)
            elif mx_desc.lower() in tickets_por_sumario:
                ticket_encontrado = tickets_por_sumario[mx_desc.lower()]
                # Vincula imediatamente para futuras execuções
                ticket_encontrado.maximo_id = mx_id

            if ticket_encontrado:
                alterou = False

                # Verifica mudança de Status
                if ticket_encontrado.status_maximo != mx_status:
                    # Valida se o status existe no nosso Model para evitar erros
                    status_valido = any(choice[0] == mx_status for choice in Ticket.MAXIMO_STATUS_CHOICES)
                    
                    if status_valido:
                        ticket_encontrado.status_maximo = mx_status
                        alterou = True

                # Verifica se precisamos salvar o ID novo
                if ticket_encontrado.maximo_id != mx_id:
                    ticket_encontrado.maximo_id = mx_id
                    alterou = True

                if alterou:
                    ticket_encontrado.save()
                    atualizados += 1
                    self.stdout.write(f"Ticket #{ticket_encontrado.id} atualizado: {mx_status} (SR {mx_id})")

        self.stdout.write(self.style.SUCCESS(f"Sincronização concluída. Total atualizados: {atualizados}"))