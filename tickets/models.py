from django.contrib.auth.models import AbstractUser
from django.db import models

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
    