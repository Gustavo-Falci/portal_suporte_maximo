from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
import os

class Cliente(AbstractUser):
    location = models.CharField(max_length=200, blank=True, null=True)
    person_id = models.CharField(max_length=150, blank=True, null=True)

    groups = models.ManyToManyField(
        "auth.Group",
        related_name="cliente_groups",
        blank=True
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="cliente_permissions",
        blank=True
    )

    class Meta:
        db_table = "clientes"
    
    @property
    def is_consultor(self):
        """Verifica se o usuário pertence ao grupo 'Consultores'."""
        return self.groups.filter(name='Consultores').exists()

    @property
    def is_support_team(self):
        """
        Helper geral: Retorna True se for Staff (Admin) OU Consultor.
        Usado para dar permissões de visualização.
        """
        return self.is_staff or self.is_consultor

class Ambiente(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="ambientes")
    nome_ambiente = models.CharField(max_length=100)
    numero_ativo = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.nome_ambiente} ({self.numero_ativo})"
    
class Area(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="areas")
    nome_area = models.CharField(max_length=100)
    
    def __str__(self):
        return self.nome_area

# --- TICKET (FASE 2) ---

class Ticket(models.Model):
    # Lista Exata de Status do IBM Maximo (ALN Domain)
    MAXIMO_STATUS_CHOICES = [
        ('NEW', 'Novo'),
        ('QUEUED', 'Em fila'),
        ('INPROG', 'Em Andamento'),
        ('PENDING', 'Pendente'),
        ('APPR', 'Aprovado'),
        ('APPFML', 'Aprovado pelo Gerenciador de Cumprimento'),
        ('APPLM', 'Aprovado pelo Gerente de Linha'),
        ('RESOLVED', 'Resolvido'),
        ('CLOSED', 'Fechado'),
        ('CANCELLED', 'Cancelado'),
        ('REJECTED', 'Rejeitado'),
        ('DRAFT', 'Rascunho'),
        ('HISTEDIT', 'Editado no Histórico'),
        ('TSTCLI', 'Teste do cliente'),
        ('TSTCLIOK', 'Teste do cliente OK'),
        ('TSTCLIFAIL', 'Teste do cliente falhou'),
        ('IMPPRODOK', 'Implementação em produção OK'),
        ('AGREUN', 'Reunião Agendada'),
        ('CRITFAIL', 'Falha Crítica'),
        ('ROLLBACK', 'Rollback'),
        ('TREINAMTO', 'Treinamento'),
        ('DOC', 'Documentar'),
        ('SLAHOLD', 'Espera de SLA'),
    ]

    PRIORIDADE_CHOICES = [
        ('', 'Selecione...'),
        ('1', '1 - Crítica'),
        ('2', '2 - Alta'),
        ('3', '3 - Média'),
        ('4', '4 - Baixa'),
        ('5', '5 - Sem Prioridade'),
    ]

    # Vínculos (Quem abriu, Onde, Qual Área)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="tickets")
    ambiente = models.ForeignKey(Ambiente, on_delete=models.SET_NULL, null=True, blank=False)
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, blank=True)

    # Dados do Chamado
    sumario = models.CharField(max_length=100, verbose_name="Resumo do Problema")
    descricao = models.TextField(verbose_name="Descrição Detalhada")
    arquivo = models.FileField(upload_to='anexos_tickets/', null=True, blank=True)
    
    # Integração Maximo
    maximo_id = models.CharField(max_length=50, null=True, blank=True, verbose_name="ID do Chamado (SR)")
    
    # Status padrão é NEW (Novo) até o Maximo processar
    status_maximo = models.CharField(
        max_length=20, 
        default='NEW', 
        choices=MAXIMO_STATUS_CHOICES,
        verbose_name="Status Atual"
    )

    prioridade = models.CharField(
        max_length=2, 
        choices=PRIORIDADE_CHOICES, 
        default='', 
        verbose_name="Prioridade",
        blank=False
    )

    anexo = models.FileField(
        upload_to='ticket_anexos/', 
        null=True, 
        blank=True, 
        verbose_name="Anexo"
    )
    
    # Auditoria (Datas automáticas)
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Aberto em")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Última atualização")

    class Meta:
        ordering = ['-data_criacao'] # Ordena do mais recente para o mais antigo
        db_table = "tickets"
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"

    def __str__(self):
        return f"Ticket #{self.id} - {self.sumario}"

    @property
    def badge_class(self):
        """
        Retorna a classe CSS do Bootstrap (bg-color) baseada no status atual.
        Usado no frontend para colorir as etiquetas automaticamente.
        """
        status = self.status_maximo

        # Verde (Sucesso / Conclusão)
        if status in ['RESOLVED', 'TSTCLIOK', 'IMPPRODOK', 'APPR']:
            return 'bg-success'
        
        # Amarelo/Laranja (Em andamento / Aguardando / Aprovação)
        elif status in ['INPROG', 'PENDING', 'APPFML', 'APPLM', 'TSTCLI', 'AGREUN', 'TREINAMTO', 'DOC', 'SLAHOLD', 'QUEUED']:
            return 'bg-warning text-dark'
        
        # Vermelho (Erro / Falha / Rejeição)
        elif status in ['TSTCLIFAIL', 'CRITFAIL', 'REJECTED', 'ROLLBACK']:
            return 'bg-danger'
        
        # Cinza (Fechado / Cancelado / Histórico)
        elif status in ['CLOSED', 'CANCELLED', 'HISTEDIT', 'DRAFT']:
            return 'bg-secondary'
        
        # Azul (Padrão para Novo)
        else:
            return 'bg-primary'

class TicketInteracao(models.Model):
    ticket = models.ForeignKey(
        Ticket, 
        on_delete=models.CASCADE, 
        related_name="interacoes"
    )
    autor = models.ForeignKey(
        Cliente, 
        on_delete=models.CASCADE,
        verbose_name="Autor"
    )
    mensagem = models.TextField(verbose_name="Mensagem")
    anexo = models.FileField(
        upload_to="interacoes_anexos/", 
        null=True, 
        blank=True,
        verbose_name="Anexo (Opcional)"
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_criacao'] # Ordem cronológica
        db_table = "ticket_interacoes"
        verbose_name = "Interação"
        verbose_name_plural = "Interações"

    def __str__(self):
        return f"Msg de {self.autor.username} em {self.ticket.id}"

    @property
    def is_support(self):
        """
        Verifica se a mensagem deve aparecer como 'Suporte' no chat.
        Isso agora inclui Admins E Consultores.
        """
        return self.autor.is_support_team
    
    @property
    def filename(self):
        """Retorna apenas o nome do arquivo, sem o caminho completo."""
        if self.anexo:
            return os.path.basename(self.anexo.name) if self.anexo else ''
        return None
    
class Notificacao(models.Model):
    # Opções de tipo para ícones no frontend
    TIPO_CHOICES = (
        ('mensagem', 'Nova Mensagem'),
        ('status', 'Mudança de Status'),
        ('sistema', 'Aviso do Sistema'),
    )

    destinatario = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='notificacoes')
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, null=True, blank=True)
    
    titulo = models.CharField(max_length=50, default="Nova Notificação") # Ex: "Nova Resposta"
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='sistema')
    
    mensagem = models.CharField(max_length=255)
    lida = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.titulo} - {self.destinatario}"