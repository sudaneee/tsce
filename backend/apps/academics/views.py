from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Certificate


class CertificateVerifyView(APIView):
    """
    Public certificate check (verify.html): GET /api/certificates/verify?no=TSCE/CERT/2026/00001
    Only the details printed on the certificate itself are disclosed.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "verify"

    def get(self, request):
        number = (request.query_params.get("no") or "").strip()
        cert = (
            Certificate.objects.select_related("enrollment__student", "enrollment__programme", "enrollment__cohort")
            .filter(number__iexact=number).first() if number else None
        )
        if cert is None:
            return Response({"status": "not_found", "number": number})
        if cert.status == Certificate.Status.REVOKED:
            return Response({"status": "revoked", "number": cert.number})
        e = cert.enrollment
        return Response({
            "status": "valid",
            "number": cert.number,
            "holder": e.student.full_name,
            "programme": e.programme.name,
            "cohort": e.cohort.name,
            "issuedAt": cert.issued_at,
        })
