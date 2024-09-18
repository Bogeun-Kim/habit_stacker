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
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.utils import timezone
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
import json
from asgiref.sync import sync_to_async
from openai import OpenAI
import json
from django.conf import settings
import base64
from PIL import Image
import io

from .settings import OPENAI_API_KEY
from .models import Challenge, ChallengeParticipant, User, ChallengeAuthentication, ChatMessage
from .forms import SignUpForm, LoginForm, ChallengeForm
from .chatgpt_assistant import ChatGPTAssistant
import logging

logger = logging.getLogger(__name__)

from django.core.cache import cache

@require_GET
async def get_chat_history(request, challenge_id):
    try:
        page = int(request.GET.get('page', 1))
        page_size = 5

        get_messages = sync_to_async(lambda: list(ChatMessage.objects.filter(challenge_id=challenge_id).order_by('-timestamp').select_related('user')))
        messages = await get_messages()

        start = (page - 1) * page_size
        end = start + page_size
        paginated_messages = messages[start:end]

        history = []
        for message in paginated_messages:
            history.append({
                'id': message.id,
                'user': message.user.username if message.user else 'AI',
                'message': message.message,
                'timestamp': message.timestamp.isoformat(),
                'image_url': message.image.url if message.image else None
            })

        return JsonResponse({'history': history[::-1]})  # 역순으로 반환
    except ValueError as e:
        logger.error(f"잘못된 입력: {e}")
        return JsonResponse({'status': 'error', 'error': '잘못된 입력입니다.'}, status=400)
    except Exception as e:
        logger.exception("get_chat_history에서 예상치 못한 오류 발생")
        return JsonResponse({'status': 'error', 'error': '서버 오류가 발생했습니다.'}, status=500)

@require_POST
@csrf_exempt
async def chat_message(request):
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        elif request.content_type.startswith('multipart/form-data'):
            data = request.POST
        else:
            return JsonResponse({'status': 'error', 'error': '지원되지 않는 content-type입니다.'}, status=400)

        challenge_id = data.get('challenge_id')
        message = data.get('message')
        image = request.FILES.get('image')
        
        if not challenge_id or not message:
            return JsonResponse({'status': 'error', 'error': '챌린지 ID와 메시지는 필수입니다.'}, status=400)
        
        get_challenge = sync_to_async(Challenge.objects.get)
        challenge = await get_challenge(id=challenge_id)
        
        User = get_user_model()
        get_user = sync_to_async(User.objects.get)
        
        @sync_to_async
        def get_user_id():
            return request.user.id
        
        user_id = await get_user_id()
        user = await get_user(id=user_id)
        
        assistant = ChatGPTAssistant()
        
        create_chat_message = sync_to_async(ChatMessage.objects.create)
        user_message = await create_chat_message(
            challenge=challenge,
            user=user,
            message=message,
            image=image if image else None
        )

        user_response = {
            'status': 'success',
            'message': {
                'id': user_message.id,
                'user': user_message.user.username,
                'message': user_message.message,
                'timestamp': user_message.timestamp.isoformat(),
                'image_url': user_message.image.url if user_message.image else None
            }
        }

        async def stream_response():
            yield json.dumps(user_response).encode('utf-8') + b'\n'

            image_data = None
            if image:
                image_data = await sync_to_async(image.read)()
            
            ai_response = await assistant.process_chat_message_async(user.id, challenge_id, message, image_data)

            ai_message = await create_chat_message(
                challenge=challenge,
                user=None,
                message=ai_response
            )

            ai_response = {
                'status': 'success',
                'message': {
                    'id': ai_message.id,
                    'user': 'AI',
                    'message': ai_message.message,
                    'timestamp': ai_message.timestamp.isoformat(),
                    'image_url': None
                }
            }

            yield json.dumps(ai_response).encode('utf-8') + b'\n'

        return StreamingHttpResponse(stream_response(), content_type='application/json')

    except Exception as e:
        logger.exception("Unexpected error in chat_message view")
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

# async def translate_to_korean(text):
#     # OpenAI API를 사용하여 텍스트를 한국어로 번역
#     # 이 부분은 실제 OpenAI API 사용 방식에 따라 구현해야 합니다
#     client = OpenAI()
#     response = await client.chat.completions.create(
#         model="gpt-3.5-turbo",
#         messages=[
#             {"role": "system", "content": "You are a translator. Translate the following text to Korean."},
#             {"role": "user", "content": text}
#         ]
#     )
#     return response.choices[0].message.content

def get_authentications(request, challenge_id):
    authentications = ChallengeAuthentication.objects.filter(challenge_id=challenge_id).order_by('-created_at')
    auth_list = []
    for auth in authentications:
        auth_data = {
            'user': auth.user.username,
            'text': auth.text,
            'created_at': auth.created_at.isoformat(),
        }
        if auth.file:
            try:
                # 이미지 파일을 열고 WebP로 변환
                with default_storage.open(auth.file.name, 'rb') as f:
                    img = Image.open(f)
                    img = img.convert('RGB')  # WebP는 알파 채널을 지원하지 않으므로 RGB로 변환
                    buffer = io.BytesIO()
                    img.save(buffer, format="WebP")
                    # Base64로 인코딩
                    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    auth_data['file_url'] = f"data:image/webp;base64,{img_str}"
            except Exception as e:
                print(f"이미지 처리 중 오류 발생: {e}")
                auth_data['file_url'] = None
        else:
            auth_data['file_url'] = None
        auth_list.append(auth_data)
    return JsonResponse({'authentications': auth_list})

def challenge_authentications(request, challenge_id):
    authentications = ChallengeAuthentication.objects.filter(participant__challenge_id=challenge_id).order_by('-created_at')[:10]  # 최근 10개만 가져옵니다
    data = [{
        'user': auth.participant.user.username,
        'text': auth.text,
        'file_url': auth.file.url if auth.file else None,
        'created_at': auth.created_at.isoformat()
    } for auth in authentications]
    return JsonResponse(data, safe=False)

@login_required
def authenticate_challenge(request, challenge_id):
    challenge = get_object_or_404(Challenge, id=challenge_id)
    
    # 사용자가 이 챌린지에 참가했는지 확인
    is_participant = challenge.participants.filter(user=request.user).exists()
    
    if not is_participant:
        # 참가하지 않은 경우 처리 (예: 에러 메시지 표시 또는 참가 페이지로 리다이렉트)
        return render(request, 'habit_stacker/error.html', {'message': '이 챌린지에 참가하지 않았습니다.'})
    
    # 챌린지 정보를 문자열로 변환 (템플릿에서 사용)
    challenge_info = f"제목: {challenge.title}\n기간: {challenge.duration}\n설명: {challenge.description}"
    
    context = {
        'challenge': challenge,
        'challenge_info': challenge_info,
    }
    
    return render(request, 'habit_stacker/authenticate_challenge.html', context)

@csrf_protect
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

def single_challenge_page(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    is_participant = False
    participants_count = challenge.participants.count()

    if request.user.is_authenticated:
        is_participant = ChallengeParticipant.objects.filter(user=request.user, challenge=challenge).exists()

    if is_participant:
        return redirect('joined_challenge', pk=challenge.pk)

    return render(
        request,
    'habit_stacker/single_challenge_page.html',
    {
        'challenge': challenge,
        'is_participant': is_participant,
        'participants_count': participants_count,
    }
)

@login_required
def join_challenge(request, challenge_id):
    challenge = get_object_or_404(Challenge, id=challenge_id)
    if request.user not in challenge.participants.all():
        ChallengeParticipant.objects.create(user=request.user, challenge=challenge)
    return redirect('joined_challenge', pk=challenge_id)

@login_required
def joined_challenge_page(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    is_participant = ChallengeParticipant.objects.filter(user=request.user, challenge=challenge).exists()
    context = {
        'challenge': challenge,
        'is_participant': is_participant,
    }
    print(is_participant)
    print(context)
    return render(request, 'habit_stacker/joined_challenge.html', context)


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



#     challenge = get_object_or_404(Challenge, id=challenge_id)
#     participants = ChallengeParticipant.objects.filter(challenge=challenge)
    
#     return render(request, 'app_name/participants_list.html', {'challenge': challenge, 'participants': participants})