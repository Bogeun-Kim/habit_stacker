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
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout, name='logout'),
    path('search/<str:q>/', views.ChallengeSearch.as_view(), name='challenge_search'),

    path('single_challenge_page/<int:pk>/', views.single_challenge_page, name='single_challenge_page'),
    path('join_challenge/<int:challenge_id>/', views.join_challenge, name='join_challenge'),
    path('<int:pk>/joined_challenge/', views.joined_challenge_page, name='joined_challenge'),
    path('challenge/<int:challenge_id>/authenticate/<int:user_id>/<int:index>/', views.authenticate_challenge, name='authenticate_challenge'),
    path('get_comments/<int:challenge_id>/<int:user_id>/<int:index>/', views.get_comments, name='get_comments'),

    path('challenge_form/', views.create_challenge, name='challenge_form'),
    path('challenge/<int:challenge_id>/add_comment/<int:user_id>/<int:index>/', views.add_comment, name='add_comment'),
    path('challenge/<int:challenge_id>/edit_challenge/', views.edit_challenge, name='edit_challenge'),
    path('api/challenge/chat/', views.chat_message, name='chat_message'),

    # path('challenge/<int:challenge_id>/authenticate/', views.authenticate_challenge, name='authenticate_challenge'),
    path('api/challenge/<int:challenge_id>/authentications/', views.challenge_authentications, name='challenge_authentications'),
    path('api/challenge/<int:challenge_id>/my-authentications/', views.my_challenge_authentications, name='my_challenge_authentications'),
    
    path('api/challenge/<int:challenge_id>/chat-history/<int:user_id>/', views.get_chat_history, name='get_chat_history'),
    path('api/user/challenges/<int:user_id>/', views.get_user_challenges, name='get_user_challenges'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.CHALLENGE_IMAGE_URL, document_root=settings.CHALLENGE_IMAGE_ROOT)