from __future__ import annotations

import unicodedata

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class AcademicDomain(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        if self.parent_id:
            return f"{self.parent.name} / {self.name}"
        return self.name


class DocumentType(models.Model):
    """Nature académique d'un document : cours, article, mémoire, thèse, examen, TD, rapport…

    C'est la source de vérité pour l'icône et la couleur affichées côté frontend.
    Les administrateurs peuvent ajouter de nouveaux types sans changement de code.
    """

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=60,
        blank=True,
        help_text="Nom d'icône ou emoji utilisé par le frontend.",
    )
    color = models.CharField(
        max_length=7,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^#[0-9A-Fa-f]{6}$",
                message="La couleur doit être un code hexadécimal, ex. #2563EB",
            )
        ],
        help_text="Couleur hexadécimale, ex. #2563EB.",
    )
    display_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name


def normalize_author_name(display_name: str) -> str:
    """Forme de tri d'un nom d'auteur : minuscules, sans accents, espaces
    normalisés. Déterministe, et sans hypothèse sur la structure du nom."""
    folded = unicodedata.normalize("NFKD", display_name or "")
    without_accents = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    return " ".join(without_accents.lower().split())


class Author(models.Model):
    class AuthorType(models.TextChoices):
        PERSON = "person", "Person"
        GROUP = "group", "Group"
        INSTITUTION = "institution", "Institution"
        PUBLISHER = "publisher", "Publisher"
        OTHER = "other", "Other rights holder"

    display_name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=220)
    author_type = models.CharField(
        max_length=24,
        choices=AuthorType.choices,
        default=AuthorType.PERSON,
    )
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="author_profiles",
    )
    affiliation = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["normalized_name", "display_name"]

    def __str__(self) -> str:
        return self.display_name

    def save(self, *args, **kwargs):
        """`normalized_name` est dérivé, jamais écrit à la main.

        Il l'était, et deux conventions coexistaient : les tests écrivaient
        « nze aline » (nom de famille d'abord), le seed et l'API staff
        écrivaient `display_name.lower()`, soit « aline nze ». Comme ce champ
        pilote `Meta.ordering`, la liste d'auteurs se retrouvait triée de deux
        façons selon l'origine de la ligne.

        La dérivation est délibérément littérale : minuscules, accents
        dépliés, espaces normalisés. Elle ne devine pas la structure du nom.
        Trier par nom de famille, comme le veut l'usage académique, demande de
        savoir lequel l'est — impossible sur « Université Omar Bongo » — et
        donc un champ `sort_name` distinct, qui est une décision produit.

        Limite connue : `bulk_create` et `QuerySet.update` ne passent pas par
        ici. Aucun chemin de production ne les emprunte pour un auteur, et un
        test le vérifie ; un import en masse devra appeler
        `normalize_author_name` lui-même.
        """
        self.normalized_name = normalize_author_name(self.display_name)
        super().save(*args, **kwargs)


class Document(models.Model):
    class Category(models.TextChoices):
        VOLUNTARY_TEACHER_DEPOSIT = (
            "voluntary_teacher_deposit",
            "Voluntary teacher deposit",
        )
        INSTITUTIONAL_FUND = "institutional_fund", "Institutional fund"
        STUDENT_WORK = "student_work", "Student work"
        OPEN_RESOURCE = "open_resource", "Open resource"
        COMMERCIAL_PARTNER_CONTENT = (
            "commercial_partner_content",
            "Commercial partner content",
        )

    class AccessModel(models.TextChoices):
        FREE = "free", "Free"
        SUBSCRIPTION = "subscription", "Subscription"
        INSTITUTION_ONLY = "institution_only", "Institution only"
        SPONSORED = "sponsored", "Sponsored"
        RESTRICTED = "restricted", "Restricted"
        PRIVATE = "private", "Private"

    class PublicationStatus(models.TextChoices):
        """Les cinq états du plan directeur §8.2, plus le rejet (D014).

        `submitted` est le « en vérification » du plan directeur. Les trois
        états de revue qui existaient ici — `rights_review`,
        `technical_processing`, `editorial_review` — ont été retirés parce
        qu'ils dupliquaient des barrières tenues ailleurs, et mieux :

        - les droits, par `RightsAgreement.authorization_status`, que
          `missing_publication_requirements` exige déjà approuvé ;
        - le traitement, par `DocumentVersion.status` et `ProcessingJob`,
          qu'agrège `/api/staff/v1/documents/<id>/ingestion/`.

        Deux représentations du même verrou finissent par se contredire, et
        c'est alors la publication qui devient imprévisible. `suspended` est
        parti aussi : `withdrawn` couvre déjà « non lisible, traçable,
        republiable sur nouvelle décision ».
        """

        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        PUBLISHED = "published", "Published"
        WITHDRAWN = "withdrawn", "Withdrawn"
        ARCHIVED = "archived", "Archived"
        REJECTED = "rejected", "Rejected"

    title = models.CharField(max_length=260)
    slug = models.SlugField(unique=True)
    abstract = models.TextField(blank=True)
    language_code = models.CharField(max_length=12, default="fr")
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    document_type = models.ForeignKey(
        DocumentType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    academic_domain = models.ForeignKey(
        AcademicDomain,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    owner_organization = models.ForeignKey(
        "accounts.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_documents",
    )
    category = models.CharField(max_length=40, choices=Category.choices)
    access_model = models.CharField(max_length=24, choices=AccessModel.choices)
    publication_status = models.CharField(
        max_length=32,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
    )
    confidentiality_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    authors = models.ManyToManyField(
        Author,
        through="DocumentAuthor",
        related_name="documents",
    )

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title

    @property
    def entitlement_scope_id(self) -> str:
        return str(self.pk)

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.publication_year is not None:
            current_year = timezone.now().year
            if self.publication_year < 1900 or self.publication_year > current_year + 1:
                raise ValidationError(
                    {
                        "publication_year": (
                            f"L'année de publication doit être comprise entre 1900 et {current_year + 1}."
                        )
                    }
                )


class DocumentAuthor(models.Model):
    class Role(models.TextChoices):
        AUTHOR = "author", "Author"
        COAUTHOR = "coauthor", "Co-author"
        SUPERVISOR = "supervisor", "Supervisor"
        EDITOR = "editor", "Editor"
        INSTITUTIONAL_CONTRIBUTOR = (
            "institutional_contributor",
            "Institutional contributor",
        )

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="document_authors",
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.PROTECT,
        related_name="document_authorships",
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.AUTHOR)
    position = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "author"],
                name="uniq_author_per_document",
            ),
            models.UniqueConstraint(
                fields=["document", "position"],
                name="uniq_author_position_per_document",
            ),
        ]
        ordering = ["document", "position"]

    def __str__(self) -> str:
        return f"{self.author.display_name} - {self.document.title}"


class Collection(models.Model):
    """Regroupement thématique de documents (ex. « Licence Droit — UOB »).

    Une collection peut servir de portée (scope) à un entitlement ou à une offre
    commerciale : on accorde/vend l'accès à la collection via son identifiant.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    academic_domain = models.ForeignKey(
        AcademicDomain,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="collections",
    )
    owner_organization = models.ForeignKey(
        "accounts.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_collections",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_active = models.BooleanField(default=True)
    documents = models.ManyToManyField(
        Document,
        through="CollectionItem",
        related_name="collections",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def entitlement_scope_id(self) -> str:
        return str(self.pk)


class CollectionItem(models.Model):
    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name="items",
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        related_name="collection_items",
    )
    position = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "document"],
                name="uniq_document_per_collection",
            ),
            models.UniqueConstraint(
                fields=["collection", "position"],
                name="uniq_position_per_collection",
            ),
        ]
        ordering = ["collection", "position"]

    def __str__(self) -> str:
        return f"{self.collection.name} #{self.position}: {self.document.title}"


class RightsAgreement(models.Model):
    class AgreementType(models.TextChoices):
        TEACHER_VOLUNTARY = "teacher_voluntary", "Teacher voluntary publication"
        INSTITUTIONAL_ARCHIVE = "institutional_archive", "Institutional archive/fund"
        STUDENT_CONSENT = "student_consent", "Student work consent"
        OPEN_LICENSE = "open_license", "Open license"
        COMMERCIAL_DISTRIBUTION = "commercial_distribution", "Commercial distribution"

    class AuthorizationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"

    class WithdrawalRule(models.TextChoices):
        AUTHOR_REQUEST = "author_request", "Author request"
        CONTRACT_TERMS = "contract_terms", "Contract terms"
        CONFIDENTIALITY_OVERRIDE = "confidentiality_override", "Confidentiality override"
        LICENSE_INVALID = "license_invalid", "License invalid"
        COMMERCIAL_TERMS = "commercial_terms", "Commercial terms"

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="rights_agreement",
    )
    rights_holder_name = models.CharField(max_length=240)
    agreement_type = models.CharField(max_length=40, choices=AgreementType.choices)
    authorization_status = models.CharField(
        max_length=24,
        choices=AuthorizationStatus.choices,
        default=AuthorizationStatus.DRAFT,
    )
    authorization_date = models.DateField(null=True, blank=True)
    access_model = models.CharField(max_length=24, choices=Document.AccessModel.choices)
    withdrawal_rule = models.CharField(max_length=40, choices=WithdrawalRule.choices)
    revenue_sharing_rule = models.TextField(blank=True)
    confidentiality_terms = models.TextField(blank=True)
    consent_reference = models.CharField(max_length=160, blank=True)
    reviewer_decision = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    audit_reference = models.CharField(max_length=160, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["document__title"]

    def __str__(self) -> str:
        return f"{self.document.title} rights - {self.authorization_status}"

    def is_valid_for_publication(self, at=None) -> bool:
        at = at or timezone.now().date()
        if self.authorization_status != self.AuthorizationStatus.APPROVED:
            return False
        if self.access_model not in Document.AccessModel.values:
            return False
        if not self.rights_holder_name or not self.authorization_date:
            return False
        if not self.withdrawal_rule or not self.reviewer_decision or not self.audit_reference:
            return False
        if self.access_model != self.document.access_model:
            return False
        if self.valid_from and self.valid_from > at:
            return False
        if self.valid_until and self.valid_until < at:
            return False
        return True
