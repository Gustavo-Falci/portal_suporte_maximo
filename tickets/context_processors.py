# tickets/context_processors.py
from .models import Notificacao

def notificacoes_usuario(request):
    if request.user.is_authenticated:
        # Filtramos apenas onde lida=False.
        # Assim que você clicar, ela vira lida=True e some desta lista.
        notificacoes = Notificacao.objects.filter(
            destinatario=request.user, 
            lida=False
        ).order_by('-data_criacao')[:5]
        
        # A contagem é simplesmente o tamanho dessa lista
        qtd_nao_lidas = notificacoes.count()
        
        return {
            'notificacoes_list': notificacoes,
            'notificacoes_count': qtd_nao_lidas
        }
    return {}