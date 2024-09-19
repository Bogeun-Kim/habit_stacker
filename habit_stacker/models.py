from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
import bcrypt
from django.conf import settings
from django.utils import timezone

# Create your models here.
class Challenge(models.Model):
    CATEGORY_CHOICES = [
        ('Environment', 'Environment'),
        ('Exercise', 'Exercise'),
        ('Health', 'Health'),
        ('Sentiment', 'Sentiment'),
        ('Nutrition', 'Nutrition'),
        ('Hobby', 'Hobby'),
    ]

    DURATION_CHOICES = [
        ('For 1 week', 'For 1 week'),
        ('For 2 weeks', 'For 2 weeks'),
        ('For 3 weeks', 'For 3 weeks'),
        ('For 4 weeks', 'For 4 weeks'),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=100)
    description = models.TextField()
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES, default='For 1 week')
    image = models.ImageField(upload_to='challenge_images/', null=True, blank=True)

    def __str__(self):
        return f'[{self.pk}] {self.title}'
    
    #객체의 URL을 반환하는 메서드 정의
    def get_absolute_url(self):
        return reverse("single_challenge_page", kwargs={"pk": self.pk})
    

# 챌린지에 참여한 사용자를 관리하는 모델
# 사용자가 챌린지에 언제 참가했는지, 그리고 참가한 후 인증을 완료했는지 등을 기록함
class ChallengeParticipant(models.Model):
    # user: ForeignKey는 다른 모델과 관계를 설정할 때 사용하는 필드임.
    # User 모델과 연결하여, 각 challengeParticipant가 어떤 사용자(User)인지 나타냄
    # on_delete=models.CASCADE: 사용자가 삭제되면, 이와 연결된 ChallengeParticipant 레코드도 함께 삭제됨
    # releated_name='challenge_participants': 역참조할 때 사용할 이름, 예) 사용자가 어떤 챌린지에 참여했는지 확인할 때 user.challenge_participants로 조회 가능
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenge_participants')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE,related_name='participants')
    join_data = models.DateTimeField(auto_now_add=True) # 참가한 날짜 및 시간 기록
    is_verified = models.BooleanField(default=False) # 사용자가 해당 챌린지에서 인증을 완료했는지 여부를 저장하는 필드, 기본값(default)는 False임. 사용자가 인증을 완료하면 True로 변경할 수 있음
    last_authentication_date = models.DateTimeField(null=True, blank=True)

    # ChallengeParticipant 객체가 출력될 때, 참가한 사용자의 username과 해당 사용자가 참여한 챌린지의 title이 표시되도록 설정했음
    # 예) Newuser2 - 5km running
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'challenge'], name='unique_user_challenge')
        ]

    def __str__(self):
        return f"{self.user.username} - {self.challenge.title}"
    
class User(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=60)  # bcrypt 해시를 저장하기 위한 충분한 길이
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        self.password = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, raw_password):
        return bcrypt.checkpw(raw_password.encode(), self.password.encode())

class ChallengeAuthentication(models.Model):
    participant = models.ForeignKey(ChallengeParticipant, on_delete=models.CASCADE)
    text = models.TextField()
    file = models.FileField(upload_to='challenge_authentications/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.participant} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
class ChatMessage(models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)  # null=True, blank=True 추가
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True)  # 이 줄을 추가합니다

    def __str__(self):
        return f"{self.user.username if self.user else 'AI'}: {self.message[:50]}"