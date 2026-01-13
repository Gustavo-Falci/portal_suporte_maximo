import requests
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from tickets.models import Ticket
from requests.adapters import HTTPAdapter, Retry

# Configuração de Log
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sincroniza status, ID e descrição dos tickets com o IBM Maximo'

    def handle(self, *args, **options):

        retry_strategy = Retry(
            total=3,
            backoff_factor=1, # Espera 1s, 2s, 4s...
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("https://", adapter)
        http.mount("http://", adapter)

        API_URL = getattr(settings, 'MAXIMO_API_URL', None)
        API_KEY = getattr(settings, 'MAXIMO_API_KEY', None)
        
        # Parâmetros da API
        params = {
            "_dropnulls": 0,
            "lean": 1,
            "oslc.select": "TICKETID,DESCRIPTION,STATUS", 
        }

        headers = {
            "apikey": API_KEY,
            "Content-Type": "application/json"
        }

        self.stdout.write("--- Iniciando Sincronização (Modo Debug) ---")

        try:
            verify_ssl = getattr(settings, 'MAXIMO_VERIFY_SSL', True)
            
            response = http.get(
                API_URL, 
                params=params, 
                headers=headers, 
                verify=verify_ssl, # Controlado por settings
                timeout=30 # Timeout reduzido para não travar workers
            )
            response.raise_for_status()
            
            data = response.json()
            items = data.get('member', [])
            
            if not items:
                self.stdout.write("API Maximo retornou lista vazia.")
                return

            self.processar_tickets(items)

        except Exception as e:
            logger.error(f"Erro na sincronização: {e}")
            self.stdout.write(self.style.ERROR(f"Erro Crítico: {e}"))

    def processar_tickets(self, items: list) -> None:
        # Contadores separados para melhor clareza no log
        total_vinculados = 0
        total_status_alterados = 0
        
        # 1. Carrega tickets locais (exclui fechados)
        tickets_locais = Ticket.objects.exclude(status_maximo__in=['CLOSED', 'CANCELLED'])
        
        self.stdout.write(f"Tickets locais carregados para verificação: {tickets_locais.count()}")

        # 2. Indexação e Listas
        tickets_por_id = {}
        tickets_sem_id = []

        # Separa quem tem ID de quem não tem
        for t in tickets_locais:
            if t.maximo_id and t.maximo_id.strip():
                tickets_por_id[t.maximo_id.strip()] = t
            else:
                tickets_sem_id.append(t)

        # Debug: Listar tickets que estão esperando vínculo (sem ID)
        if tickets_sem_id:
            self.stdout.write("--- Tickets Locais aguardando vínculo (Sem ID) ---")
            for t in tickets_sem_id:
                self.stdout.write(f"   Local ID: {t.id} | Sumário: '{t.sumario}'")
            self.stdout.write("--------------------------------------------------")

        for item in items:
            mx_id = str(item.get('ticketid', ''))
            mx_status = item.get('status', '')
            mx_desc_raw = item.get('description', '')
            
            # Normalização (minúsculo e sem espaços nas pontas)
            mx_desc_clean = mx_desc_raw.strip().lower()

            if not mx_id:
                continue

            ticket_encontrado = None
            novo_vinculo = False # Flag para saber se houve vínculo nesta iteração

            # --- ESTRATÉGIA 1: ID do Maximo (Já vinculado) ---
            if mx_id in tickets_por_id:
                ticket_encontrado = tickets_por_id[mx_id]
            
            # --- ESTRATÉGIA 2: Busca por Texto (Para novos vínculos) ---
            else:
                for t_local in tickets_sem_id:
                    local_sumario_clean = t_local.sumario.strip().lower()
                    
                    # LOGICA DE MATCH:
                    # 1. Verifica se são IGUAIS
                    # 2. OU se o texto local está CONTIDO no Maximo (Match Parcial)
                    match_exato = (local_sumario_clean == mx_desc_clean)
                    match_parcial = (len(local_sumario_clean) > 5 and local_sumario_clean in mx_desc_clean)

                    if match_exato or match_parcial:
                        ticket_encontrado = t_local
                        
                        # Debug do Match
                        tipo_match = "EXATO" if match_exato else "PARCIAL"
                        self.stdout.write(self.style.SUCCESS(f"MATCH {tipo_match} ENCONTRADO!"))
                        self.stdout.write(f"   Maximo: '{mx_desc_clean}'")
                        self.stdout.write(f"   Local:  '{local_sumario_clean}'")
                        
                        # Realiza o vínculo
                        self._vincular_id(ticket_encontrado, mx_id)
                        novo_vinculo = True
                        total_vinculados += 1
                        
                        # Remove da lista para não duplicar
                        tickets_sem_id.remove(t_local)
                        break

            # --- PROCESSAMENTO DE ATUALIZAÇÃO ---
            if ticket_encontrado:
                # Se acabamos de vincular, o ID já está salvo, mas verificamos o status
                # Se não era novo vínculo, verificamos ID e status
                if self._atualizar_ticket(ticket_encontrado, mx_status, mx_id):
                    total_status_alterados += 1
                    msg_acao = "VINCULADO E ATUALIZADO" if novo_vinculo else "ATUALIZADO"
                    self.stdout.write(f"Ticket #{ticket_encontrado.id} [{msg_acao}] -> Status: {mx_status} (SR {mx_id})")
                elif novo_vinculo:
                    # Se só vinculou mas o status era o mesmo, avisamos também
                    self.stdout.write(f"Ticket #{ticket_encontrado.id} [VINCULADO] -> ID Maximo: {mx_id}")

        # Resumo Final Detalhado
        msg_final = f"Sincronização concluída. Novos Vínculos: {total_vinculados} | Status Alterados: {total_status_alterados}"
        
        if total_vinculados > 0 or total_status_alterados > 0:
            self.stdout.write(self.style.SUCCESS(msg_final))
        else:
            self.stdout.write(msg_final)

    def _vincular_id(self, ticket: Ticket, novo_maximo_id: str):
        """Salva apenas o ID no banco."""
        logger.info(f"VINCULO: Ticket Local #{ticket.id} agora ligado ao Maximo ID {novo_maximo_id}")
        ticket.maximo_id = novo_maximo_id
        ticket.save(update_fields=['maximo_id'])

    def _atualizar_ticket(self, ticket: Ticket, novo_status: str, maximo_id: str) -> bool:
        """
        Verifica mudanças de Status e ID. 
        Retorna True se houve alteração salva no banco.
        """
        alterou = False

        # Verifica ID (redundância de segurança caso não tenha vindo do _vincular_id)
        if ticket.maximo_id != maximo_id:
            ticket.maximo_id = maximo_id
            alterou = True

        # Verifica Status
        if ticket.status_maximo != novo_status:
            # Validação se o status existe na lista do Django
            status_valido = any(choice[0] == novo_status for choice in Ticket.MAXIMO_STATUS_CHOICES)
            
            if status_valido:
                ticket.status_maximo = novo_status
                alterou = True
            else:
                logger.warning(f"Status desconhecido recebido do Maximo: '{novo_status}' para ticket #{ticket.id}. Ignorado.")

        if alterou:
            ticket.save()
        
        return alterou