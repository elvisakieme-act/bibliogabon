from django.utils import timezone

from accounts.models import Entitlement, Organization, User
from billing.models import CommercialOffer, PaymentTransaction
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor, RightsAgreement


def create_user(email="staff@example.ga", *, is_staff=False):
    return User.objects.create_user(email=email, password="password", is_staff=is_staff)


def create_organization(slug="operations-org"):
    return Organization.objects.create(
        name=f"Organization {slug}",
        slug=slug,
        organization_type=Organization.OrganizationType.UNIVERSITY,
    )


def create_publishable_document(slug="operations-document"):
    organization = create_organization(slug=f"owner-{slug}")
    domain = AcademicDomain.objects.create(name=f"Domain {slug}", slug=f"domain-{slug}")
    document = Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        owner_organization=organization,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.SUBMITTED,
    )
    author = Author.objects.create(display_name="Author", normalized_name="author")
    DocumentAuthor.objects.create(document=document, author=author, role=DocumentAuthor.Role.AUTHOR)
    RightsAgreement.objects.create(
        document=document,
        rights_holder_name="Rights Holder",
        agreement_type=RightsAgreement.AgreementType.OPEN_LICENSE,
        authorization_status=RightsAgreement.AuthorizationStatus.APPROVED,
        authorization_date=timezone.now().date(),
        access_model=document.access_model,
        withdrawal_rule=RightsAgreement.WithdrawalRule.LICENSE_INVALID,
        reviewer_decision="Approved for publication",
        audit_reference=f"audit-{slug}",
    )
    return document


def create_payment_transaction(user=None):
    user = user or create_user(email="payer@example.ga")
    offer = CommercialOffer.objects.create(
        name="Monthly Access",
        slug="monthly-access",
        offer_type=CommercialOffer.OfferType.INDIVIDUAL,
        billing_period=CommercialOffer.BillingPeriod.MONTHLY,
        price_xaf=1000,
        duration_days=30,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )
    return PaymentTransaction.objects.create(
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=1000,
        idempotency_key="operations-payment-key",
    )


def create_entitlement(user=None):
    user = user or create_user(email="entitled@example.ga")
    return Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.ADMIN_GRANT,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )
