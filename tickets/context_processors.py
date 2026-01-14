# tickets/context_processors.py
from .models import Notificacao

def notificacoes_usuario(request):
    if request.user.is_authenticated:
        # Pega as 5 últimas não lidas ou recentes
        notificacoes = Notificacao.objects.filter(destinatario=request.user).order_by('-data_criacao')[:5]
        qtd_nao_lidas = Notificacao.objects.filter(destinatario=request.user, lida=False).count()
        
        return {
            'notificacoes_list': notificacoes,
            'notificacoes_count': qtd_nao_lidas
        }
    return {}