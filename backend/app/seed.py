import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Employee


def seed_employees(db: Session) -> int:
    seed_dir = settings.resolve_path(settings.submissions_seed_dir)
    if not seed_dir.exists():
        return 0

    created = 0
    for folder in sorted(seed_dir.iterdir()):
        if not folder.is_dir():
            continue
        info_path = folder / "employee_info.json"
        if not info_path.exists():
            continue
        data = json.loads(info_path.read_text())
        existing = (
            db.query(Employee)
            .filter(Employee.employee_id == data["employee_id"])
            .first()
        )
        if existing:
            continue
        emp = Employee(
            employee_id=data["employee_id"],
            name=data["name"],
            grade=data["grade"],
            title=data["title"],
            department=data["department"],
            manager_id=data["manager_id"],
            home_base=data["home_base"],
            seeded=True,
        )
        db.add(emp)
        created += 1
    if created:
        db.commit()
    return created
