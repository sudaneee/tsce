"""
Safety net for payments whose callback and webhook never arrived (closed tab,
network blip): asks the gateway about every unconfirmed payment in the
lookback window and records the answer.

    python manage.py reconcile_payments

Cron (every 5 minutes, as Zainpay recommends):
    */5 * * * * cd /srv/tsce/backend && .venv/bin/python manage.py reconcile_payments >> /var/log/tsce/reconcile.log 2>&1
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.payments import services
from apps.payments.gateways import GatewayError
from apps.payments.models import Payment


class Command(BaseCommand):
    help = "Re-verify unconfirmed (PENDING/FAILED) gateway payments."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=settings.ZAINPAY["RECONCILE_LOOKBACK_HOURS"])
        qs = (Payment.objects.filter(kind=Payment.Kind.CHARGE, status=Payment.Status.PENDING,
                                     gateway__in=["zainpay", "simulator"], created_at__gte=cutoff)
              .exclude(checkout_url=""))
        counts = {"SUCCESS": 0, "FAILED": 0, "PENDING": 0, "errors": 0}
        for payment in qs.iterator():
            try:
                status = services.process_payment(payment).status
                counts[status if status in counts else "PENDING"] += 1
                if status == Payment.Status.SUCCESS:
                    self.stdout.write(self.style.SUCCESS(f"CONFIRMED {payment.reference}"))
            except GatewayError as exc:
                counts["errors"] += 1
                self.stderr.write(f"{payment.reference}: {exc}")
        self.stdout.write(f"{timezone.now():%Y-%m-%d %H:%M:%S} reconcile: confirmed={counts['SUCCESS']} "
                          f"failed={counts['FAILED']} still_pending={counts['PENDING']} errors={counts['errors']}")
