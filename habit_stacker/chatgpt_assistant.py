from openai import AsyncOpenAI
from django.conf import settings
from django.core.cache import cache
import base64

class ChatGPTAssistant:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.assistant_id = None

    async def create_or_update_assistant(self):
        # 기존 어시스턴트가 있는지 확인
        assistants = await self.client.beta.assistants.list()
        existing_assistant = next((a for a in assistants.data if a.name == "HabitStackerAssistant"), None)

        instructions = """
        당신은 HabitStacker 앱의 AI 어시스턴트입니다. 사용자들의 챌린지를 돕고, 동기부여를 제공하며, 
        건강한 챌린지 달성에 대한 조언을 제공합니다. 항상 긍정적이고 격려하는 톤을 유지하세요. 
        사용자의 질문에 대해 간결하고 명확하게 답변하되, 필요한 경우 추가적인 정보나 팁을 제공하세요.
        사용자가 인증 사진을 업로드하면 이를 분석하고 설명해주세요. 특히 습관 인증과 관련된 내용이 있다면 언급해주고 챌린지에 대한 영감을 주는 내용이 있다면 언급해주세요. 챌린지 인증을 축하합니다!
        """

        if existing_assistant:
            # 기존 어시스턴트 업데이트
            updated_assistant = await self.client.beta.assistants.update(
                assistant_id=existing_assistant.id,
                instructions=instructions,
                model="gpt-4-turbo-preview",
                tools=[{"type": "code_interpreter"}]
            )
            return updated_assistant.id
        else:
            # 새 어시스턴트 생성
            new_assistant = await self.client.beta.assistants.create(
                name="HabitStackerAssistant",
                instructions=instructions,
                model="gpt-4-turbo-preview",
                tools=[{"type": "code_interpreter"}]
            )
            return new_assistant.id

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

    async def run_assistant(self, thread_id):
        run = await self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )
        while run.status != 'completed':
            run = await self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        return run

    async def get_assistant_response(self, thread_id):
        messages = await self.client.beta.threads.messages.list(thread_id=thread_id)
        return messages.data[0].content[0].text.value

    async def process_image(self, image_data):
        # Base64로 인코딩된 이미지 데이터를 처리
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        response = await self.client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "챌린지에 대한 인증 사진입니다. 이 사진을 분석하고 설명해주세요. 특히 습관 인증과 관련된 내용이 있다면 언급해주고 챌린지에 대한 영감을 주는 내용이 있다면 언급해주세요. 챌린지 인증을 축하합니다!"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/webp;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
        )
        return response.choices[0].message.content

    async def process_chat_message_async(self, user_id, challenge_id, message=None, image_data=None):
        if message is None or message == "":
            message = "I participated in the challenge. Please encourage me and let me know if there are any changes I need to make based on my images."
        if not self.assistant_id:
            self.assistant_id = await self.create_or_update_assistant()

        thread_id = await self.get_or_create_thread(user_id, challenge_id)
        
        if image_data:
            image_description = await self.process_image(image_data)
            await self.add_message_to_thread(thread_id, f"사용자가 이미지를 업로드했습니다. 이미지 설명: {image_description}")
        
        await self.add_message_to_thread(thread_id, message)
        await self.run_assistant(thread_id)
        return await self.get_assistant_response(thread_id)