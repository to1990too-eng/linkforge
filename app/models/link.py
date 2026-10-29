from tortoise import fields, models


class Link(models.Model):
    id = fields.IntField(pk=True)
    short_code = fields.CharField(max_length=16, unique=True, db_index=True)
    original_url = fields.CharField(max_length=2048)
    created_at = fields.DatetimeField(auto_now_add=True)
    click_count = fields.IntField(default=0)

    class Meta:
        table = "short_links"