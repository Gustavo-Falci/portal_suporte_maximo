from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from typing import Any
import os
from .models import Ambiente, Area, Ticket

# ==============================================================================
# 1. FORMULÁRIO DE LOGIN (MANTIDO IDÊNTICO)
# ==============================================================================
class EmailAuthenticationForm(AuthenticationForm):
    """
    Formulário de autenticação customizado para usar E-mail como login.
    """
    username = forms.CharField(
        label="E-mail",
        max_length=254,
        widget=forms.EmailInput(attrs={
            "autofocus": True, 
            "class": "form-control", 
            "placeholder": "nome@exemplo.com"
        })
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            "class": "form-control", 
            "placeholder": "Sua senha"
        })
    )

    error_messages = {
        'invalid_login': "Login inválido. E-mail ou senha incorretos.",
        'inactive': "Esta conta está inativa. Entre em contato com o administrador.",
    }

    def __init__(self, request: Any = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(request, *args, **kwargs)


# ==============================================================================
# 2. FORMULÁRIO DE TICKET (COM PRIORIDADE)
# ==============================================================================
class TicketForm(forms.ModelForm):
    """
    ModelForm para Ticket.
    Inclui validação de anexo e filtro de ambientes por usuário.
    """
    class Meta:
        model = Ticket
        # Agora incluímos 'prioridade' na lista de campos
        fields = ['sumario', 'descricao', 'ambiente', 'prioridade', 'area', 'arquivo']
        
        # Estilização com Bootstrap 5
        widgets = {
            'sumario': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Resumo curto'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control', 
                'style': 'height: 150px', 
                'placeholder': 'Descreva detalhadamente o problema'
            }),
            'ambiente': forms.Select(attrs={'class': 'form-select'}),
            'prioridade': forms.Select(attrs={'class': 'form-select'}), 
            'area': forms.Select(attrs={'class': 'form-select'}),
            'arquivo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Captura o usuário para filtrar as opções
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['ambiente'].queryset = Ambiente.objects.filter(cliente=user)
            self.fields['area'].queryset = Area.objects.filter(cliente=user)
        else:
            self.fields['ambiente'].queryset = Ambiente.objects.none()
            self.fields['area'].queryset = Area.objects.none()
        

    def clean_arquivo(self):
        """
        Validação do arquivo (tamanho e extensão).
        """
        arquivo = self.cleaned_data.get('arquivo')
        if arquivo:
            # 1. Limite de Tamanho: 15MB
            if arquivo.size > 15 * 1024 * 1024:
                raise ValidationError("O arquivo é muito grande. O limite máximo é 15MB.")
            
            # 2. Extensões Permitidas
            extensoes_validas = ['.pdf', '.png', '.jpg', '.jpeg', '.txt', '.log', '.csv', '.xlsx', '.docx', '.doc']
            ext = os.path.splitext(arquivo.name)[1].lower()
            
            if ext not in extensoes_validas:
                raise ValidationError(f"Extensão '{ext}' não permitida. Use: PDF, Imagens, Logs, Excel ou Word")
                
        return arquivo