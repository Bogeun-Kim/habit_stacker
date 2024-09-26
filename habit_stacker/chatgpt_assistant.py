from openai import AsyncOpenAI
from django.conf import settings
from django.core.cache import cache
import base64

class ChatGPTAssistant:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.assistant_ids = {}
        self.challenge_contexts = {}

    async def create_or_update_assistant(self, challenge_id, challenge_title, challenge_duration, challenge_description, challenge_category):
        # 챌린지 컨텍스트 저장
        self.challenge_contexts[challenge_id] = {
            "title": challenge_title,
            "duration": challenge_duration,
            "description": challenge_description,
            "category": challenge_category
        }

        instructions = f"""
        You are the AI assistant for the HabitStacker app's challenge: {challenge_title}. 
        This challenge lasts for {challenge_duration} and falls under the category of {challenge_category}.
        Challenge Description: {challenge_description}

        Your role:
        1. Help users understand and stay committed to this specific challenge.
        2. Provide motivation and encouragement tailored to this challenge's goals.
        3. Offer advice on achieving this challenge, considering its duration and category.
        4. Answer user questions concisely and clearly, always in the context of this challenge.
        5. When users upload verification photos, analyze them in relation to this challenge's requirements.
        6. Mention anything particularly relevant to this challenge's certification process.
        7. Provide inspiration specific to this challenge when appropriate.

        Always maintain a positive and encouraging tone, and keep the focus on this particular challenge.
        """

        try:
            # 기존 어시스턴트 찾기
            assistants = await self.client.beta.assistants.list()
            existing_assistant = next((a for a in assistants.data if a.name == f"HabitStackerAssistant_{challenge_id}"), None)

            if existing_assistant:
                # 기존 어시스턴트 업데이트
                updated_assistant = await self.client.beta.assistants.update(
                    assistant_id=existing_assistant.id,
                    instructions=instructions,
                    model="gpt-4-turbo-preview",
                    tools=[{"type": "code_interpreter"}]
                )
                self.assistant_ids[challenge_id] = updated_assistant.id
            else:
                # 새 어시스턴트 생성
                new_assistant = await self.client.beta.assistants.create(
                    name=f"HabitStackerAssistant_{challenge_id}",
                    instructions=instructions,
                    model="gpt-4-turbo-preview",
                    tools=[{"type": "code_interpreter"}]
                )
                self.assistant_ids[challenge_id] = new_assistant.id

            return self.assistant_ids[challenge_id]
        except Exception as e:
            print(f"Error creating/updating assistant: {str(e)}")
            return None

    async def get_or_create_thread(self, user_id, challenge_id):
        thread_id = cache.get(f'thread_id_{user_id}_{challenge_id}')
        if not thread_id:
            thread = await self.client.beta.threads.create()
            thread_id = thread.id
            cache.set(f'thread_id_{user_id}_{challenge_id}', thread_id, timeout=None)
        return thread_id

    async def add_message_to_thread(self, thread_id, message):
        return await self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )

    async def run_assistant(self, thread_id, challenge_id):
        assistant_id = self.assistant_ids.get(challenge_id)
        if not assistant_id:
            raise ValueError("Assistant ID not found for the given challenge_id")

        run = await self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        while run.status != 'completed':
            run = await self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        return run

    async def get_assistant_response(self, thread_id):
        messages = await self.client.beta.threads.messages.list(thread_id=thread_id)
        return messages.data[0].content[0].text.value

    async def process_image(self, image_data, challenge_context):
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {
                        "role": "system",
                        "content": f"챌린지: {challenge_context['title']}에 대한 이미지를 분석합니다. "
                                   f"챌린지 기간: {challenge_context['duration']}, "
                                   f"카테고리: {challenge_context['category']}, "
                                   f"설명: {challenge_context['description']}"
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "이 이미지를 챌린지의 맥락에서 분석해 주세요."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"이미지 처리 중 오류 발생: {str(e)}")
            return "이미지 분석을 수행할 수 없습니다. 텍스트 기반 응답만 제공됩니다."

    async def process_chat_message_async(self, user_id, challenge_id, message, image_data):
        challenge_context = self.challenge_contexts.get(challenge_id, {})
        
        thread_id = await self.get_or_create_thread(user_id, challenge_id)
        
        if image_data:
            # 이미지 분석
            image_analysis = await self.process_image(image_data, challenge_context)
            
            # 이미지 분석 결과를 스레드에 추가
            await self.add_message_to_thread(thread_id, f"사용자가 인증 이미지를 업로드했습니다. 이미지 분석 결과: {image_analysis}")
        
        # 사용자 메시지를 스레드에 추가
        await self.add_message_to_thread(thread_id, message)
        
        # 어시스턴트 실행
        await self.run_assistant(thread_id, challenge_id)
        
        # 어시스턴트의 응답 가져오기
        response = await self.get_assistant_response(thread_id)
        
        return response