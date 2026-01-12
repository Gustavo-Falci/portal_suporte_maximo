import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from typing import Optional, Any

# Configurar logger
logger = logging.getLogger(__name__)
Cliente = get_user_model()

class EmailBackend(ModelBackend):
    def authenticate(self, request: Optional[HttpRequest], username: Optional[str] = None, password: Optional[str] = None, **kwargs: Any) -> Optional[Any]:
        logger.info(f"Tentativa de login para o e-mail: {username}")
        
        try:
            user = Cliente.objects.get(email=username)
        except Cliente.DoesNotExist:
            logger.warning(f"Login falhou: Usuário não encontrado para {username}")
            return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            logger.info(f"Login bem-sucedido para: {username}")
            return user
        
        logger.warning(f"Login falhou: Senha incorreta para {username}")
        return None