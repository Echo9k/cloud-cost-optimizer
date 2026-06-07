"""Resource ingestion & inventory endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import seed as seed_module
from app.database import get_db
from app.models import Resource
from app.schemas import ResourceCreate, ResourceOut

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("", response_model=list[ResourceOut])
def list_resources(db: Session = Depends(get_db)) -> list[Resource]:
    return db.query(Resource).order_by(Resource.monthly_cost.desc()).all()


@router.post("", response_model=ResourceOut, status_code=status.HTTP_201_CREATED)
def create_resource(
    payload: ResourceCreate, db: Session = Depends(get_db)
) -> Resource:
    resource = Resource(**payload.model_dump())
    db.add(resource)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Resource '{payload.external_id}' already exists.",
        )
    db.refresh(resource)
    return resource


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: int, db: Session = Depends(get_db)) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.post("/seed", status_code=status.HTTP_201_CREATED)
def seed_resources(db: Session = Depends(get_db)) -> dict:
    """Load the synthetic demo fleet (resets existing data)."""
    count = seed_module.seed(db, reset=True)
    return {"seeded_resources": count}
