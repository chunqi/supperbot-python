import decimal
import itertools
import math
import os
import time
from collections import Counter
from typing import List, Literal, Tuple, TypedDict

import boto3
from boto3.dynamodb.conditions import Attr, Key

from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource

DYNAMODB_RESOURCE: DynamoDBServiceResource = boto3.resource('dynamodb')
TABLE = DYNAMODB_RESOURCE.Table(os.environ['TABLE_NAME'])


class ItemTypeDef(TypedDict):
    item: str
    price: int


class OrderListTypeDef(TypedDict):
    firstname: str
    items: List[ItemTypeDef]


class JioTypeDef(TypedDict):
    chat_id: int
    timestamp: int
    starter_id: int
    status: Literal['Open', 'Closed']
    type: Literal['Al Amaan']
    closes: Literal[15, 30, 45, 60, 90]
    split: Literal['Split Equally', 'Weighted', 'Free']
    gst: Literal['Included', 'Not Included']
    delivery: int
    orders: dict[str, OrderListTypeDef]


JIO_TYPE: List[str] = JioTypeDef.__annotations__['type'].__args__
JIO_CLOSES: List[int] = JioTypeDef.__annotations__['closes'].__args__
JIO_SPLIT: List[str] = JioTypeDef.__annotations__['split'].__args__
JIO_GST: List[str] = JioTypeDef.__annotations__['gst'].__args__
JIO_DELIVERY = 300
GST_RATE = decimal.Decimal(0.07)


class Jio:
    @staticmethod
    def exists(chat_id: int):
        time_window = int(time.time()) - (4 * 60 * 60)
        response = TABLE.query(
            Select='ALL_ATTRIBUTES',
            ConsistentRead=True,
            KeyConditionExpression=Key('chat_id').eq(
                chat_id) & Key('timestamp').gt(time_window),
            FilterExpression=Attr('status').eq('Open')
        )
        if response['Count']:
            jio = response['Items'][0]
            timestamp = jio['timestamp']
            starter_id = jio['starter_id']
            type = jio['type']
            closes = jio['closes']
            split = jio['split']
            gst = jio['gst']
            delivery = jio['delivery']
            orders = jio['orders']
            return Jio(chat_id, timestamp, starter_id, type, closes, split, gst, delivery, orders)
        return None

    @staticmethod
    def create(chat_id: int, starter_id: int, type: str, closes: int, split: str, gst: str, delivery: int) -> bool:
        if Jio.exists(chat_id):
            return False
        else:
            TABLE.put_item(Item={
                'chat_id': chat_id,
                'timestamp': int(time.time()),
                'starter_id': starter_id,
                'status': 'Open',
                'type': type,
                'closes': closes,
                'split': split,
                'gst': gst,
                'delivery': delivery,
                'orders': {}
            })
            return True

    def __init__(self, chat_id: int, timestamp: int, starter_id: int, type: str, closes: int, split: str, gst: str, delivery: int, orders: dict[str, OrderListTypeDef]):
        self.chat_id = chat_id
        self.timestamp = timestamp
        self.starter_id = starter_id
        self.type = type
        self.closes = closes
        self.split = split
        self.gst = gst
        self.delivery = delivery
        self.orders = orders

    def __repr__(self):
        return '<%d, %d, %d, %s, %d, %s, %s, %d>' % (
            self.chat_id,
            self.timestamp,
            self.starter_id,
            self.type,
            self.closes,
            self.split,
            self.gst,
            self.delivery
        )

    def _close(self) -> bool:
        response = TABLE.update_item(
            Key={
                'chat_id': self.chat_id,
                'timestamp': self.timestamp
            },
            UpdateExpression='SET #s = :status',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':status': 'Closed'}
        )
        return response['ResponseMetadata']['HTTPStatusCode'] == 200

    def close(self) -> Tuple[str, dict[str, str]]:
        order_summary: List[str] = []
        user_messages: dict[str, str] = {}
        # combine all orders into single list
        all_items = list(itertools.chain.from_iterable(
            [order['items'] for order in self.orders.values()]))
        if len(all_items) == 0:
            order_summary.append('Jio is closed! There were no items ordered.')
        else:
            order_summary.append(
                'Jio is closed! Here are the items ordered:\n')
            # count quantity ordered for each item
            all_items = [(item['item'], item['price']) for item in all_items]
            for item, count in Counter(all_items).items():
                order_summary.append('%s x %d' % (item[0], count))
            order_summary.append(
                '\nPlease pay per person total:\n')
            # calculate order totals for each user, exclude users with no items
            user_total: dict[str, int] = {}
            user_gst: dict[str, int] = {}
            user_delivery: dict[str, int] = {}
            for user_id, user_order in self.orders.items():
                if len(user_order['items']) == 0:
                    continue
                user_total[user_id] = sum([item['price']
                                          for item in user_order['items']])
                # calculate gst if included
                if self.gst == JIO_GST[0]:  # Included
                    user_gst[user_id] = math.ceil(
                        user_total[user_id] * GST_RATE)
                else:
                    user_gst[user_id] = 0
            grand_total = sum(user_total.values())
            # calculate delivery fee for each user
            for user_id, user_order in self.orders.items():
                if len(user_order['items']) == 0:
                    continue
                if self.split == JIO_SPLIT[0]:  # Split Equally
                    user_delivery[user_id] = math.ceil(
                        self.delivery / len(user_total))
                elif self.split == JIO_SPLIT[1]:  # Weighted
                    user_delivery[user_id] = math.ceil(
                        self.delivery * (user_total[user_id] / grand_total))
                elif self.split == JIO_SPLIT[2]: # Free
                    user_delivery[user_id] = 0
                user_grand_total = sum([
                    user_total[user_id],
                    user_delivery[user_id],
                    user_gst[user_id]
                ])
                user_order_summary = '%s - $%.2f' % (user_order['firstname'], user_grand_total/100)
                user_inclusion_string = ''
                user_inclusions: list[str] = []
                if self.split != JIO_SPLIT[2]: # not=Free
                    user_inclusions.append('$%.2f delivery' % (user_delivery[user_id]/100))
                if self.gst == JIO_GST[0]:
                    user_inclusions.append('$%.2f GST' % (user_gst[user_id]/100))
                if user_inclusions:
                    user_inclusion_string = ' (incl. %s)' % (' & '.join(user_inclusions))
                order_summary.append('%s%s' % (user_order_summary, user_inclusion_string))
                user_messages[user_id] = 'Your food order costs *$%.2f* in total%s' % (
                    user_grand_total/100,
                    user_inclusion_string
                )
            # grand total is user_total sum, plus GST if included and delivery fee
            grand_total_gst = grand_total * GST_RATE
            if self.gst == JIO_GST[0]:  # Included
                grand_total += grand_total_gst
            grand_total += self.delivery
            grand_total_summary = '\n*Grand Total* - $%.2f' % (grand_total/100)
            if self.gst == JIO_GST[0]: # Included
                grand_total_summary += ' (GST $%.2f %s)' % (grand_total_gst/100, JIO_GST[0].lower())
            else:
                grand_total_summary += ' (GST %s)' % (JIO_GST[1].lower())
            order_summary.append(grand_total_summary)
        # close the jio
        if self._close():
            return '\n'.join(order_summary), user_messages
        else:
            raise Exception('dynamodb.update_item() returned status code is not 200')

    def add_item(self, user_id: int, firstname: str, item: str, price: int) -> bool:
        order_item = ItemTypeDef(item=item, price=price)
        if str(user_id) in self.orders:
            response = TABLE.update_item(
                Key={
                    'chat_id': self.chat_id,
                    'timestamp': self.timestamp
                },
                UpdateExpression='SET #ord.#usr.#itm = list_append(#ord.#usr.#itm, :order)',
                ExpressionAttributeNames={
                    '#ord': 'orders',
                    '#usr': str(user_id),
                    '#itm': 'items'
                },
                ExpressionAttributeValues={':order': [order_item]}
            )
        else:
            response = TABLE.update_item(
                Key={
                    'chat_id': self.chat_id,
                    'timestamp': self.timestamp
                },
                UpdateExpression='SET #ord.#usr = :order',
                ExpressionAttributeNames={
                    '#ord': 'orders',
                    '#usr': str(user_id)
                },
                ExpressionAttributeValues={
                    ':order': {
                        'firstname': firstname,
                        'items': [order_item]
                    }
                }
            )
        return response['ResponseMetadata']['HTTPStatusCode'] == 200

    def remove_item(self, user_id: int, index: int) -> bool:
        if str(user_id) in self.orders:
            user_items: OrderListTypeDef = self.orders[str(user_id)]
            if index < len(user_items['items']):
                response = TABLE.update_item(
                    Key={
                        'chat_id': self.chat_id,
                        'timestamp': self.timestamp
                    },
                    UpdateExpression='REMOVE #ord.#usr.#itm[%d]' % index,
                    ExpressionAttributeNames={
                        '#ord': 'orders',
                        '#usr': str(user_id),
                        '#itm': 'items'
                    }
                )
                return response['ResponseMetadata']['HTTPStatusCode'] == 200
        return False

    def get_order_summary(self) -> str:
        order_strings: List[str] = []
        for user_order in self.orders.values():
            firstname = user_order['firstname']
            if len(user_order['items']) == 0:
                continue
            items = [(item['item'], item['price'])
                     for item in user_order['items']]
            for item, count in Counter(items).items():
                order_strings.append('%s - %s x %d' %
                                     (firstname, item[0], count))
        if order_strings:
            return '\n'.join(order_strings)
        else:
            return 'None so far'
