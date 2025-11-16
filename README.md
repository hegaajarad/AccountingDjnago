PrimEx Accounting System — Django MVP

Overview
PrimEx is a lightweight Django project for managing customer cash boxes with deposits/withdrawals, multi‑currency balances, printable PDF reports, and bilingual UI (English/Arabic).

What’s included
- Django 5.1 project (primex) with a cashbox app
- Models: Customer, Currency, AccountType, CashBox, Transaction
- Per‑currency decimal precision and signed balance calculations
- Admin for fast data entry
- Simple Bootstrap UI with i18n (en/ar)
- PDF export of customer reports (xhtml2pdf)
- Basic tests for arithmetic and PDF endpoint

Prerequisites
- Python 3.11+ (3.12 recommended)
- pip
No external services are required; SQLite is used by default.

Quick start (Windows)
1) Create and activate a virtual environment
   - python -m venv .venv
   - .venv\Scripts\activate

2) Install dependencies
   - pip install -r requirements.txt

3) Initialize the database
   - python manage.py makemigrations
   - python manage.py migrate
   - python manage.py createsuperuser   # follow prompts

4) Run the server
   - python manage.py runserver

Open http://127.0.0.1:8000/ for the app and http://127.0.0.1:8000/admin/ for the admin.

Quick usage
1) In Admin, create Currencies (e.g., USD:2, USDT:6, ILS:2, EGP:2) and Account Types (e.g., BOP, CASH, WALLET).
2) Create a Customer from the UI (Home → Add Customer).
3) Create Cash Boxes for that customer (choose currency and account type).
4) Add Transactions (Deposit/Withdraw) with amount and note.
5) View the Customer Report for per‑currency totals and per‑box balances.
6) Export reports to PDF:
   - Customer summary PDF from the customer page (Export PDF button).
   - Full transactions PDF for a specific cash box from either the customer page (per‑box Export PDF) or the cash box transactions page.

Internationalization
- Language switcher is available in the navbar (English/العربية).
- To localize additional strings, add translations under /locale and run:
  - django-admin makemessages -l ar
  - django-admin compilemessages

Running tests
- python manage.py test

Notes
- PDF rendering uses xhtml2pdf (pure Python); it should work on Windows without extra system packages.
- For production, configure a proper SECRET_KEY, DEBUG=False, ALLOWED_HOSTS, and a production database (e.g., PostgreSQL).


