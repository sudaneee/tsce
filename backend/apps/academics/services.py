"""
Academic rules in one place: attendance rate, results summary and certificate
eligibility. Used by the student portal (and by the staff academics tools).
"""
from dataclasses import dataclass, field

from .grading import grade_for
from .models import AttendanceRecord, Certificate, Enrollment, Result

MIN_ATTENDANCE_PCT = 75
PASS_AVERAGE = 50


@dataclass
class AttendanceSummary:
    records: list = field(default_factory=list)
    present: int = 0
    late: int = 0
    absent: int = 0

    @property
    def total(self) -> int:
        return len(self.records)

    @property
    def rate(self) -> int:
        """Present and late both count as attended."""
        return round((self.present + self.late) / self.total * 100) if self.total else 0


def attendance(enrollment: Enrollment) -> AttendanceSummary:
    recs = list(enrollment.attendance.select_related("session__module").order_by("session__date"))
    s = AttendanceSummary(records=recs)
    for r in recs:
        if r.status == AttendanceRecord.Status.PRESENT:
            s.present += 1
        elif r.status == AttendanceRecord.Status.LATE:
            s.late += 1
        else:
            s.absent += 1
    return s


@dataclass
class ResultsSummary:
    records: list
    withheld: bool          # fees not cleared: the student can't see scores yet

    @property
    def average(self) -> int:
        return round(sum(r.score for r in self.records) / len(self.records)) if self.records else 0

    @property
    def grade(self) -> str:
        return grade_for(self.average) if self.records else "—"

    @property
    def best(self):
        return max(self.records, key=lambda r: r.score, default=None)


def results(enrollment: Enrollment) -> ResultsSummary:
    """Published results only; withheld from the student until the programme fee is paid in full."""
    recs = list(enrollment.results.filter(status=Result.Status.PUBLISHED).select_related("module").order_by("assessed_on", "module__order"))
    return ResultsSummary(records=recs, withheld=not enrollment.fees_cleared)


@dataclass
class Check:
    label: str
    ok: bool
    value: str


def certificate_status(enrollment: Enrollment) -> dict:
    """{'state': Issued | Revoked | Eligible | In Progress, 'checks': [...], 'certificate': … or None}"""
    try:
        cert = enrollment.certificate
    except Certificate.DoesNotExist:
        cert = None
    att, res = attendance(enrollment), results(enrollment)
    app = enrollment.application
    checks = [
        Check("All modules completed", enrollment.progress >= 100, f"{enrollment.progress}%"),
        Check(f"Attendance of at least {MIN_ATTENDANCE_PCT}%", att.total > 0 and att.rate >= MIN_ATTENDANCE_PCT, f"{att.rate}%"),
        Check(f"Assessment average of {PASS_AVERAGE}% or more", bool(res.records) and res.average >= PASS_AVERAGE,
              f"{res.average}%" if res.records else "—"),
        Check("Programme fees fully paid", enrollment.fees_cleared, app.payment_status),
    ]
    if cert and cert.status == Certificate.Status.ISSUED and enrollment.fees_cleared:
        state = "Issued"
    elif cert and cert.status == Certificate.Status.REVOKED:
        state = "Revoked"
    else:
        state = "Eligible" if all(c.ok for c in checks) else "In Progress"
    return {"state": state, "checks": checks, "certificate": cert if state == "Issued" else None}
