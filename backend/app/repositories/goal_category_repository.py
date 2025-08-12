from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import List, Optional

from app.models.goal_category import GoalCategory
from app.schemas.goal_category import GoalCategoryCreate, GoalCategoryUpdate


class GoalCategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_categories(self, active_only: bool = False) -> List[GoalCategory]:
        """Get all goal categories from the goal_categories table"""
        query = self.db.query(GoalCategory)
        if active_only:
            query = query.filter(GoalCategory.is_active == True)
        return query.order_by(GoalCategory.name).all()

    def get_category_by_id(self, category_id: int) -> Optional[GoalCategory]:
        """Get a specific goal category by ID"""
        return self.db.query(GoalCategory).filter(GoalCategory.id == category_id).first()

    def create_category(self, category_data: GoalCategoryCreate) -> GoalCategory:
        """Create a new goal category"""
        category = GoalCategory(**category_data.dict())
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def update_category(self, category_id: int, category_data: GoalCategoryUpdate) -> Optional[GoalCategory]:
        """Update an existing goal category"""
        category = self.get_category_by_id(category_id)
        if not category:
            return None

        update_data = category_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(category, field, value)

        self.db.commit()
        self.db.refresh(category)
        return category

    def delete_category(self, category_id: int) -> bool:
        """Delete a goal category (only if not in use)"""
        category = self.get_category_by_id(category_id)
        if not category:
            return False

        # Check if category is in use by any goals
        from app.models.iep_goal import IEPGoal
        goals_using_category = self.db.query(IEPGoal).filter(IEPGoal.goal_category_id == category_id).first()
        if goals_using_category:
            raise ValueError(f"Cannot delete category '{category.name}' as it is currently in use by existing goals")

        self.db.delete(category)
        self.db.commit()
        return True

    def toggle_category_status(self, category_id: int) -> Optional[GoalCategory]:
        """Toggle the active status of a goal category"""
        category = self.get_category_by_id(category_id)
        if not category:
            return None

        category.is_active = not category.is_active
        self.db.commit()
        self.db.refresh(category)
        return category
