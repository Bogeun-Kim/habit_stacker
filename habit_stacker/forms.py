from django import forms
from .models import User, Challenge, Comment, Authentication
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model, authenticate
from django.core.exceptions import ValidationError

User = get_user_model()

class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        max_length=254,
        help_text='필수 항목입니다. 유효한 이메일 주소를 입력하세요.',
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg bg-light fs-6',
            'placeholder': 'Email address',
            'autocomplete': 'email'
        })
    )

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control form-control-lg bg-light fs-6',
            'placeholder': 'Password',
            'autocomplete': 'new-password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control form-control-lg bg-light fs-6',
            'placeholder': 'Confirm Password',
            'autocomplete': 'new-password'
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email'].split('@')[0]
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control form-control-lg bg-light fs-6',
        'placeholder': 'Email address',
        'autocomplete': 'email'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-lg bg-light fs-6',
        'placeholder': 'Password',
        'autocomplete': 'current-password'
    }))

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

class ChallengeForm(forms.ModelForm):
    class Meta:
        model = Challenge
        fields = ['title', 'description', 'duration', 'category', 'image', 'authentication_image', 'note']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'duration': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control-file'}),
            'authentication_image': forms.FileInput(attrs={'class': 'form-control-file'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        # 추가 유효성 검사가 필요한 경우 여기에 구현
        return cleaned_data
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '챌린지 제목'
        })
        self.fields['description'].widget.attrs.update({
            'class': 'form-control',
            'rows': 4,
            'placeholder': '챌린지 설명'
        })
        self.fields['duration'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '챌린지 기간'
        })
        self.fields['category'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '챌린지 카테고리'
        })
        self.fields['image'].widget.attrs.update({
            'class': 'form-control-file',
            'placeholder': '챌린지 이미지'
        })
        self.fields['note'].widget.attrs.update({
            'class': 'form-control',
            'rows': 4,
            'placeholder': '챌린지 노트'
        })      

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text', 'comment_user', 'authentication']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'comment_user': forms.HiddenInput(),
            'authentication': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['text'].widget.attrs.update({
            'class': 'form-control',
            'rows': 3,
            'placeholder': '댓글 작성'
        })

class AuthenticationForm(forms.ModelForm):
    class Meta:
        model = Authentication
        fields = ['text', 'file']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['text'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '인증 텍스트'
        })
        