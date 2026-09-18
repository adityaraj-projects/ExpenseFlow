from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.category import Category, CategoryType
from app.models.transaction import Transaction
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryResponse])
def get_categories(
    type: Optional[str] = Query(None, description="Filter by type: income, expense, or both"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all categories belonging to the authenticated user."""
    query = db.query(Category).filter(Category.user_id == current_user.id)

    if type:
        type_lower = type.lower()
        if type_lower in ["income", "expense"]:
            query = query.filter((Category.type == type_lower) | (Category.type == CategoryType.BOTH))
        elif type_lower == "both":
            query = query.filter(Category.type == CategoryType.BOTH)

    categories = query.order_by(Category.name.asc()).all()
    return categories


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category_in: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new custom category for the user."""
    existing = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.name.ilike(category_in.name.strip()),
        Category.type == category_in.type
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{category_in.name}' of type '{category_in.type.value}' already exists."
        )

    new_cat = Category(
        user_id=current_user.id,
        name=category_in.name.strip(),
        type=category_in.type,
        icon=category_in.icon or "tag",
        color=category_in.color or "#6366F1",
        is_default=False
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    category_in: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update category properties (name, type, icon, color)."""
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found."
        )

    if category_in.name is not None:
        target_name = category_in.name.strip()
        target_type = category_in.type if category_in.type is not None else category.type
        # check duplicate
        duplicate = db.query(Category).filter(
            Category.user_id == current_user.id,
            Category.id != category.id,
            Category.name.ilike(target_name),
            Category.type == target_type
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category '{target_name}' already exists."
            )
        category.name = target_name

    if category_in.type is not None:
        category.type = category_in.type
    if category_in.icon is not None:
        category.icon = category_in.icon
    if category_in.color is not None:
        category.color = category_in.color

    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Safely delete a category.
    Prevents deletion if there are transactions linked to this category.
    """
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found."
        )

    # Check for linked transactions
    linked_tx_count = db.query(Transaction).filter(
        Transaction.category_id == category_id,
        Transaction.user_id == current_user.id
    ).count()

    if linked_tx_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot delete category '{category.name}' because {linked_tx_count} transaction(s) "
                "are linked to it. Please reassign or delete these transactions first."
            )
        )

    db.delete(category)
    db.commit()
    return {"message": f"Category '{category.name}' deleted successfully."}
