from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from catalog.models import Document


class DocumentSearchIndex(models.Model):
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="search_index",
    )
    title = models.CharField(max_length=260)
    slug = models.SlugField(max_length=260)
    abstract = models.TextField(blank=True)
    language_code = models.CharField(max_length=12, default="fr")
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    access_model = models.CharField(max_length=24, choices=Document.AccessModel.choices)
    domain_name = models.CharField(max_length=160, blank=True)
    domain_slug = models.SlugField(max_length=160, blank=True)
    author_names = models.TextField(blank=True)
    metadata_text = models.TextField(blank=True)
    page_text = models.TextField(blank=True)
    indexed_page_count = models.PositiveIntegerField(default=0)
    indexed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain_slug"], name="discovery_domain_slug_idx"),
            models.Index(fields=["language_code"], name="discovery_language_idx"),
            models.Index(fields=["access_model"], name="discovery_access_idx"),
            models.Index(fields=["publication_year"], name="discovery_year_idx"),
        ]
        ordering = ["title"]

    def clean(self):
        if not self.title or not self.title.strip():
            raise ValidationError("Title must not be blank")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title
