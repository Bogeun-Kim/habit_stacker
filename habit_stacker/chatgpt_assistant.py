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
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {
                    "role": "system",
                    "content": f"You are analyzing an image for the challenge: {challenge_context['title']}. "
                               f"This challenge is about {challenge_context['description']} and lasts for {challenge_context['duration']}. "
                               f"It falls under the category of {challenge_context['category']}. "
                               f"Please analyze the image in the context of this challenge."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please analyze this image in the context of the challenge."},
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

    async def process_chat_message_async(self, user_id, challenge_id, message, image_data):
        challenge_context = self.challenge_contexts.get(challenge_id, {})
        
        messages = [
            {"role": "system", "content": f"You are assisting with the challenge: {challenge_context.get('title')}. "
                                          f"Duration: {challenge_context.get('duration')}, "
                                          f"Category: {challenge_context.get('category')}. "
                                          f"Description: {challenge_context.get('description')}"}
        ]

        if image_data:
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "사용자가 인증 이미지를 업로드했습니다. 이 이미지를 챌린지의 맥락에서 분석해 주세요. 인증을 확인하고 축하해주세요."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            })
        
        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=messages,
                max_tokens=300
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            return "죄송합니다. 메시지 처리 중 오류가 발생했습니다."