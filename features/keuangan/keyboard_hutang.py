from __future__ import annotations

from typing import Iterable, List, Sequence

from telegram import ReplyKeyboardMarkup

from config import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_SAVE,
    BTN_SKIP_NOTE,
    BTN_DELETE_CONFIRM,
    BTN_DELETE_CANCEL,
    BTN_YES,
    BTN_HUTANG,
    BTN_DEBT_PERSON,
    BTN_DEBT_COMPANY,
    BTN_PERSON_ADD,
    BTN_PERSON_HISTORY,
    BTN_COMPANY_ADD,
    BTN_COMPANY_LIST,
    BTN_MARK_PAID,
    BTN_DEBT_DELETE,
    BTN_COUNT_OTHER,
)


def kb(rows: Sequence[Sequence[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)


def root_keyboard() -> ReplyKeyboardMarkup:
    return kb([
        [BTN_DEBT_PERSON],
        [BTN_DEBT_COMPANY],
        [BTN_BACK],
    ])


def person_dashboard_keyboard() -> ReplyKeyboardMarkup:
    return kb([
        [BTN_PERSON_ADD],
        [BTN_PERSON_HISTORY],
        [BTN_BACK],
    ])


def company_dashboard_keyboard() -> ReplyKeyboardMarkup:
    return kb([
        [BTN_COMPANY_ADD],
        [BTN_COMPANY_LIST],
        [BTN_BACK],
    ])


def add_cancel_keyboard() -> ReplyKeyboardMarkup:
    return kb([[BTN_CANCEL], [BTN_BACK]])


def note_keyboard() -> ReplyKeyboardMarkup:
    return kb([[BTN_SKIP_NOTE], [BTN_BACK]])


def save_cancel_keyboard() -> ReplyKeyboardMarkup:
    return kb([[BTN_SAVE, BTN_CANCEL], [BTN_BACK]])


def yes_cancel_keyboard() -> ReplyKeyboardMarkup:
    return kb([[BTN_YES, BTN_CANCEL], [BTN_BACK]])


def delete_keyboard() -> ReplyKeyboardMarkup:
    return kb([[BTN_DELETE_CONFIRM, BTN_DELETE_CANCEL], [BTN_BACK]])


def count_keyboard() -> ReplyKeyboardMarkup:
    return kb([
        ["1x", "2x", "3x", "4x"],
        ["5x", "6x", "8x", "10x"],
        ["12x", BTN_COUNT_OTHER],
        [BTN_BACK],
    ])


def person_detail_keyboard() -> ReplyKeyboardMarkup:
    return kb([
        [BTN_MARK_PAID, BTN_DEBT_DELETE],
        [BTN_BACK],
    ])


def company_detail_keyboard(installment_labels: Sequence[str]) -> ReplyKeyboardMarkup:
    rows: List[List[str]] = [[label] for label in installment_labels]
    rows.append([BTN_DEBT_DELETE])
    rows.append([BTN_BACK])
    return kb(rows)


def list_keyboard(labels: Sequence[str]) -> ReplyKeyboardMarkup:
    rows: List[List[str]] = [[label] for label in labels]
    rows.append([BTN_BACK])
    return kb(rows)
