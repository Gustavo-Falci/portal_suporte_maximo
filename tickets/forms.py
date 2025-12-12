from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import Ambiente, Area

# Formulário de Login (O seu original)
class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="E-mail",
        max_length=254,
        widget=forms.EmailInput(attrs={"autofocus": True, "class": "form-control", "placeholder": "nome@exemplo.com"})
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Sua senha"})
    )

# Formulário de Ticket
class TicketForm(forms.Form):
    sumario = forms.CharField(
        max_length=100, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Resumo curto'})
    )
    descricao_problema = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'style': 'height: 150px', 'placeholder': 'Descreva o problema aqui'})
    )
    # ModelChoiceField garante que o ID enviado realmente existe no banco
    ambiente = forms.ModelChoiceField(
        queryset=Ambiente.objects.none(), # Será preenchido no __init__
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    prioridade = forms.ChoiceField(
        choices=[
            ('', 'Selecione...'),
            ('1', '1 - Crítica'),
            ('2', '2 - Alta'),
            ('3', '3 - Média'),
            ('4', '4 - Baixa'),
            ('5', '5 - Sem prioridade')
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    area = forms.ModelChoiceField(
        queryset=Area.objects.none(), # Será preenchido no __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Validação de Arquivo
    anexo = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        # Recebemos o 'user' para filtrar os ambientes/áreas dele
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['ambiente'].queryset = Ambiente.objects.filter(cliente=user)
            self.fields['area'].queryset = Area.objects.filter(cliente=user)

    def clean_anexo(self):
        arquivo = self.cleaned_data.get('anexo')
        if arquivo:
            # 1. Limite de Tamanho: 5MB
            if arquivo.size > 5 * 1024 * 1024:
                raise ValidationError("O arquivo é muito grande. O limite máximo é 5MB.")
            
            # 2. Extensões Permitidas (Whitelist)
            extensoes_validas = ['.pdf', '.png', '.jpg', '.jpeg', '.txt', '.log', '.csv', '.xlsx', 'docx']
            import os
            ext = os.path.splitext(arquivo.name)[1].lower()
            if ext not in extensoes_validas:
                raise ValidationError(f"Extensão '{ext}' não permitida. Use: PDF, Imagens, Logs, Excel ou Word")
                
        return arquivo