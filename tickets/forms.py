from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.conf import settings
from .models import Ambiente, Area, Ticket, TicketInteracao
import os
import mimetypes

# --- UTILITÁRIO DE VALIDAÇÃO (DRY & Segurança) ---

def _validar_anexo_comum(arquivo):
    """
    Validação centralizada para uploads (Ticket e Chat).
    Verifica tamanho, extensão e MIME type.
    """
    if not arquivo:
        return None

    # 1. Validar tamanho (Limite: 5MB)
    limit_mb = 150
    if arquivo.size > limit_mb * 1024 * 1024:
        raise ValidationError(f"O ficheiro é muito grande. Máximo permitido: {limit_mb}MB.")
    
    # 2. Validar extensão
    ext = os.path.splitext(arquivo.name)[1].lower()
    extensoes_validas = ['.pdf', '.png', '.jpg', '.jpeg', '.txt', '.xlsx', '.xls', '.docx', '.doc', '.csv', '.zip', '.rar', '.xml']
    
    if ext not in extensoes_validas:
        raise ValidationError(f"Extensão '{ext}' não permitida. Use apenas PDF, Imagens ou Office.")
    
    # 3. Validação de MIME type (Segurança reforçada)
    # Adivinha o tipo baseado no nome do ficheiro (não é perfeito, mas ajuda)
    content_type_guess, _ = mimetypes.guess_type(arquivo.name)
    
    # Lista de tipos seguros
    allowed_mimes = [
        'application/pdf', 
        'image/png', 
        'image/jpeg', 
        'text/plain', 
        'text/csv',
        'application/vnd.ms-excel', 
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/msword', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]

    if content_type_guess:
        is_text = 'text' in content_type_guess
        is_valid = content_type_guess in allowed_mimes
        
        if not (is_valid or is_text):
            raise ValidationError(f"Formato de ficheiro inválido ({content_type_guess}).")
            # pass
    return arquivo


# 1. FORMULÁRIO DE LOGIN

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
        })
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            "class": "form-control", 
        })
    )

    error_messages = {
        'invalid_login': "Login inválido. E-mail ou senha incorretos.",
        'inactive': "Esta conta está inativa. Contacte o suporte.",
    }


# 2. FORMULÁRIO DE ABERTURA DE TICKET

class TicketForm(forms.ModelForm):
    """
    Formulário principal de abertura de chamados.
    """
    class Meta:
        model = Ticket
        fields = ['sumario', 'descricao', 'ambiente', 'prioridade', 'area', 'anexo']
        
        widgets = {
            'sumario': forms.TextInput(attrs={
                'class': 'form-control', 
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 5, 
            }),
            'ambiente': forms.Select(attrs={'class': 'form-select'}),
            'prioridade': forms.Select(attrs={'class': 'form-select'}),
            'area': forms.Select(attrs={'class': 'form-select'}),
            'anexo': forms.FileInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['ambiente'].queryset = Ambiente.objects.filter(cliente=user)
            
            # Lógica de Área baseada no LOCATION
            # Tratamento seguro caso location seja None
            location_str = str(user.location).upper() if getattr(user, 'location', None) else ""
            
            # Verifica se pertence às empresas que exigem Área
            empresas_com_area = ["PAMPA", "ABL"]
            # any() verifica se alguma das empresas está na string location
            tem_acesso_area = any(empresa in location_str for empresa in empresas_com_area)

            if tem_acesso_area:
                self.fields['area'].queryset = Area.objects.filter(cliente=user)
                self.fields['area'].required = False
            else:
                self.fields['area'].queryset = Area.objects.none()
                self.fields['area'].required = False
                self.fields['area'].widget = forms.HiddenInput()

    def clean_anexo(self):
        # Reutiliza a lógica centralizada
        return _validar_anexo_comum(self.cleaned_data.get('anexo'))


# 3. FORMULÁRIO DE INTERAÇÃO (RESPOSTAS)

class TicketInteracaoForm(forms.ModelForm):
    """
    Formulário para adicionar comentários/respostas ao ticket.
    """
    class Meta:
        model = TicketInteracao
        fields = ['mensagem', 'anexo']
        widgets = {
            'mensagem': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
            'anexo': forms.FileInput(attrs={'class': 'form-control'})
        }

    def clean_anexo(self):
        return _validar_anexo_comum(self.cleaned_data.get('anexo'))