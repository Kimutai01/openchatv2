import uuid
from abc import abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO
from typing import Optional

import boto3
import requests
from botocore.client import Config
from django.conf import settings
from telebot import TeleBot
from telebot.util import smart_split
from twilio.rest import Client

from apps.channels import audio
from apps.channels.models import ChannelSession, ExperimentChannel
from apps.chat.bots import get_bot_from_session
from apps.chat.exceptions import AudioSynthesizeException, MessageHandlerException
from apps.experiments.models import ExperimentSession, SessionStatus


class MESSAGE_TYPES(Enum):
    TEXT = "text"
    VOICE = "voice"


class MessageHandler:
    """
    Base class for message handlers in different channels. This class defines a set of common functions that all channels
    must implement. It provides a blueprint for tuning the behavior of the handler to suit specific channels.

    Attributes:
        voice_replies_supported: Indicates whether the channel supports voice messages

    Args:
        channel: An optional ExperimentChannel object representing the channel associated with the handler.
        experiment_session: An optional ExperimentSession object representing the experiment session associated with the handler.

        Either one of these arguments must to be provided
    Raises:
        MessageHandlerException: If both 'channel' and 'experiment_session' arguments are not provided.

    Properties:
        chat_id: An abstract property that must be implemented in subclasses to return the unique identifier of the chat.
        message_content_type: An abstract property that must be implemented in subclasses to return the type of message content (e.g., text, voice).
        message_text: An abstract property that must be implemented in subclasses to return the text content of the message.

    Abstract methods:
        initialize: (Optional) Performs any necessary initialization
        send_voice_to_user: (Optional) An abstract method to send a voice message to the user. This must be implemented
            if voice_replies_supported is True
        send_text_to_user: Implementation of sending text to the user. Typically this is the reply from the bot
        get_message_audio: The method to retrieve the audio content of the message from the external channel
        transcription_started:A callback indicating that the transcription process has started
        transcription_finished: A callback indicating that the transcription process has finished.
        submit_input_to_llm: A callback indicating that the user input will be given to the language model
    """

    voice_replies_supported = False

    def __init__(
        self, channel: Optional[ExperimentChannel] = None, experiment_session: Optional[ExperimentSession] = None
    ):
        if not channel and not experiment_session:
            raise MessageHandlerException("MessageHandler expects either")

        self.channel = channel
        self.experiment_session = experiment_session
        self.experiment = channel.experiment if channel else experiment_session.experiment
        self.message = None

        self.initialize()

    @abstractmethod
    def initialize(self):
        pass

    @property
    @abstractmethod
    def chat_id(self):
        raise Exception("Not implemented")

    @property
    @abstractmethod
    def message_content_type(self):
        raise Exception("Not implemented")

    @property
    @abstractmethod
    def message_text(self):
        raise Exception("Not implemented")

    @abstractmethod
    def send_voice_to_user(self, voice_audio, duration):
        if self.voice_replies_supported:
            raise Exception(
                "Voice replies are supported but the method reply (`send_voice_to_user`) is not implemented"
            )
        pass

    @abstractmethod
    def send_text_to_user(self, text: str):
        """Channel specific way of sending text back to the user"""
        pass

    @abstractmethod
    def get_message_audio(self) -> BytesIO:
        pass

    @abstractmethod
    def new_bot_message(self, bot_message: str):
        """Handles a message coming from the bot. Call this to send bot messages to the user"""
        raise Exception("Not implemented")

    @abstractmethod
    def transcription_started(self):
        """Callback indicating that the transcription process started"""
        pass

    @abstractmethod
    def transcription_finished(self, transcript: str):
        """Callback indicating that the transcription is finished"""
        pass

    @abstractmethod
    def submit_input_to_llm(self):
        """Callback indicating that the user input will now be given to the LLM"""
        pass

    @staticmethod
    def from_experiment_session(experiment_session: ExperimentSession) -> "MessageHandler":
        """Given a `channel_session` instance, returns the correct MessageHandler subclass to use"""
        channel_session = experiment_session.get_channel_session()
        platform = channel_session.experiment_channel.platform

        if platform == "telegram":
            PlatformMessageHandlerClass = TelegramMessageHandler
        elif platform == "web":
            PlatformMessageHandlerClass = WebMessageHandler
        elif platform == "whatsapp":
            PlatformMessageHandlerClass = WhatsappMessageHandler
        else:
            raise Exception(f"Unsupported platform type {platform}")
        return PlatformMessageHandlerClass(
            channel=channel_session.experiment_channel, experiment_session=experiment_session
        )

    def _add_message(self, message):
        """Adds the message to the handler in order to extract session information"""
        self.message = message
        self._ensure_sessions_exists()

    def new_user_message(self, message) -> str:
        """Handles the message coming from the user. Call this to send bot messages to the user.
        The `message` here will probably be some object, depending on the channel being used.
        """
        self._add_message(message)
        if self.channel.platform != "web":
            # Webchats' statuses are updated through an "external" flow
            self.experiment_session.status = SessionStatus.ACTIVE
            self.experiment_session.save()

        response = None
        if self.message_content_type == MESSAGE_TYPES.TEXT:
            response = self._get_llm_response(self.message_text)
            self.send_text_to_user(response)
        elif self.message_content_type == MESSAGE_TYPES.VOICE:
            transcript = self._get_voice_transcript()
            response = self._get_llm_response(transcript)
            if self.voice_replies_supported and self.experiment.synthetic_voice:
                self._reply_voice_message(response)
            else:
                self.send_text_to_user(response)
        # Returning the response here is a bit of a hack to support chats through the web UI while trying to
        # use a coherent interface to manage / handle user messages
        return response

    def _reply_voice_message(self, text: str):
        try:
            voice_audio, duration = audio.synthesize_voice(text, synthetic_voice=self.experiment.synthetic_voice)
            self.send_voice_to_user(voice_audio, duration)
        except AudioSynthesizeException:
            self.send_text_to_user(text)

    def _get_voice_transcript(self) -> str:
        # Indicate to the user that the bot is busy processing the message
        self.transcription_started()

        audio_file = self.get_message_audio()
        transcript = audio.get_transcript(audio_file)

        self.transcription_finished(transcript)
        return transcript

    def _get_llm_response(self, text: str) -> str:
        """
        Handles a user message by sending it for experiment response and replying with the answer.
        """
        self.submit_input_to_llm()

        return self._get_experiment_response(session_id=self.experiment_session.id, message=text)

    def _get_experiment_response(self, session_id: int, message: str) -> str:
        session = ExperimentSession.objects.get(id=session_id)
        experiment_bot = get_bot_from_session(session)
        answer = experiment_bot.get_response(message)
        experiment_bot.save_history()
        session.no_activity_ping_count = 0
        session.save()
        return answer

    def _ensure_sessions_exists(self):
        """
        Ensures an experiment session exists for the given experiment and chat ID.

        Checks if an experiment session already exists for the specified experiment and chat ID.
        If not, a new experiment session is created and associated with the chat.
        """
        if self.experiment_session and not self.channel:
            # Since web channels doesn't have channel records (atm), they will only have experiment sessions
            # so we don't create channel_sessions for them.
            return

        self.experiment_session = ExperimentSession.objects.filter(
            experiment=self.experiment,
            channel_session__external_chat_id=str(self.chat_id),
        ).first()
        if not self.experiment_session:
            self._create_experiment_and_channel_sessions()
        elif not self.experiment_session.channel_session.experiment_channel:
            # This branch will only be entered for channel sessions that were created by the data migration.
            # These sessions doesn't have experiment channels associated with them, so we need to make sure that
            # they have experiment channels here. For new chats/sessions, the channel is added when they're
            # created in _create_experiment_and_channel_sessions.
            # See this PR: https://github.com/czue/gpt-playground/pull/67
            # If you see this comment in or after November 2023, you can remove this code. Do update the data
            # migration (apps/channels/migrations/0005_create_channel_sessions.py) to link experiment channels
            # to the channel sessions when removing this code
            channel_session = self.experiment_session.channel_session
            channel_session.experiment_channel = self.channel
            channel_session.save()

    def _create_experiment_and_channel_sessions(self):
        self.experiment_session = ExperimentSession.objects.create(
            user=None,
            participant=None,
            experiment=self.experiment,
            llm=self.experiment.llm,
        )

        channel_session = ChannelSession(
            external_chat_id=self.chat_id,
            experiment_session=self.experiment_session,
            experiment_channel=self.channel,
        )
        channel_session.save()


class WebMessageHandler(MessageHandler):
    """Message Handler for the UI"""

    voice_replies_supported = False

    @property
    def chat_id(self) -> int:
        return self.message.chat_id

    @property
    def message_content_type(self):
        return MESSAGE_TYPES.TEXT

    @property
    def message_text(self):
        return self.message.message_text

    def new_bot_message(self, bot_message: str):
        # Simply adding a new AI message to the chat history will cause it to be sent to the UI
        pass


class TelegramMessageHandler(MessageHandler):
    voice_replies_supported = True

    def initialize(self):
        self.telegram_bot = TeleBot(self.channel.extra_data["bot_token"], threaded=False)

    @property
    def chat_id(self) -> int:
        return self.message.chat.id

    @property
    def message_content_type(self):
        if self.message.content_type == "text":
            return MESSAGE_TYPES.TEXT
        elif self.message.content_type == "voice":
            return MESSAGE_TYPES.VOICE

    @property
    def message_text(self):
        return self.message.text

    def send_voice_to_user(self, voice_audio, duration):
        self.telegram_bot.send_voice(self.chat_id, voice=voice_audio, duration=duration)

    def send_text_to_user(self, text: str):
        for message_text in smart_split(text):
            self.telegram_bot.send_message(chat_id=self.chat_id, text=message_text)

    def get_message_audio(self) -> BytesIO:
        file_url = self.telegram_bot.get_file_url(self.message.voice.file_id)
        ogg_audio = BytesIO(requests.get(file_url).content)
        return audio.convert_ogg_to_wav(ogg_audio)

    def new_bot_message(self, bot_message: str):
        """Handles a message coming from the bot. Call this to send bot messages to the user"""
        channel_session = self.experiment_session.channel_session
        self.telegram_bot.send_message(chat_id=channel_session.external_chat_id, text=bot_message)

    # Callbacks

    def submit_input_to_llm(self):
        # Indicate to the user that the bot is busy processing the message
        self.telegram_bot.send_chat_action(chat_id=self.chat_id, action="typing")

    def transcription_started(self):
        self.telegram_bot.send_chat_action(chat_id=self.chat_id, action="upload_voice")

    def transcription_finished(self, transcript: str):
        self.telegram_bot.send_message(
            self.chat_id, text=f"I heard: {transcript}", reply_to_message_id=self.message.message_id
        )


class WhatsappMessageHandler(MessageHandler):
    voice_replies_supported = True

    def initialize(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    def send_text_to_user(self, text: str):
        from_number = self.channel.extra_data["number"]
        to_number = self.chat_id
        self.client.messages.create(from_=f"whatsapp:{from_number}", body=text, to=f"whatsapp:{to_number}")

    @property
    def chat_id(self) -> int:
        return self.message.chat_id

    @property
    def message_content_type(self):
        return self.message.content_type

    @property
    def message_text(self):
        return self.message.message_text

    def new_bot_message(self, bot_message: str):
        """Handles a message coming from the bot. Call this to send bot messages to the user"""
        from_number = self.channel.extra_data["number"]
        channel_session = self.experiment_session.get_channel_session()
        to_number = channel_session.external_chat_id
        self.client.messages.create(from_=f"whatsapp:{from_number}", body=bot_message, to=f"whatsapp:{to_number}")

    def get_message_audio(self) -> BytesIO:
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        ogg_audio = BytesIO(requests.get(self.message.media_url, auth=auth).content)
        return audio.convert_ogg_to_wav(ogg_audio)

    def transcription_finished(self, transcript: str):
        self.send_text_to_user(f'I heard: "{transcript}"')

    def send_voice_to_user(self, voice_audio, duration):
        """
        Uploads the synthesized voice to AWS and send the public link to twilio
        """
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.WHATSAPP_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.WHATSAPP_AWS_SECRET_KEY,
            region_name=settings.WHATSAPP_AWS_REGION,
            config=Config(signature_version="s3v4"),
        )
        file_path = f"{self.chat_id}/{uuid.uuid4()}.mp3"
        audio_bytes = voice_audio.getvalue()
        s3_client.upload_fileobj(
            BytesIO(audio_bytes),
            settings.WHATSAPP_AWS_AUDIO_BUCKET,
            file_path,
            ExtraArgs={
                "Expires": datetime.utcnow() + timedelta(minutes=7),
                "Metadata": {
                    "DurationSeconds": str(duration),
                },
                "ContentType": "audio/mpeg",
            },
        )
        public_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.WHATSAPP_AWS_AUDIO_BUCKET,
                "Key": file_path,
            },
            ExpiresIn=360,
        )
        print(f"\n\npublic_url: {public_url}\n\n")
        from_number = self.channel.extra_data["number"]
        to_number = self.chat_id
        self.client.messages.create(from_=f"whatsapp:{from_number}", to=f"whatsapp:{to_number}", media_url=[public_url])
