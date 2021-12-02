import json
import logging
import os
from typing import Any, List, Literal, Optional, TypedDict

import requests


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class _InlineKeyboardButton(TypedDict):
    text: str


class InlineKeyboardButton(_InlineKeyboardButton, total=False):
    url: str
    callback_data: str


class InlineKeyboardMarkup(TypedDict):
    inline_keyboard: List[List[InlineKeyboardButton]]


class _User(TypedDict):
    id: int
    is_bot: bool
    first_name: str


class User(_User, total=False):
    pass


class _Chat(TypedDict):
    id: int
    type: Literal['private', 'group', 'supergroup', 'channel']


class Chat(_Chat, total=False):
    title: str


class _MessageEntity(TypedDict):
    type: Literal['mention', 'hashtag', 'cashtag', 'bot_command', 'url', 'email', 'phone_number',
                  'bold', 'italic', 'underline', 'strikethrough', 'code', 'pre', 'text_link', 'text_mention']
    offset: int
    length: int


class MessageEntity(_MessageEntity, total=False):
    pass


From = TypedDict('From', {'from': User})


class _Message(TypedDict):
    message_id: int
    date: int
    chat: Chat


class Message(_Message, From, total=False):
    entities: List[MessageEntity]
    text: str
    new_chat_members: List[User]
    left_chat_member: User


class _CallbackQuery(From):
    id: str


class CallbackQuery(_CallbackQuery, total=False):
    message: Message
    data: str


class _Update(TypedDict):
    id: int


class Update(_Update, total=False):
    message: Message
    callback_query: CallbackQuery


def _send_edit_message(endpoint: str, chat_id: int, text: str, message_id: Optional[int] = None, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
    data: dict[str, Any] = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    if message_id:
        data['message_id'] = message_id
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    response = requests.post(
        url='https://api.telegram.org/bot%s/%s' % (
            os.environ['BOT_TOKEN'], endpoint),
        data=data
    )
    logger.info('status_code: %d' % response.status_code)
    logger.debug(response.content)
    return response.status_code == 200


def send_message(chat_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
    return _send_edit_message(
        endpoint='sendMessage',
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup
    )


def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
    return _send_edit_message(
        endpoint='editMessageText',
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=reply_markup
    )
