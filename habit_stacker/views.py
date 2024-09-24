from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView
# Paginator
from django.core.paginator import Paginator

# 댓글
# from .models import Comment

# 검색
from django.db.models import Q

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
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
import json
from asgiref.sync import sync_to_async
from openai import OpenAI
import json
from django.conf import settings
import base64
from PIL import Image
import io
import os
from .settings import OPENAI_API_KEY
from .models import Challenge, ChallengeParticipant, User, ChallengeAuthentication, ChatMessage, Authentication, Comment
from .forms import SignUpForm, LoginForm, ChallengeForm, CommentForm, AuthenticationForm
from .chatgpt_assistant import ChatGPTAssistant
import logging

logger = logging.getLogger(__name__)

from django.core.cache import cache

@login_required
@require_GET
def get_user_challenges(request, user_id):
    try:
        user_challenges = Challenge.objects.filter(participants__user=user_id).values('id', 'title')
        return JsonResponse(list(user_challenges), safe=False)
    except Exception as e:
        logger.exception("사용자 챌린지 목록을 가져오는 중 오류 발생")
        return JsonResponse({'status': 'error', 'error': '서버 오류가 발생했습니다.'}, status=500)

@require_GET
async def get_chat_history(request, challenge_id, user_id):
    try:
        page = int(request.GET.get('page', 1))
        page_size = 5

        get_messages = sync_to_async(lambda: list(ChatMessage.objects.filter(
            challenge_id=challenge_id,
            user_id__in=[user_id, None]  # user_id가 None인 경우 AI 메시지
        ).order_by('-timestamp').select_related('user')))
        messages = await get_messages()

        start = (page - 1) * page_size
        end = start + page_size
        paginated_messages = messages[start:end]

        history = []
        for message in paginated_messages:
            history.append({
                'id': message.id,
                'user': message.user.username if message.user else message.user.username,
                'message': message.message,
                'timestamp': message.timestamp.isoformat(),
                'image_url': message.image.url if message.image else None,
                'is_ai': message.is_ai
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
            logger.error(f"Unsupported content-type: {request.content_type}")
            return JsonResponse({'status': 'error', 'error': '지원되지 않는 content-type입니다.'}, status=400)

        challenge_id = data.get('challenge_id')
        message = data.get('message', '')
        image = request.FILES.get('image')

        logger.info(f"Received request - challenge_id: {challenge_id}, message: {message}, image: {image is not None}")

        if not challenge_id:
            logger.error("Missing challenge_id")
            return JsonResponse({'status': 'error', 'error': '챌린지 ID는 필수입니다.'}, status=400)

        if not message and not image:
            logger.error("Missing both message and image")
            return JsonResponse({'status': 'error', 'error': '메시지나 이미지 중 하나는 필수입니다.'}, status=400)
        
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
        
        # 챌린지별 어시스턴트 생성 또는 업데이트 (모든 필요한 정보 전달)
        await assistant.create_or_update_assistant(
            challenge_id,
            challenge.title,
            challenge.duration,
            challenge.description,
            challenge.category
        )
        
        create_chat_message = sync_to_async(ChatMessage.objects.create)
        user_message = await create_chat_message(
            challenge=challenge,
            user=user,
            message=message,
            image=image if image else None
        )

        # 이미지가 포함되어 있으면 챌린지 인증 진행
        if image:
            create_authentication = sync_to_async(Authentication.objects.create)
            await create_authentication(
                user=user,
                challenge=challenge,
                text=message,
                file=image
            )

        user_response = {
            'status': 'success',
            'message': {
                'id': user_message.id,
                'user': user_message.user.username,
                'message': user_message.message,
                'timestamp': user_message.timestamp.isoformat(),
                'image_url': user_message.image.url if user_message.image else None,
                'is_ai': False
            }
        }

        image_data = None
        if image:
            # 이미지 파일이 저장된 후 WebP로 변환 후 base64로 인코딩
            await sync_to_async(default_storage.save)(image.name, image)
            with default_storage.open(image.name, 'rb') as f:
                img = Image.open(f)
                img = img.convert('RGB')  # WebP는 알파 채널을 지원하지 않으므로 RGB로 변환
                buffer = io.BytesIO()
                img.save(buffer, format="WebP")
                image_data = buffer.getvalue()  # bytes 타입으로 변환
        
        ai_response = await assistant.process_chat_message_async(user.id, challenge_id, message, image_data)

        ai_message = await create_chat_message(
            challenge=challenge,
            user=user,
            message=ai_response,
            is_ai=True
        )

        ai_response = {
            'status': 'success',
            'message': {
                'id': ai_message.id,
                'user': 'AI',
                'message': ai_message.message,
                'timestamp': ai_message.timestamp.isoformat(),
                'image_url': None,
                'is_ai': True
            }
        }

        response_data = [user_response, ai_response]
        return StreamingHttpResponse((json.dumps(data).encode('utf-8') + b'\n' for data in response_data), content_type='application/json')

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({'status': 'error', 'error': '잘못된 JSON 형식입니다.'}, status=400)
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

@login_required
def my_challenge_authentications(request, challenge_id):
    try:
        challenge = Challenge.objects.get(id=challenge_id)
        authentications = Authentication.objects.filter(challenge=challenge, user=request.user.id).order_by('-created_at')
        
        auth_data = [{
            'user': auth.user.username,
            'user_id': auth.user.id,
            'text': auth.text,
            'file_url': auth.file.url if auth.file else None,
            'created_at': auth.created_at.isoformat(),
            'index': auth.index,
        } for auth in authentications]
        
        return JsonResponse({'authentications': auth_data})
    except Challenge.DoesNotExist:
        return JsonResponse({'error': 'Challenge not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def challenge_authentications(request, challenge_id):
    try:
        challenge = Challenge.objects.get(id=challenge_id)
        authentications = Authentication.objects.filter(challenge=challenge).order_by('-created_at')
        
        auth_data = [{
            'user': auth.user.username,
            'user_id': auth.user.id,  # user_id 추가
            'text': auth.text,
            'file_url': auth.file.url if auth.file else None,
            'created_at': auth.created_at.isoformat(),
            'index': auth.index,
        } for auth in authentications]
        
        return JsonResponse({'authentications': auth_data})
    except Challenge.DoesNotExist:
        return JsonResponse({'error': 'Challenge not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_comments(request, challenge_id, user_id, index):
    comments = Comment.objects.filter(
        challenge_id=challenge_id,
        user_id=user_id,
        authentication_id=index
    ).order_by('-created_at')
    
    comments_data = [{
        'id': comment.id,
        'text': comment.text,
        'comment_user': comment.comment_user.username,
        'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'authentication_id': index
    } for comment in comments]
    
    return JsonResponse({'comments': comments_data})

@login_required
def authenticate_challenge(request, challenge_id, user_id, index):
    challenge = get_object_or_404(Challenge, id=challenge_id)
    authentication = get_object_or_404(Authentication, challenge_id=challenge_id, user_id=user_id, index=index)
    context = {
        'challenge': challenge,
        'authentication': authentication,
        'user': request.user,
        'index': index,
    }
    return render(request, 'habit_stacker/authenticate_user_page.html', context)

@login_required
def add_comment(request, challenge_id, user_id, index):
    if request.method == 'POST':
        authentication = get_object_or_404(Authentication, challenge_id=challenge_id, user_id=user_id, index=index)
        comment_text = request.POST.get('comment')
        if comment_text:
            comment = Comment.objects.create(
                challenge_id=challenge_id,
                user_id=user_id,
                authentication_id=index,
                comment_user=request.user,
                text=comment_text
            )
            return JsonResponse({
                'status': 'success',
                'comment_id': comment.id,
                'comment_text': comment.text,
                'comment_user': comment.comment_user.username,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'authentication_id': index
            })
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def edit_challenge(request, challenge_id):
    authentication = get_object_or_404(Authentication, challenge_id=challenge_id, user=request.user)
    if request.method == 'POST':
        form = AuthenticationForm(request.POST, request.FILES, instance=authentication)
        if form.is_valid():
            updated_authentication = form.save(commit=False)
            if 'new_image' in request.FILES:
                updated_authentication.file = request.FILES['new_image']
            updated_authentication.save()
            messages.success(request, '챌린지 인증이 성공적으로 수정되었습니다.')
            return redirect('joined_challenge', pk=challenge_id)
        else:
            messages.error(request, '폼 데이터가 유효하지 않습니다. 다시 확인해주세요.')
    else:
        form = AuthenticationForm(instance=authentication)
    
    return render(request, 'habit_stacker/edit_challenge_authenticate.html', {
        'form': form, 
        'authentication': authentication,
        'challenge_id': challenge_id
    })

# @login_required
# def authenticate_challenge(request, challenge_id):
#     challenge = get_object_or_404(Challenge, id=challenge_id)
    
#     # 사용자가 이 챌린지에 참가했는지 확인
#     is_participant = challenge.participants.filter(user=request.user).exists()
    
#     if not is_participant:
#         # 참가하지 않은 경우 처리 (예: 에러 메시지 표시 또는 참가 페이지로 리다이렉트)
#         return render(request, 'habit_stacker/error.html', {'message': '이 챌린지에 참가하지 않았습니다.'})
    
#     # 챌린지 정보를 문자열로 변환 (템플릿에서 사용)
#     challenge_info = f"제목: {challenge.title}\n기간: {challenge.duration}\n설명: {challenge.description}"
    
#     context = {
#         'challenge': challenge,
#         'challenge_info': challenge_info,
#     }
    
#     return render(request, 'habit_stacker/authenticate_challenge.html', context)

def create_challenge(request):
    if request.method == 'POST':
        form = ChallengeForm(request.POST, request.FILES)
        if form.is_valid():
            challenge = form.save(commit=False)
            challenge.created_at = timezone.now()
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
    challenge_index = Authentication.objects.filter(challenge=challenge, user=request.user).count()
    authentication = Authentication.objects.filter(challenge=challenge)
    context = {
        'challenge': challenge,
        'is_participant': is_participant,
        'challenge_index': challenge_index,
        'authentication': authentication,
    }
    return render(request, 'habit_stacker/joined_challenge.html', context)


def main_page(request):
    # 참여자 수가 가장 많은 12개의 챌린지를 가져옵니다.
    popular_challenges = Challenge.objects.annotate(
        participants_count=Count('participants')
    ).order_by('-participants_count')[:12]

    # 기존의 ChallengeList view를 가져옵니다.
    challenge_list_view = ChallengeList.as_view()
    
    # ChallengeList view를 호출하여 결과를 얻습니다.
    response = challenge_list_view(request)
    
    # 만약 response가 TemplateResponse 인스턴스라면 context를 수정합니다.
    if hasattr(response, 'context_data'):
        response.context_data['popular_challenges'] = popular_challenges
    
    return response


def pagination(request):
    challenges = Challenge.objects.all().order_by('-created_at')  # 생성일 기준 내림차순 정렬
    
    # 페이지당 아이템 수 설정
    items_per_page = 12
    
    # 페이지네이터 객체 생성
    paginator = Paginator(challenges, items_per_page)
    
    # 현재 페이지 번호 가져오기 (기본값 1)
    page_number = request.GET.get('page', 1)
    
    # 해당 페이지의 아이템들 가져오기
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'habit_stacker/challenge_list.html', {
        'page_obj': page_obj
    })

# CBV로 페이지 만들기
class ChallengeList(ListView):
    model = Challenge
    template_name = 'habit_stacker/challenge_list.html'
    ordering = '-pk'  # 최신 글부터 나열
    paginate_by = 12

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 참여자 수가 가장 많은 12개의 챌린지를 가져옵니다.
        context['popular_challenges'] = Challenge.objects.annotate(
            participants_count=Count('participants')
        ).order_by('-participants_count')[:12]
        return context

# CBV로 챌린지 생성하기
class ChallengeCreate(LoginRequiredMixin, CreateView):
    model = Challenge
    fields = ['title', 'description', 'duration', 'category', 'image', 'note']
    template_name = 'habit_stacker/challenge_form.html'
    success_url = reverse_lazy('main_page')

    def form_valid(self, form):
        if 'image' in self.request.FILES:
            image_file = self.request.FILES['image']
            file_name = default_storage.get_available_name(os.path.join('challenge_images', image_file.name))
            file_content = ContentFile(image_file.read())
            file_path = default_storage.save(file_name, file_content)
            form.instance.image = file_path
        form.instance.creator = self.request.user  # 챌린지 생성자 설정
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['image'].required = False  # 이미지 필드를 선택적으로 만듦
        return form

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



# 검색 기능
class ChallengeSearch(ChallengeList):
    paginate_by = 12

    def get_queryset(self):
        q = self.kwargs.get('q')
        challenge_list = Challenge.objects.filter(Q(title__contains=q))
        return challenge_list
    
    def get_context_data(self, **kwargs):
        context = super(ChallengeSearch, self).get_context_data(**kwargs)
        q = self.kwargs.get('q')
        context['search_info'] = f'검색: {q} ({self.get_queryset().count()})'
        context['base_url'] = reverse_lazy('main_page')  # main_page의 URL을 base_url로 추가
        return context


# # 상세 댓글
# def comment_detail(request, pk):
#     comment_details = get_object_or_404(Comment, pk=pk)
#     comments = Comment.objects.filter(challenge = pk)
#     if request.method == "POST":
#         comment = Comment()
#         comment.challenge = comment_details
#         comment.body = request.POST.get('body')
#         comment.save()
#         return redirect('single_challenge_page', comment_details.challenge.pk)
#     else:
#         return render(request, 'habit_stacker/comment_detail.html', {'challenge': comment_details,'comment_details': comment_details})



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