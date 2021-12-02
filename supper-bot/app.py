import enum
import json
import logging
import os
import traceback
from typing import Any, TypedDict, Union

from jio import JIO_DELIVERY, Jio, JIO_CLOSES, JIO_GST, JIO_SPLIT, JIO_TYPE
from menu import get_menu_choices
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity, Update, User, edit_message_text, send_message

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Command(enum.Enum):
    START = 'start'
    OPEN_JIO = 'openjio'
    CLOSE_JIO = 'closejio'
    ADD_ITEM = 'additem'
    REMOVE_ITEM = 'removeitem'
    VIEW_ORDER = 'vieworder'
    CANCEL = 'cancel'


MESSAGE_ADD_ITEM = 'Please choose an item:'
MESSAGE_ERROR = 'Something went wrong.'
MESSAGE_INVALID_COMMAND = 'Command not recognised.'
MESSAGE_JIO_EXISTS = 'There is already a Supper Jio going on.\n\n/additem to add item to order\n/removeitem to remove item from order\n/vieworder to check order'
MESSAGE_JIO_EXISTS_PRIVATE = 'There is already a Supper Jio going on.'
MESSAGE_NO_JIO = 'There is no Supper Jio going on!\n\n/openjio to start a Supper Jio'
MESSAGE_NO_JIO_PRIVATE = 'There is no Supper Jio going on!'
MESSAGE_NOT_JIO_STARTER = 'Sorry, only the person who started it can close the Supper Jio!'
MESSAGE_SEND_TO_GROUP = 'Please send your commands in a group chat!'
MESSAGE_START_CHAT = 'Hi there, please start a chat with me first!'


class FlowStep(TypedDict):
    message: str
    choices: Union[list[str], list[int]]


OPEN_JIO_FLOW = [
    FlowStep(
        message='Ordering supper from which establishment?',
        choices=JIO_TYPE
    ),
    FlowStep(
        message='How long before closing the Supper Jio? (You will still need to tell me with /closejio)',
        choices=JIO_CLOSES
    ),
    FlowStep(
        message='How do you want to split the delivery fee?',
        choices=JIO_SPLIT
    ),
    FlowStep(
        message='Do you want to include 7% GST?',
        choices=JIO_GST
    )
]

BUTTON_CANCEL = InlineKeyboardButton(
    text='Cancel',
    callback_data=Command.CANCEL.value
)

KEYBOARD_START = InlineKeyboardMarkup(
    inline_keyboard=[[
        InlineKeyboardButton(text='Start chat!', url=os.environ['BOT_URL'])
    ]]
)


def open_jio(chat_id: int, user_id: int):
    jio = Jio.exists(chat_id)
    if jio:
        send_message(chat_id, MESSAGE_JIO_EXISTS)
    else:
        data_prefix = '%s_%s' % (Command.OPEN_JIO.value, chat_id)
        flow_handler(data_prefix, user_id)


def open_jio_send_messages(flow_state: list[str], user_id: int, message_id: int, first_name: str):
    chat_id = int(flow_state[1])
    type = JIO_TYPE[int(flow_state[2])]
    delivery = JIO_DELIVERY
    closes = JIO_CLOSES[int(flow_state[3])]
    split = JIO_SPLIT[int(flow_state[4])]
    gst = JIO_GST[int(flow_state[5])]
    jio = Jio.exists(chat_id)
    if jio:
        return edit_message_text(user_id, message_id, MESSAGE_JIO_EXISTS)
    else:
        Jio.create(chat_id, user_id, type, closes, split, gst, delivery)
        edit_message_text(user_id, message_id, 'Supper Jio started!')
        return send_message(
            chat_id=chat_id,
            text='*%s* has started a Supper Jio for *%s*, closing in *%s mins*. Delivery cost of $%0.2f will be *%s*, GST is *%s*.\n\n/additem to add item to order\n/removeitem to remove item from order\n/vieworder to check order' %
            (first_name, type, closes, delivery/100, split.lower(), gst.lower())
        )


def close_jio(chat_id: int, user_id: int):
    jio = Jio.exists(chat_id)
    if jio:
        if user_id == jio.starter_id:
            try:
                order_summary, user_messages = jio.close()
                send_message(chat_id, order_summary)
                for message_user_id, message in user_messages.items():
                    send_message(int(message_user_id), message)
            except Exception:
                traceback.print_exc()
                send_message(chat_id, MESSAGE_ERROR)
        else:
            send_message(chat_id, MESSAGE_NOT_JIO_STARTER)
    else:
        send_message(chat_id, MESSAGE_NO_JIO)


def add_item(chat_id: int, user_id: int):
    jio = Jio.exists(chat_id)
    if jio:
        prefix = '%s_%s' % (Command.ADD_ITEM.value, chat_id)
        flow_handler(prefix, user_id)
    else:
        send_message(chat_id, MESSAGE_NO_JIO)


def remove_item(chat_id: int, user_id: int):
    jio = Jio.exists(chat_id=chat_id)
    if jio:
        if str(user_id) in jio.orders and jio.orders[str(user_id)]['items']:
            prefix = '%s_%s' % (Command.REMOVE_ITEM.value, chat_id)
            item_names = ['%s - ($%.2f)' % (item['item'], item['price']/100)
                          for item in jio.orders[str(user_id)]['items']]
            kb = get_inline_keyboard_markup(prefix, item_names)
            if not send_message(user_id, 'Please choose an item to remove:', kb):
                send_message(chat_id, MESSAGE_START_CHAT, KEYBOARD_START)
        else:
            send_message(chat_id, 'You have no items to remove!')
    else:
        send_message(chat_id, MESSAGE_NO_JIO)


def view_order(chat_id: int, user_id: int):
    jio = Jio.exists(chat_id)
    if jio:
        send_message(chat_id, 'Items ordered:\n\n%s' % jio.get_order_summary())
    else:
        send_message(chat_id, MESSAGE_NO_JIO)


def flow_handler(data: str, user_id: int, message_id: int = 0, first_name: str = ''):
    try:
        logger.debug('flow_handler data: %s' % data)
        logger.debug('user_id: %s' % user_id)
        logger.debug('message_id: %s' % message_id)
        logger.debug('first_name: %s' % first_name)
        flow_state = data.split('_')
        command = flow_state[0]
        if command == Command.CANCEL.value:
            return edit_message_text(user_id, message_id, 'Cancelled!')
        # cancel command does not have chat_id attached
        chat_id = int(flow_state[1])
        selections = [int(i) for i in flow_state[2:]
                      ] if len(flow_state) > 2 else []
        stage = len(selections)
        if command == Command.OPEN_JIO.value:
            jio = Jio.exists(chat_id)
            if jio:
                edit_message_text(user_id, message_id,
                                  MESSAGE_JIO_EXISTS_PRIVATE)
            else:
                if stage == len(OPEN_JIO_FLOW):
                    # end of the openjio flow
                    open_jio_send_messages(
                        flow_state, user_id, message_id, first_name)
                else:
                    message = OPEN_JIO_FLOW[stage]['message']
                    choices = OPEN_JIO_FLOW[stage]['choices']
                    if stage == 0:
                        kb = get_inline_keyboard_markup(data, choices)
                        if message_id:  # user has went back to stage 0
                            edit_message_text(user_id, message_id, message, kb)
                        else:  # message_id = 0, i.e. initial openjio command
                            if not send_message(user_id, message, kb):
                                send_message(
                                    chat_id, MESSAGE_START_CHAT, KEYBOARD_START)
                    else:
                        kb = get_inline_keyboard_markup(
                            data, choices, include_back=True)
                        edit_message_text(user_id, message_id, message, kb)
        elif command == Command.ADD_ITEM.value:
            jio = Jio.exists(chat_id)
            if jio:
                choices, selection = get_menu_choices(selections)
                if stage == 0 and choices:  # initial message to add item
                    kb = get_inline_keyboard_markup(data, choices)
                    if message_id:  # user has went back to stage 0
                        edit_message_text(user_id, message_id,
                                          MESSAGE_ADD_ITEM, kb)
                    else:
                        if not send_message(user_id, MESSAGE_ADD_ITEM, kb):
                            send_message(
                                chat_id, MESSAGE_START_CHAT, KEYBOARD_START)
                else:
                    if selection:  # an item has been selected
                        item = selection[0]
                        price = selection[1]
                        if jio.add_item(user_id, first_name, item, price):
                            prefix = '%s_%s' % (
                                Command.ADD_ITEM.value, chat_id)
                            kb = InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(
                                    text='Add another item',
                                    callback_data=prefix
                                ),
                                BUTTON_CANCEL
                            ]])
                            edit_message_text(
                                user_id, message_id, 'Item added - %s ($%.2f)' % (item, price/100), kb)
                    elif choices:  # update message keyboard with menu choices
                        kb = get_inline_keyboard_markup(
                            data, choices, include_back=True)
                        edit_message_text(user_id, message_id,
                                          MESSAGE_ADD_ITEM, kb)
            else:
                edit_message_text(user_id, message_id, MESSAGE_NO_JIO_PRIVATE)
        elif command == Command.REMOVE_ITEM.value:
            index = selections[0]
            jio = Jio.exists(chat_id)
            if jio:
                if jio.remove_item(user_id, index):
                    return edit_message_text(user_id, message_id, text='Item removed!')
            else:
                edit_message_text(user_id, message_id, MESSAGE_NO_JIO_PRIVATE)
        else:
            logger.error('unhandled command: %s' % command)
            edit_message_text(user_id, message_id, MESSAGE_ERROR)
    except Exception:
        traceback.print_exc()
        edit_message_text(user_id, message_id, MESSAGE_ERROR)


def parse_command(command: str, chat_id: int, _from: User):
    user_id = _from['id']
    if command == Command.START.value:
        send_message(chat_id, MESSAGE_START_CHAT, KEYBOARD_START)
    elif command == Command.OPEN_JIO.value:
        open_jio(chat_id, user_id)
    elif command == Command.CLOSE_JIO.value:
        close_jio(chat_id, user_id)
    elif command == Command.ADD_ITEM.value:
        add_item(chat_id, user_id)
    elif command == Command.REMOVE_ITEM.value:
        remove_item(chat_id, user_id)
    elif command == Command.VIEW_ORDER.value:
        view_order(chat_id, user_id)
    else:
        send_message(user_id, MESSAGE_INVALID_COMMAND)


def parse_update(update: Update):
    if 'message' in update:
        message = update['message']
        chat_id = message['chat']['id']
        chat_title = message['chat']['title'] if 'title' in message['chat'] else chat_id
        if message['chat']['type'] == 'private':
            send_message(chat_id, MESSAGE_SEND_TO_GROUP)
        else:
            if 'entities' in message and 'from' in message and 'text' in message:
                entities = message['entities']
                _from = message['from']
                text = message['text']
                # iterate through message entities to find bot_command
                for entity in entities:
                    if entity['type'] == 'bot_command':
                        command = extract_command(text, entity)
                        logger.info('bot_command: %s' % command)
                        parse_command(command, chat_id, _from)
                        # process only one bot command
                        break
            elif 'left_chat_member' in message:
                user = message['left_chat_member']
                if user['is_bot'] and user['id'] == int(os.environ['BOT_ID']):
                    send_message(int(os.environ['BOT_OWNER']), 'Removed from chat: %s' % chat_title)
            elif 'new_chat_members' in message:
                for user in message['new_chat_members']:
                    if user['is_bot'] and user['id'] == int(os.environ['BOT_ID']):
                        send_message(int(os.environ['BOT_OWNER']), 'Added to chat: %s' % chat_title)
                        break
    elif 'callback_query' in update:
        callback_query: CallbackQuery = update['callback_query']
        if 'data' in callback_query and 'message' in callback_query and 'chat' in callback_query['message']:
            data = callback_query['data']
            message_id = callback_query['message']['message_id']
            user_id = callback_query['from']['id']
            first_name = callback_query['from']['first_name']
            flow_handler(data, user_id, message_id, first_name)


def extract_command(text: str, entity: MessageEntity) -> str:
    command = text[entity['offset']:entity['offset'] + entity['length']]
    # strip bot name and leading slash
    command = command.split('@')[0]
    command = command[1:]
    return command


def get_inline_keyboard_markup(data_prefix: str, choices: Union[list[str], list[int]], include_cancel: bool = True, include_back: bool = False) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for index, choice in enumerate(choices):
        button = InlineKeyboardButton(
            text=str(choice),
            callback_data='%s_%s' % (data_prefix, index)
        )
        buttons.append([button])
    if include_back:
        prefix_parts = data_prefix.split('_')
        if len(prefix_parts) > 2:
            button = InlineKeyboardButton(
                text='Back',
                callback_data='_'.join(prefix_parts[:-1])
            )
            buttons.append([button])
    if include_cancel:
        buttons.append([BUTTON_CANCEL])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def lambda_handler(event: dict[str, Any], context: dict[str, Any]):
    try:
        update = json.loads(event['body'])
        parse_update(update)
    except Exception:
        logger.info('Error while processing event: %s' % event)
        traceback.print_exc()
    return {
        "statusCode": 200,
        "body": None
    }
