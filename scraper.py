"""
سكريبت يجمع أسعار العملات في السودان (الرسمي وغير الرسمي/السوق الموازي)
من موقع alsoug.com كل مرة يتم تشغيله، ويضيف لقطة (snapshot) جديدة
إلى data/history.json مع وقت التحديث.

يتم تشغيله تلقائيًا كل ساعة عبر GitHub Actions (انظر .github/workflows/update-rates.yml).
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.alsoug.com/en/currency"
HISTORY_PATH = Path(__file__).parent / "data" / "history.json"
MAX_ENTRIES = 24 * 90  # الاحتفاظ بحوالي 90 يومًا من القراءات الساعية

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en,ar;q=0.9",
}

# مطابقة كلمات مفتاحية (بحروف صغيرة) من اسم العملة في الصفحة إلى رمز العملة.
# عدّل/أضف هنا إن غيّر الموقع طريقة كتابة الاسم.
NAME_MAP = [
    ("dollar", "USD"),
    ("euro", "EUR"),
    ("saudi", "SAR"),
    ("qatari", "QAR"),
    ("emirati", "AED"),
    ("egyptian", "EGP"),
]


def first_number(text: str):
    """يستخرج أول رقم عشري/صحيح من نص الخلية (يتجاهل رموز الأسهم والنصوص الأخرى)."""
    match = re.search(r"\d[\d,]*\.?\d*", text)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def scrape_rates() -> dict:
    resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rates = {}
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        name_text = cells[0].get_text(" ", strip=True).lower()
        code = next((c for key, c in NAME_MAP if key in name_text), None)
        if not code:
            continue
        official = first_number(cells[1].get_text(" ", strip=True))
        unofficial = first_number(cells[2].get_text(" ", strip=True))
        if official is None and unofficial is None:
            continue
        rates[code] = {"official": official, "unofficial": unofficial}

    if not rates:
        raise RuntimeError(
            "لم يتم العثور على صفوف عملات مطابقة — يبدو أن بنية صفحة المصدر تغيّرت. "
            "افتح SOURCE_URL يدويًا وحدّث NAME_MAP أو منطق التحليل."
        )
    return rates


def load_history() -> list:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return []


def save_history(history: list) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    try:
        rates = scrape_rates()
    except Exception as exc:  # noqa: BLE001
        print(f"فشل الجمع: {exc}", file=sys.stderr)
        return 1

    history = load_history()
    history.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rates": rates,
        }
    )
    history = history[-MAX_ENTRIES:]
    save_history(history)
    print(f"تم حفظ {len(rates)} عملة بتاريخ {history[-1]['timestamp']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
