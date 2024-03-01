from django.conf import settings
from django.core import mail
from django.core.mail import get_connection, EmailMessage, send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
import pdb
from django.conf import settings

from .models import User, Invitation


# @receiver(post_save, sender=User)
# def send_email_to_lecturer(sender, instance, created, **kwargs):
#     if created and instance.role == instance.Role.LECTURER:
#         subject = 'Thông tin tài khoản'
#         message = f'Chào thầy/cô {instance.get_full_name()},'
#         f'\n\nTài khoản thầy cô đã được tạo.\nTài khoản: {instance.username}'
#         f'\nMật khẩu: ou@123\n\n '
#         f'Thầy/cô vui lòng đổi mật trong vòng 24h.'
#         from_email = settings.EMAIL_HOST_USER
#         # #instance.email_user(subject, message, from_email)
#         # send_mail(subject, message, 'phongmauser440@gmail.com', ['2151013069phong@ou.edu.vn'],
#         #           fail_silently=False, )
#         send_mail(subject, message, {settings.EMAIL_HOST_USER}, [{instance.email}], fail_silently=False,)


