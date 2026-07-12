from telegram import ReplyKeyboardMarkup
from config import (
    MAIN_MENU, BTN_KEUANGAN, BTN_CATAT, BTN_HUTANG, BTN_TARGET, BTN_AI, BTN_ADD, BTN_HISTORY, BTN_REPORT, BTN_SETTINGS, BTN_BACK,
    BTN_INCOME, BTN_EXPENSE, BTN_SKIP_NOTE, BTN_TODAY, BTN_CUSTOM_DATE,
    BTN_SAVE, BTN_EDIT, BTN_CANCEL,
    BTN_PERIOD_TODAY, BTN_PERIOD_WEEK, BTN_PERIOD_MONTH, BTN_PERIOD_ALL, BTN_PERIOD_SEARCH,
    BTN_REPORT_1M, BTN_REPORT_2M, BTN_REPORT_3M, BTN_REPORT_6M, BTN_REPORT_9M, BTN_REPORT_1Y,
    BTN_SET_BALANCE, BTN_RESET, BTN_EXPORT, BTN_IMPORT, BTN_DELETE_CONFIRM, BTN_DELETE_CANCEL,
    BTN_EDIT_AMOUNT, BTN_EDIT_CATEGORY, BTN_EDIT_NOTE, BTN_EDIT_DATE, BTN_EDIT_TYPE, BTN_EDIT_SAVE, BTN_EDIT_ABORT,
)

def kb(rows):
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

def main_menu():
    return kb([
        [BTN_KEUANGAN],
        [BTN_AI],
    ])

def keuangan_gate():
    return kb([
        [BTN_CATAT, BTN_TARGET],
        [BTN_HUTANG],
        [BTN_BACK],
    ])
def catat_dashboard():
    return kb([
        [BTN_ADD],
        [BTN_HISTORY, BTN_REPORT],
        [BTN_SETTINGS],
        [BTN_BACK],
    ])

def add_type():
    return kb([[BTN_INCOME, BTN_EXPENSE], [BTN_BACK]])

def note_keyboard():
    return kb([[BTN_SKIP_NOTE], [BTN_BACK]])

def date_keyboard():
    return kb([[BTN_TODAY, BTN_CUSTOM_DATE], [BTN_BACK]])

def confirm_keyboard():
    return kb([[BTN_SAVE, BTN_EDIT], [BTN_CANCEL]])

def history_period_keyboard():
    return kb([
        [BTN_PERIOD_TODAY, BTN_PERIOD_WEEK],
        [BTN_PERIOD_MONTH, BTN_PERIOD_ALL],
        [BTN_PERIOD_SEARCH],
        [BTN_BACK],
    ])

def report_period_keyboard():
    return kb([
        [BTN_REPORT_1M, BTN_REPORT_2M],
        [BTN_REPORT_3M, BTN_REPORT_6M],
        [BTN_REPORT_9M, BTN_REPORT_1Y],
        [BTN_BACK],
    ])

def settings_keyboard():
    return kb([
        [BTN_SET_BALANCE],
        [BTN_EXPORT, BTN_IMPORT],
        [BTN_RESET],
        [BTN_BACK],
    ])

def delete_confirm_keyboard():
    return kb([[BTN_DELETE_CONFIRM, BTN_DELETE_CANCEL]])

def edit_menu_keyboard():
    return kb([
        [BTN_EDIT_AMOUNT, BTN_EDIT_CATEGORY],
        [BTN_EDIT_NOTE, BTN_EDIT_DATE],
        [BTN_EDIT_TYPE],
        [BTN_EDIT_SAVE],
        [BTN_EDIT_ABORT],
    ])

def categories_keyboard(categories):
    rows = []
    row = []
    for idx, c in enumerate(categories, 1):
        row.append(f"{c.get('emoji','')} {c['nama']}".strip())
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([BTN_BACK])
    return kb(rows)

def edit_type_keyboard():
    return kb([[BTN_INCOME, BTN_EXPENSE], [BTN_BACK]])
