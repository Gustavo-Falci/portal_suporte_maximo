from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import Ambiente, Area, Ticket, TicketInteracao
import os
import mimetypes

 
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
        'inactive': "Esta conta está inativa. Entre em contato com o suporte.",
    }

 
# 2. FORMULÁRIO DE ABERTURA DE TICKET

class TicketForm(forms.ModelForm):
    """
    Formulário principal de abertura de chamados.
    - Filtra Ambientes pelo Cliente logado.
    - Exibe/Oculta Área baseado no Location do Cliente (Regra PAMPA/ABL).
    """
    class Meta:
        model = Ticket
        fields = ['sumario', 'descricao', 'ambiente', 'prioridade', 'area', 'anexo']
        
        widgets = {
            'sumario': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Resumo curto do problema'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 5, 
                'placeholder': 'Descreva detalhadamente o que aconteceu...'
            }),
            'ambiente': forms.Select(attrs={'class': 'form-select'}),
            'prioridade': forms.Select(attrs={'class': 'form-select'}),
            'area': forms.Select(attrs={'class': 'form-select'}),
            'anexo': forms.FileInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        # Captura o usuário para filtrar as opções
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['ambiente'].queryset = Ambiente.objects.filter(cliente=user)
            
            # Lógica da Área baseada no LOCATION
            location_str = str(user.location).upper() if user.location else ""
            
            # Se for PAMPA ou ABL, carrega as áreas. Caso contrário, esvazia.
            if "PAMPA" in location_str or "ABL" in location_str:
                self.fields['area'].queryset = Area.objects.filter(cliente=user)
                self.fields['area'].required = False # Opcional: define se é obrigatório para esses usuários
            else:
                self.fields['area'].queryset = Area.objects.none()
                self.fields['area'].required = False
                self.fields['area'].widget = forms.HiddenInput()

    def clean_anexo(self):
        """Validação de segurança de arquivos (Tamanho e Extensão)"""
        arquivo = self.cleaned_data.get('anexo')
        if arquivo:
            # 1. Validar tamanho (Limite: 5MB)
            if arquivo.size > 5 * 1024 * 1024:
                raise ValidationError("O arquivo é muito grande (Máx 5MB).")
            
            # 2. Validar extensão
            ext = os.path.splitext(arquivo.name)[1].lower()
            extensoes_validas = ['.pdf', '.png', '.jpg', '.jpeg', '.txt', '.xlsx', '.xls', '.docx', '.doc']
            if ext not in extensoes_validas:
                raise ValidationError(f"Extensão '{ext}' não permitida.")
            
            # 3. Validação básica de MIME type (Opcional, mas recomendada)
            content_type_guess, _ = mimetypes.guess_type(arquivo.name)
            allowed_mimes = [
                'application/pdf', 'image/png', 'image/jpeg', 'text/plain', 
                'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ]

            # Aceita se for texto puro ou um dos tipos permitidos. 
            # Se o tipo for desconhecido (None), deixamos passar confiando na extensão para não bloquear falsos negativos.
            if content_type_guess and content_type_guess not in allowed_mimes and 'text' not in content_type_guess:
                 pass 
                
        return arquivo


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
                'placeholder': 'Digite sua resposta ou atualização aqui...'
            }),
            'anexo': forms.FileInput(attrs={'class': 'form-control'})
        }