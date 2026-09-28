from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class DocumentPage(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    version = models.ForeignKey(
        "document_ingestion.DocumentVersion",
        on_delete=models.CASCADE,
        related_name="pages",
    )
    page_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_by_job = models.ForeignKey(
        "document_ingestion.ProcessingJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_pages",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "page_number"],
                name="uniq_page_number_per_document_version",
            ),
            models.CheckConstraint(
                condition=Q(page_number__gte=1),
                name="document_page_number_positive",
            ),
        ]
        ordering = ["version", "page_number"]

    def __str__(self) -> str:
        return f"{self.version} page {self.page_number}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        if self.created_by_job_id and self.created_by_job.version_id != self.version_id:
            raise ValidationError("Processing job must belong to the same document version")


class ExtractedText(models.Model):
    class ExtractionMethod(models.TextChoices):
        TEXT_LAYER = "text_layer", "Text layer"
        OCR = "ocr", "OCR"
        MANUAL = "manual", "Manual"

    page = models.OneToOneField(
        DocumentPage,
        on_delete=models.CASCADE,
        related_name="extracted_text",
    )
    text = models.TextField()
    language_code = models.CharField(max_length=12, default="fr")
    extraction_method = models.CharField(
        max_length=24,
        choices=ExtractionMethod.choices,
        default=ExtractionMethod.TEXT_LAYER,
    )
    confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    word_boxes = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Position de chaque mot sur la page, en fractions de la largeur et "
            "de la hauteur : [[x0, y0, x1, y1, mot], …]. Des fractions et non "
            "des pixels, pour que les positions survivent à un changement de "
            "largeur de rendu — un stockage en pixels se décalerait en silence "
            "le jour où DOCUMENT_PAGE_IMAGE_WIDTH change. Liste vide quand les "
            "positions sont inconnues : le lecteur retombe alors sur le texte "
            "à plat."
        ),
    )
    created_by_job = models.ForeignKey(
        "document_ingestion.ProcessingJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_extracted_texts",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page"]

    def __str__(self) -> str:
        return f"Text for {self.page}"

    def save(self, *args, **kwargs):
        if self.confidence is not None:
            self.confidence = Decimal(str(self.confidence))
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        if not self.text or not self.text.strip():
            raise ValidationError("Extracted text must not be blank")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValidationError("Confidence must be between 0 and 1")
        if self.created_by_job_id and self.created_by_job.version_id != self.page.version_id:
            raise ValidationError("Processing job must belong to the same document version")
        self._clean_word_boxes()

    def _clean_word_boxes(self):
        """Une boîte mal formée doit être refusée à l'écriture, pas au rendu.

        Le lecteur positionne ces valeurs en CSS. Une coordonnée hors de
        [0, 1] y produirait un mot placé hors de la page, et une boîte à cinq
        éléments manquants une exception dans le navigateur — soit un défaut
        qui n'apparaît qu'à la lecture, loin de sa cause.
        """
        if self.word_boxes in (None, ""):
            self.word_boxes = []
            return
        if not isinstance(self.word_boxes, list):
            raise ValidationError("word_boxes must be a list")
        for box in self.word_boxes:
            if not isinstance(box, list) or len(box) != 5:
                raise ValidationError("Each word box must be [x0, y0, x1, y1, word]")
            *coordinates, word = box
            if not isinstance(word, str) or not word:
                raise ValidationError("A word box must carry a non-empty word")
            for value in coordinates:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValidationError("Word box coordinates must be numbers")
                if not 0 <= value <= 1:
                    raise ValidationError("Word box coordinates must be fractions in [0, 1]")


class SearchIndexRecord(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        INDEXED = "indexed", "Indexed"
        FAILED = "failed", "Failed"

    page = models.OneToOneField(
        DocumentPage,
        on_delete=models.CASCADE,
        related_name="search_index_record",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    content_hash = models.CharField(
        max_length=64,
        validators=[
            RegexValidator(
                regex=r"^[a-f0-9]{64}$",
                message="Content hash must be a lowercase SHA-256 hex digest",
            )
        ],
    )
    language_code = models.CharField(max_length=12, default="fr")
    indexed_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"], name="search_index_status_idx"),
            models.Index(fields=["language_code"], name="search_index_language_idx"),
        ]
        ordering = ["page"]

    def __str__(self) -> str:
        return f"{self.status}: {self.page}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
