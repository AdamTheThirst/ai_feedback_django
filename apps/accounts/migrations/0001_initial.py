"""Начальная миграция приложения accounts."""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
import uuid


class Migration(migrations.Migration):
    """Создаёт таблицу кастомных пользователей и ограничения ролей."""

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Публичный ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
                ("is_staff", models.BooleanField(default=False, verbose_name="staff status")),
                ("date_joined", models.DateTimeField(auto_now_add=True, verbose_name="date joined")),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="Email")),
                ("nickname", models.CharField(max_length=150, verbose_name="Никнейм")),
                ("role", models.CharField(choices=[("user", "Пользователь"), ("admin", "Администратор"), ("superadmin", "Супер-администратор")], default="user", max_length=32, verbose_name="Роль")),
                ("is_primary_superadmin", models.BooleanField(default=False, verbose_name="Главный супер-администратор")),
                ("avatar_letter", models.CharField(max_length=1, verbose_name="Буква аватара")),
                ("avatar_bg_hex", models.CharField(max_length=7, verbose_name="Цвет фона аватара")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_users", to="accounts.user", verbose_name="Кем создан")),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={
                "verbose_name": "Пользователь",
                "verbose_name_plural": "Пользователи",
            },
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                check=Q(("is_primary_superadmin", False), ("role", "superadmin"), _connector="OR"),
                name="accounts_user_primary_requires_superadmin_role",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                check=Q(("role", "user"), ("is_staff", False), _connector="OR") | ~Q(("role", "user")),
                name="accounts_user_regular_not_staff",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                check=Q(("role", "user")) | Q(("is_staff", True)),
                name="accounts_user_admin_roles_staff",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(condition=Q(("is_primary_superadmin", True)), fields=("is_primary_superadmin",), name="accounts_user_single_primary_superadmin"),
        ),
    ]
