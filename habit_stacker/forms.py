from django import forms
from .models import User, Challenge, Comment, Authentication, UserProfile
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
        
class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'placeholder': '사용자 이름'
        })
        self.fields['email'].widget.attrs.update({
            'placeholder': '이메일 주소'
        })

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['profile_picture']

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({
            'placeholder': '챌린지 제목'
        })
        self.fields['description'].widget.attrs.update({
            'placeholder': '챌린지 설명'
        })
        self.fields['note'].widget.attrs.update({
            'placeholder': '챌린지 노트'
        })

class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '현재 비밀번호'})
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '새 비밀번호'})
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '새 비밀번호 확인'})
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError('현재 비밀번호가 올바르지 않습니다.')
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError('새 비밀번호가 일치하지 않습니다.')
        return cleaned_data

    def save(self, commit=True):
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user