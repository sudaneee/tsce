"""Staff-side queries over payments: filters, duplicate flag, money totals."""
from django.db.models import Q, Sum

from .models import Payment


def filter_payments(p):
    """Staff payment filters (?status=&purpose=&kind=&q=) → queryset, newest first."""
    qs = Payment.objects.select_related("application__programme", "application__enrollment__student", "parent")
    for key in ("status", "purpose", "kind"):
        if p.get(key):
            qs = qs.filter(**{key: p[key]})
    if p.get("q"):
        q = p["q"].strip()
        qs = qs.filter(Q(reference__icontains=q) | Q(name__icontains=q) | Q(email__icontains=q)
                       | Q(application__number__icontains=q))
    return qs.order_by("-created_at")


def is_duplicate_row(payment, counted) -> bool:
    return (payment.kind == Payment.Kind.CHARGE and payment.status == Payment.Status.SUCCESS
            and payment.application_id is not None and payment.pk not in counted)


def payments_summary(counted) -> dict:
    charges = Payment.objects.filter(kind=Payment.Kind.CHARGE)
    total = lambda **f: charges.filter(**f).aggregate(t=Sum("amount"))["t"] or 0  # noqa: E731
    paid = [Payment.Status.SUCCESS, Payment.Status.REFUNDED]
    return {
        "collected": total(status__in=paid),
        "applicationFees": total(status__in=paid, purpose=Payment.Purpose.APPLICATION_FEE),
        "programmeFees": total(status__in=paid, purpose=Payment.Purpose.PROGRAMME_FEE),
        "refunded": Payment.objects.filter(kind=Payment.Kind.REFUND).aggregate(t=Sum("amount"))["t"] or 0,
        "pending": charges.filter(status=Payment.Status.PENDING).count(),
        "failed": charges.filter(status=Payment.Status.FAILED).count(),
        "duplicates": charges.filter(status=Payment.Status.SUCCESS, application__isnull=False).exclude(id__in=counted).count(),
    }
