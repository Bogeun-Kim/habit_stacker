"""
URL configuration for habit_stacker project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', views.main_page, name='main_page'),
    # path('account/', include('django.contrib.auth.urls')),
    # path('account/', include('account.urls')),
    # path('', views.ChallengeList.as_view(), name='challenge_list'),
    path('<int:pk>/', views.single_challenge_page, name='single_challenge_page'),
    # path('<int:pk>/joined_challenge/', views.joined_challenge_page, name='joined_challenge'),
    path('challenge_form/', views.create_challenge, name='challenge_form'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout, name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)