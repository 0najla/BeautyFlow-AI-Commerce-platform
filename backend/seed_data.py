from app import app, db
from models import Account, AccountProfile, AccountSecurity, RoleEnum, Address
from sqlalchemy import select
from werkzeug.security import generate_password_hash

def get_or_create(model, defaults=None, **kwargs):
    inst = db.session.execute(select(model).filter_by(**kwargs)).scalar_one_or_none()
    if inst:
        return inst, False
    params = dict(**kwargs)
    if defaults:
        params.update(defaults)
    inst = model(**params)
    db.session.add(inst)
    db.session.flush()
    return inst, True

with app.app_context():
    # 1) إنشاء حسابات
    admin, _ = get_or_create(
        Account, username="admin",
        defaults=dict(
            email="admin@beautyflow.local",
            phone_number="0500000000",
            password_hash=generate_password_hash("Admin@123"),
            role=RoleEnum.ADMIN
        )
    )

    najla, _ = get_or_create(
        Account, username="najla",
        defaults=dict(
            email="najla@example.com",
            phone_number="0555555555",
            password_hash=generate_password_hash("User@123"),
            role=RoleEnum.USER
        )
    )

    supplier1, _ = get_or_create(
        Account, username="supplier1",
        defaults=dict(
            email="supplier1@vendor.com",
            phone_number="0544444444",
            password_hash=generate_password_hash("Supp@123"),
            role=RoleEnum.SUPPLIER
        )
    )

    # 2) الملف الشخصي
    get_or_create(AccountProfile, account_id=admin.id,
                  defaults=dict(full_name="BeautyFlow Admin", locale="en-US", timezone="Asia/Riyadh"))
    get_or_create(AccountProfile, account_id=najla.id,
                  defaults=dict(full_name="Najla", locale="ar-SA", timezone="Asia/Riyadh"))
    get_or_create(AccountProfile, account_id=supplier1.id,
                  defaults=dict(full_name="Supplier Team", locale="en-US"))

    # 3) الأمان
    get_or_create(AccountSecurity, account_id=admin.id,
                  defaults=dict(is_2fa_enabled=True, two_factor_method="totp"))
    get_or_create(AccountSecurity, account_id=najla.id,
                  defaults=dict(is_2fa_enabled=False))
    get_or_create(AccountSecurity, account_id=supplier1.id,
                  defaults=dict(is_2fa_enabled=True, two_factor_method="sms"))

    # 4) عناوين نجلا
    get_or_create(
        Address, user_id=najla.id, kind="shipping",
        defaults=dict(
            full_name="Najla",
            phone="0555555555",
            line1="Al Bahah - Street 12",
            city="Al Bahah",
            state="Al Bahah",
            country="Saudi Arabia",
            postal_code="65555",
            is_default=True
        )
    )
    get_or_create(
        Address, user_id=najla.id, kind="billing",
        defaults=dict(
            full_name="Najla (Billing)",
            phone="0555555555",
            line1="Al Bahah - Billing St",
            city="Al Bahah",
            state="Al Bahah",
            country="Saudi Arabia",
            postal_code="65555",
            is_default=True
        )
    )

    db.session.commit()
    print("✅ Seed done: accounts + profiles + security + addresses")

