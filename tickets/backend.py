from django.contrib.auth.backends import ModelBackend
from .models import Cliente


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        print(f"Tentando autenticar o usuário: {username} com a senha: {password}") # Linha de debug
        try:
            # Tenta encontrar um usuário com o e-mail fornecido
            user = Cliente.objects.get(email=username)
        except Cliente.DoesNotExist:
            return None
        
        # Se o usuário for encontrado, verifica a senha
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
