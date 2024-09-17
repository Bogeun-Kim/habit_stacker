from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import logout as auth_logout, login as auth_login
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_protect

from .models import Challenge, ChallengeParticipant, User
from .forms import SignUpForm, LoginForm, ChallengeForm

def single_challenge_page(request, pk):
    challenge = Challenge.objects.get(pk=pk)

    if request.user.is_authenticated:
        if ChallengeParticipant.objects.filter(user=request.user, challenge=challenge).exists():
            return redirect('joined_challenge', pk=pk)
 

    return render(
        request,
        'habit_stacker/single_challenge_page.html',
        {
            'challenge': challenge,
        }
    )

@csrf_protect
@login_required
def create_challenge(request):
    if request.method == 'POST':
        form = ChallengeForm(request.POST)
        if form.is_valid():
            challenge = form.save(commit=False)
            challenge.creator = request.user
            challenge.save()
            return redirect('main_page')
    else:
        form = ChallengeForm()
    
    return render(request, 'habit_stacker/challenge_form.html', {'form': form})

def joined_challenge_page(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')
    challenge = Challenge.objects.get(pk=pk)
    ChallengeParticipant.objects.create(user=request.user, challenge=challenge)
    #join_challenge(request, pk)
    return render(
        request, 
        'habit_stacker/joined_challenge.html',
        {
            'challenge': challenge,
        }
    )

def main_page(request):
    challenge_list = ChallengeList.as_view()
    return challenge_list(request)

# CBV로 페이지 만들기
class ChallengeList(ListView):
    model = Challenge
    template_name = 'habit_stacker/challenge_list.html'
    ordering = '-pk' # 최신 글부터 나열
    paginate_by = 12


# CBV로 챌린지 생성하기
class ChallengeCreate(LoginRequiredMixin, CreateView):
    model = Challenge
    fields = ['title', 'description', 'duration', 'category']

    # 객체 생성 후 리디렉트할 URL 정의
    success_url = reverse_lazy('challenge_list') # 'challenge_list'는 리디렉션될 페이지의 URL 이름

##회원 관리 코드
@csrf_protect
def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                login(request, user)
                messages.success(request, '회원가입이 완료되었습니다.')
                return redirect('main_page')
            except IntegrityError:
                form.add_error('username', '이미 존재하는 사용자 이름입니다.')
    else:
        form = SignUpForm()
    return render(request, 'habit_stacker/signup.html', {'form': form})

@csrf_protect
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            username = email.split('@')[0]  # 이메일의 @ 이전 부분을 username으로 설정
            user = authenticate(request, username=username, email=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, '로그인되었습니다.')
                return redirect('main_page')
            else:
                messages.error(request, '이메일 또는 비밀번호가 올바르지 않습니다.')
    else:
        form = LoginForm()
    return render(request, 'habit_stacker/login.html', {'form': form})

@csrf_protect
def logout(request):
    auth_logout(request)
    messages.success(request, '로그아웃되었습니다.')
    return redirect('main_page')

# ChallengeParticipant 모델을 사용하여 특정 회원이 챌린지에 참여하고 있는지 여부를 확인하고, 필요에 따라 인증 상태를 업데이트 할 수 있다.

# @login_required
# def join_challenge(request, challenge_id):
#     challenge = get_object_or_404(challenge, id=challenge_id)

#     # 이미 참여한 사용자 여부를 확인
#     if request.user in challenge.participants.all():
#         # 이미 참여한 경우
#         return redirect('single_challenge_page', challenge_id=challenge_id)
    
#     # 참가 처리 (Challenge 모델에 ManyToManyField로 participants 설정)
#     challenge.participants.add(request.user)
#     challenge.save()

#     # 참여한 페이지로 리디렉션
#     return redirect('challenge_')

# @login_required
# def join_challenge(request, challenge_id):

#     challenge = get_object_or_404(Challenge, id=challenge_id)
    
#     # 이미 참가한 유저가 아니면 확인 (ChallengeParticipant 모델을 사용)
#     # if not ChallengeParticipant.objects.filter(user=request.user, challenge=challenge).exists():
#     #     ChallengeParticipant.objects.create(user=request.user, challenge=challenge)
    
#     # 참가한 페이지로 리디렉션
#     return redirect('joined_challenge', pk=challenge_id)



# 참가자 목록 표시
# 특정 챌린지에 참가한 모든 회원 목록을 보고 싶다면, 뷰에서 ChallengeParticipant 모델을 이용해 참가자 정보를 불러오면 된다.
# app_name/views.py
# @login_required
# def challenge_participants(request, challenge_id):
#     challenge = get_object_or_404(Challenge, id=challenge_id)
#     participants = ChallengeParticipant.objects.filter(challenge=challenge)
    
#     return render(request, 'app_name/participants_list.html', {'challenge': challenge, 'participants': participants})


