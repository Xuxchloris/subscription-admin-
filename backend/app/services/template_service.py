import json

from sqlalchemy.orm import Session

from app.models.content_template import ContentTemplate as ContentTemplateModel
from app.schemas.jobs import ContentTemplate, ContentTemplateCreate, ContentTemplateUpdate


class TemplateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _to_schema(self, template: ContentTemplateModel) -> ContentTemplate:
        try:
            skills = json.loads(template.skills_json or "[]")
        except json.JSONDecodeError:
            skills = []
        if not isinstance(skills, list):
            skills = []
        return ContentTemplate(
            id=template.id,
            name=template.name,
            prompt=template.prompt,
            skills=[str(skill) for skill in skills],
            notes=template.notes,
            created_at=template.created_at.isoformat() if template.created_at else None,
            updated_at=template.updated_at.isoformat() if template.updated_at else None,
        )

    def list_templates(self) -> list[ContentTemplate]:
        templates = self.db.query(ContentTemplateModel).order_by(ContentTemplateModel.name.asc()).all()
        return [self._to_schema(template) for template in templates]

    def create_template(self, payload: ContentTemplateCreate) -> ContentTemplate:
        template = ContentTemplateModel(
            name=payload.name.strip(),
            prompt=payload.prompt,
            skills_json=json.dumps(payload.skills, ensure_ascii=False),
            notes=payload.notes,
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return self._to_schema(template)

    def update_template(self, template_id: int, payload: ContentTemplateUpdate) -> ContentTemplate | None:
        template = self.db.get(ContentTemplateModel, template_id)
        if template is None:
            return None
        template.name = payload.name.strip()
        template.prompt = payload.prompt
        template.skills_json = json.dumps(payload.skills, ensure_ascii=False)
        template.notes = payload.notes
        self.db.commit()
        self.db.refresh(template)
        return self._to_schema(template)

    def delete_template(self, template_id: int) -> bool:
        template = self.db.get(ContentTemplateModel, template_id)
        if template is None:
            return False
        self.db.delete(template)
        self.db.commit()
        return True
