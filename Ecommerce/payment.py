# ============================================================
#  payment.py  –  Simulated secure payment processing
# ============================================================
import re
import random
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PaymentDetails:
    card_number:  str
    card_holder:  str
    expiry:       str   # MM/YY
    cvv:          str
    billing_zip:  str


@dataclass
class PaymentResult:
    success:         bool
    transaction_id:  str
    message:         str
    timestamp:       str
    amount:          float
    last_four:       str = ""


# ── validation helpers ───────────────────────────────────────

def _luhn_check(number: str) -> bool:
    """Standard Luhn algorithm for card-number validation."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def validate_payment(details: PaymentDetails) -> tuple[bool, str]:
    """Return (is_valid, error_message). Empty error means valid."""
    # Card number
    raw = details.card_number.replace(" ", "").replace("-", "")
    if not raw.isdigit() or len(raw) not in (13, 15, 16, 19):
        return False, "Invalid card number length."
    if not _luhn_check(raw):
        return False, "Card number failed Luhn check."

    # Card holder
    if len(details.card_holder.strip()) < 2:
        return False, "Card holder name is too short."

    # Expiry MM/YY
    m = re.match(r"^(\d{1,2})/(\d{2})$", details.expiry.strip())
    if not m:
        return False, "Expiry must be MM/YY format."
    month, year = int(m.group(1)), int(m.group(2)) + 2000
    now = datetime.now()
    if month < 1 or month > 12:
        return False, "Invalid expiry month."
    if (year, month) < (now.year, now.month):
        return False, "Card has expired."

    # CVV
    if not re.match(r"^\d{3,4}$", details.cvv.strip()):
        return False, "CVV must be 3 or 4 digits."

    # Billing ZIP
    if not re.match(r"^\d{4,10}$", details.billing_zip.strip()):
        return False, "Invalid billing ZIP/postal code."

    return True, ""


# ── processor ────────────────────────────────────────────────

def _generate_txn_id(card_number: str, amount: float) -> str:
    raw = f"{card_number}{amount}{time.time()}{random.randint(0, 9999)}"
    return "TXN-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


def process_payment(details: PaymentDetails, amount: float) -> PaymentResult:
    """
    Simulated payment gateway.

    Real-world integration would call Stripe / Braintree / PayPal here.
    For demo purposes, cards ending in 0000 are declined; all others succeed.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raw       = details.card_number.replace(" ", "").replace("-", "")
    last_four = raw[-4:]
    txn_id    = _generate_txn_id(raw, amount)

    # Validate
    valid, err = validate_payment(details)
    if not valid:
        return PaymentResult(
            success=False, transaction_id="", message=err,
            timestamp=timestamp, amount=amount, last_four=last_four,
        )

    # Simulate network delay
    time.sleep(0.8)

    # Simulate declined test card (last 4 = 0000)
    if last_four == "0000":
        return PaymentResult(
            success=False, transaction_id=txn_id,
            message="Payment declined by issuing bank.",
            timestamp=timestamp, amount=amount, last_four=last_four,
        )

    # Approved
    return PaymentResult(
        success=True, transaction_id=txn_id,
        message=(f"Payment of ${amount:.2f} authorised. "
                 f"Card ending in {last_four}."),
        timestamp=timestamp, amount=amount, last_four=last_four,
    )


# ── receipt ──────────────────────────────────────────────────

def generate_receipt(result: PaymentResult, items: list, summary: dict) -> str:
    lines = [
        "=" * 52,
        "          🧾  PURCHASE RECEIPT",
        "=" * 52,
        f"Transaction ID : {result.transaction_id}",
        f"Date & Time    : {result.timestamp}",
        f"Card Ending    : **** **** **** {result.last_four}",
        "-" * 52,
        f"{'ITEM':<30} {'QTY':>4} {'PRICE':>8}",
        "-" * 52,
    ]
    for item in items:
        lines.append(
            f"{item.product.name:<30} {item.quantity:>4}  "
            f"${item.subtotal:>7.2f}"
        )
    lines += [
        "-" * 52,
        f"{'Subtotal':<40} ${summary['subtotal']:>7.2f}",
    ]
    if summary["discount_amount"] > 0:
        pct = int(summary["discount_pct"] * 100)
        lines.append(
            f"{'Discount (' + summary['coupon_code'] + ' –' + str(pct) + '%)':<40}"
            f" -${summary['discount_amount']:>6.2f}"
        )
    lines += [
        f"{'Shipping':<40} ${summary['shipping']:>7.2f}",
        f"{'Tax (8%)':<40} ${summary['tax']:>7.2f}",
        "=" * 52,
        f"{'TOTAL':<40} ${summary['total']:>7.2f}",
        "=" * 52,
        "   Thank you for shopping with PyStore! 🛍️",
        "=" * 52,
    ]
    return "\n".join(lines)
