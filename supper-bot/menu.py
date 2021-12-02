import json

from collections import OrderedDict
from typing import Any, Union

MENU = json.load(open('menus/al_amaan.json', 'r'), object_pairs_hook=OrderedDict)


def get_menu_choices(selections: list[int]):
    # start from the menu root
    menu_pointer: Union[dict[str, Any], int] = MENU
    last_key = ''
    while len(selections):
        index = selections.pop(0)
        if isinstance(menu_pointer, dict):
            last_key = list(menu_pointer.keys())[index]
            menu_pointer: Union[dict[str, Any], int] = menu_pointer[last_key]
        else:  # reached a leaf item of type int
            return None, (last_key, menu_pointer)
    # return list of menu choices
    if isinstance(menu_pointer, dict):
        item_names = list(menu_pointer.keys())
        item_names = ['%s - ($%.2f)' % (item_name, menu_pointer[item_name]/100) if isinstance(
            menu_pointer[item_name], int) else item_name for item_name in item_names]
        return item_names, None
    else:
        return None, (last_key, menu_pointer)
