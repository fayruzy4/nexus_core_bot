import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

MAIN_MENU = "🏠 Menu Utama"
BTN_KEUANGAN = "💰 Keuangan"
BTN_CATAT = "📝 Catat Keuangan"
BTN_HUTANG = "💳 Catat Hutang"

BTN_DEBT_PERSON = "👤 Hutang Perorangan"
BTN_DEBT_COMPANY = "🏦 Hutang Lembaga / Pinjol"

BTN_PERSON_ADD = "➕ Tambah Hutang"
BTN_PERSON_HISTORY = "📜 Riwayat Hutang"

BTN_COMPANY_ADD = "➕ Tambah Pinjaman"
BTN_COMPANY_LIST = "📂 Daftar Pinjaman"

BTN_MARK_PAID = "✅ Tandai Lunas"
BTN_DEBT_DELETE = "🗑 Hapus"
BTN_YES = "✅ Ya"
BTN_COUNT_OTHER = "✍️ Lainnya"


BTN_ADD = "➕ Tambah Transaksi"
BTN_HISTORY = "📜 Riwayat Transaksi"
BTN_REPORT = "📊 Laporan & Analisis"
BTN_SETTINGS = "⚙️ Pengaturan"
BTN_BACK = "⬅️ Kembali"

BTN_INCOME = "💵 Pemasukan"
BTN_EXPENSE = "💸 Pengeluaran"
BTN_SKIP_NOTE = "Lewati"
BTN_TODAY = "📅 Hari Ini"
BTN_CUSTOM_DATE = "✍️ Tulis Tanggal"

BTN_SAVE = "✅ Simpan"
BTN_EDIT = "✏️ Ubah"
BTN_CANCEL = "❌ Batal"

BTN_PERIOD_TODAY = "📅 Hari Ini"
BTN_PERIOD_WEEK = "📅 Minggu Ini"
BTN_PERIOD_MONTH = "📅 Bulan Ini"
BTN_PERIOD_ALL = "📅 Semua"
BTN_PERIOD_SEARCH = "🔍 Cari"

BTN_REPORT_1M = "📅 1 Bulan"
BTN_REPORT_2M = "📅 2 Bulan"
BTN_REPORT_3M = "📅 3 Bulan"
BTN_REPORT_6M = "📅 6 Bulan"
BTN_REPORT_9M = "📅 9 Bulan"
BTN_REPORT_1Y = "📅 1 Tahun"

BTN_SET_BALANCE = "💰 Atur Saldo Awal"
BTN_RESET = "🗑 Reset Data"
BTN_EXPORT = "📤 Export Data"
BTN_IMPORT = "📥 Import Data"
BTN_DELETE_CONFIRM = "✅ HAPUS SEMUA"
BTN_DELETE_CANCEL = "❌ BATAL"

BTN_EDIT_AMOUNT = "💵 Nominal"
BTN_EDIT_CATEGORY = "🏷 Kategori"
BTN_EDIT_NOTE = "📝 Catatan"
BTN_EDIT_DATE = "📅 Tanggal"
BTN_EDIT_TYPE = "🔁 Jenis"
BTN_EDIT_SAVE = "💾 Simpan"
BTN_EDIT_ABORT = "❌ Batal"

INCOME_CATEGORIES = [
    ("💼", "Gaji"),
    ("🧑‍💻", "Freelance"),
    ("🎁", "Hadiah"),
    ("📈", "Investasi"),
    ("🧾", "Refund"),
    ("➕", "Lainnya"),
]

EXPENSE_CATEGORIES = [
    ("🍜", "Makan"),
    ("🚗", "Transport"),
    ("🛒", "Belanja"),
    ("🎮", "Hiburan"),
    ("📄", "Tagihan"),
    ("📦", "Lainnya"),
]
