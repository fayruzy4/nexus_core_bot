from __future__ import annotations

import os
import tempfile
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Optional

import matplotlib.pyplot as plt

def _save(fig) -> str:
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    fig.savefig(path, bbox_inches="tight", dpi=160)
    plt.close(fig)
    return path

def _expense_by_category(rows: List[Dict]) -> Dict[str, int]:
    totals = defaultdict(int)
    for r in rows:
        if r["jenis"] == "pengeluaran":
            totals[r["kategori"]] += int(r["nominal"])
    return dict(totals)

def create_pie_chart(rows: List[Dict], title: str) -> Optional[str]:
    data = _expense_by_category(rows)
    if not data:
        return None
    labels = list(data.keys())
    values = list(data.values())
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.set_title(title)
    return _save(fig)

def create_bar_chart(rows: List[Dict], title: str) -> Optional[str]:
    data = _expense_by_category(rows)
    if not data:
        data = {}
        for r in rows:
            if r["jenis"] == "pemasukan":
                data[r["kategori"]] = data.get(r["kategori"], 0) + int(r["nominal"])
    if not data:
        return None
    labels = list(data.keys())
    values = list(data.values())
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(labels, values)
    ax.set_title(title)
    ax.set_ylabel("Rupiah")
    ax.tick_params(axis="x", rotation=20)
    return _save(fig)

def create_line_chart(rows: List[Dict], title: str) -> Optional[str]:
    if not rows:
        return None
    grouped = {}
    for r in rows:
        d = r["tanggal_transaksi"]
        grouped.setdefault(d, {"pemasukan": 0, "pengeluaran": 0})
        grouped[d][r["jenis"]] += int(r["nominal"])
    dates = sorted(grouped.keys())
    income = [grouped[d]["pemasukan"] for d in dates]
    expense = [grouped[d]["pengeluaran"] for d in dates]
    labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m") for d in dates]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(labels, income, marker="o", label="Pemasukan")
    ax.plot(labels, expense, marker="o", label="Pengeluaran")
    ax.set_title(title)
    ax.set_ylabel("Rupiah")
    ax.legend()
    ax.tick_params(axis="x", rotation=25)
    return _save(fig)

def create_area_chart(rows: List[Dict], title: str) -> Optional[str]:
    if not rows:
        return None
    grouped = {}
    for r in rows:
        d = r["tanggal_transaksi"]
        grouped.setdefault(d, 0)
        grouped[d] += int(r["nominal"]) if r["jenis"] == "pemasukan" else -int(r["nominal"])
    dates = sorted(grouped.keys())
    running = []
    total = 0
    for d in dates:
        total += grouped[d]
        running.append(total)
    labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m") for d in dates]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.fill_between(labels, running, alpha=0.3)
    ax.plot(labels, running)
    ax.set_title(title)
    ax.set_ylabel("Saldo Bersih")
    ax.tick_params(axis="x", rotation=25)
    return _save(fig)
