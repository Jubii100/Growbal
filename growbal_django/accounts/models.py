from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
# from services.models import Service
from django.contrib.postgres.fields import ArrayField


from django.db import IntegrityError, transaction
from django.utils.text import slugify

class CustomUserManager(BaseUserManager):
    """
    Manager for the CustomUser model.  Username is the login key,
    email is optional, and we auto-slug usernames from `name`.
    """

    # Public -----------------------------------------------------------------
    def create_user(self, name: str, username: str | None = None,
                    password: str | None = None, **extra_fields):
        if not name:
            raise ValueError("The `name` field is required")

        # 1️⃣ Generate or validate the username
        if username:
            # still allow caller-supplied username
            self._assert_username_available(username)
        else:
            username = self._generate_unique_username(name)

        # 2️⃣ Build user instance
        # user = self.model(username=username, **extra_fields)
        user = self.model(username=username, name=name, **extra_fields)

        # 3️⃣ Password
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, *, name: str, username: str | None = None,
                         password: str | None = None, **extra_fields):
        name = name or username          # fall back if CLI didn’t ask for it
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(name=name, username=username,
                                password=password, **extra_fields)

    def get_or_create_user(self, *, name: str = None, email: str | None = None, username: str | None = None, password: str | None = None,
                           **extra_fields):
        # First check if ServiceProviderProfile with matching name exists
        matching_profile = ServiceProviderProfile.objects.filter(name=name).select_related('user').first()
        if matching_profile:
            return matching_profile.user, False

        username = username or self._generate_unique_username(name)
        # self._assert_username_available(username)
        defaults = {"name": name, **extra_fields}
        if email is not None:
            defaults["email"] = email
        try:
            with transaction.atomic():
                user, created = self.get_or_create(
                    username=username,
                    defaults=defaults,
                )
                if created:
                    if password:
                        user.set_password(password)
                    else:
                        user.set_unusable_password()
                    user.save()
        except IntegrityError:
            # Another process beat us; fetch the existing row
            user = self.get(username=username)
            created = False

        return user, created

    # Internals --------------------------------------------------------------
    def _assert_username_available(self, username: str) -> None:
        if self.filter(username=username).exists():
            raise ValueError("The username is already in use")

    def _generate_unique_username(self, name: str) -> str:
        base = slugify(name) or "user"
        slug = base
        counter = 1
        # Keep the loop + UNIQUE index guard inside a single transaction
        with transaction.atomic():
            # while self.filter(username=slug).exists():
                slug = f"{base}-{counter}"
                # counter += 1
        return slug


class CustomUser(AbstractUser):
    # email = models.EmailField(unique=True)
    username = models.CharField(max_length=200, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True, unique=True)  # optional
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['name']

    objects = CustomUserManager()

    def __str__(self):
        return self.username

    # class Meta:
    #     app_label = 'accounts'


class ServiceProviderProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    # service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name='entities')

    PROVIDER_TYPES = [
        ('Company', 'Company'),
        ('Agent', 'Agent'),
    ]
    # TIER_CHOICES = [
    #     ('Level 1', 'Level 1'),
    #     ('Level 2', 'Level 2'),
    #     ('Level 3', 'Level 3'),
    # ]
    COUNTRY_CHOICES = [
        ('Afghanistan', 'Afghanistan'), ('Albania', 'Albania'), ('Algeria', 'Algeria'), ('Andorra', 'Andorra'), ('Angola', 'Angola'),
        ('Antigua and Barbuda', 'Antigua and Barbuda'), ('Argentina', 'Argentina'), ('Armenia', 'Armenia'), ('Australia', 'Australia'),
        ('Austria', 'Austria'), ('Azerbaijan', 'Azerbaijan'), ('Bahamas', 'Bahamas'), ('Bahrain', 'Bahrain'), ('Bangladesh', 'Bangladesh'),
        ('Barbados', 'Barbados'), ('Belarus', 'Belarus'), ('Belgium', 'Belgium'), ('Belize', 'Belize'), ('Benin', 'Benin'), ('Bhutan', 'Bhutan'),
        ('Bolivia', 'Bolivia'), ('Bosnia and Herzegovina', 'Bosnia and Herzegovina'), ('Botswana', 'Botswana'), ('Brazil', 'Brazil'), ('Brunei', 'Brunei'),
        ('Bulgaria', 'Bulgaria'), ('Burkina Faso', 'Burkina Faso'), ('Burundi', 'Burundi'), ('Cabo Verde', 'Cabo Verde'), ('Cambodia', 'Cambodia'),
        ('Cameroon', 'Cameroon'), ('Canada', 'Canada'), ('Central African Republic', 'Central African Republic'), ('Chad', 'Chad'), ('Chile', 'Chile'),
        ('China', 'China'), ('Colombia', 'Colombia'), ('Comoros', 'Comoros'), ('Congo, Democratic Republic of the', 'Congo, Democratic Republic of the'),
        ('Congo, Republic of the', 'Congo, Republic of the'), ('Costa Rica', 'Costa Rica'), ('Croatia', 'Croatia'), ('Cuba', 'Cuba'), ('Cyprus', 'Cyprus'),
        ('Czech Republic', 'Czech Republic'), ('Denmark', 'Denmark'), ('Djibouti', 'Djibouti'), ('Dominica', 'Dominica'), ('Dominican Republic', 'Dominican Republic'),
        ('Ecuador', 'Ecuador'), ('Egypt', 'Egypt'), ('El Salvador', 'El Salvador'), ('Equatorial Guinea', 'Equatorial Guinea'), ('Eritrea', 'Eritrea'),
        ('Estonia', 'Estonia'), ('Eswatini', 'Eswatini'), ('Ethiopia', 'Ethiopia'), ('Fiji', 'Fiji'), ('Finland', 'Finland'), ('France', 'France'),
        ('Gabon', 'Gabon'), ('Gambia', 'Gambia'), ('Georgia', 'Georgia'), ('Germany', 'Germany'), ('Ghana', 'Ghana'), ('Greece', 'Greece'), ('Grenada', 'Grenada'),
        ('Guatemala', 'Guatemala'), ('Guinea', 'Guinea'), ('Guinea-Bissau', 'Guinea-Bissau'), ('Guyana', 'Guyana'), ('Haiti', 'Haiti'), ('Honduras', 'Honduras'),
        ('Hungary', 'Hungary'), ('Iceland', 'Iceland'), ('India', 'India'), ('Indonesia', 'Indonesia'), ('Iran', 'Iran'), ('Iraq', 'Iraq'), ('Ireland', 'Ireland'),
        ('Israel', 'Israel'), ('Italy', 'Italy'), ('Jamaica', 'Jamaica'), ('Japan', 'Japan'), ('Jordan', 'Jordan'), ('Kazakhstan', 'Kazakhstan'), ('Kenya', 'Kenya'),
        ('Kiribati', 'Kiribati'), ('Korea, North', 'Korea, North'), ('Korea, South', 'Korea, South'), ('Kosovo', 'Kosovo'), ('Kuwait', 'Kuwait'), ('Kyrgyzstan', 'Kyrgyzstan'),
        ('Laos', 'Laos'), ('Latvia', 'Latvia'), ('Lebanon', 'Lebanon'), ('Lesotho', 'Lesotho'), ('Liberia', 'Liberia'), ('Libya', 'Libya'), ('Liechtenstein', 'Liechtenstein'),
        ('Lithuania', 'Lithuania'), ('Luxembourg', 'Luxembourg'), ('Madagascar', 'Madagascar'), ('Malawi', 'Malawi'), ('Malaysia', 'Malaysia'), ('Maldives', 'Maldives'),
        ('Mali', 'Mali'), ('Malta', 'Malta'), ('Marshall Islands', 'Marshall Islands'), ('Mauritania', 'Mauritania'), ('Mauritius', 'Mauritius'), ('Mexico', 'Mexico'),
        ('Micronesia', 'Micronesia'), ('Moldova', 'Moldova'), ('Monaco', 'Monaco'), ('Mongolia', 'Mongolia'), ('Montenegro', 'Montenegro'), ('Morocco', 'Morocco'),
        ('Mozambique', 'Mozambique'), ('Myanmar', 'Myanmar'), ('Namibia', 'Namibia'), ('Nauru', 'Nauru'), ('Nepal', 'Nepal'), ('Netherlands', 'Netherlands'),
        ('New Zealand', 'New Zealand'), ('Nicaragua', 'Nicaragua'), ('Niger', 'Niger'), ('Nigeria', 'Nigeria'), ('North Macedonia', 'North Macedonia'), ('Norway', 'Norway'),
        ('Oman', 'Oman'), ('Pakistan', 'Pakistan'), ('Palau', 'Palau'), ('Panama', 'Panama'), ('Papua New Guinea', 'Papua New Guinea'), ('Paraguay', 'Paraguay'),
        ('Peru', 'Peru'), ('Philippines', 'Philippines'), ('Poland', 'Poland'), ('Portugal', 'Portugal'), ('Qatar', 'Qatar'), ('Romania', 'Romania'), ('Russia', 'Russia'),
        ('Rwanda', 'Rwanda'), ('Saint Kitts and Nevis', 'Saint Kitts and Nevis'), ('Saint Lucia', 'Saint Lucia'), ('Saint Vincent and the Grenadines', 'Saint Vincent and the Grenadines'),
        ('Samoa', 'Samoa'), ('San Marino', 'San Marino'), ('Sao Tome and Principe', 'Sao Tome and Principe'), ('Saudi Arabia', 'Saudi Arabia'), ('Senegal', 'Senegal'),
        ('Serbia', 'Serbia'), ('Seychelles', 'Seychelles'), ('Sierra Leone', 'Sierra Leone'), ('Singapore', 'Singapore'), ('Slovakia', 'Slovakia'), ('Slovenia', 'Slovenia'),
        ('Solomon Islands', 'Solomon Islands'), ('Somalia', 'Somalia'), ('South Africa', 'South Africa'), ('South Sudan', 'South Sudan'), ('Spain', 'Spain'),
        ('Sri Lanka', 'Sri Lanka'), ('Sudan', 'Sudan'), ('Suriname', 'Suriname'), ('Sweden', 'Sweden'), ('Switzerland', 'Switzerland'), ('Syria', 'Syria'),
        ('Taiwan', 'Taiwan'), ('Tajikistan', 'Tajikistan'), ('Tanzania', 'Tanzania'), ('Thailand', 'Thailand'), ('Togo', 'Togo'), ('Tonga', 'Tonga'),
        ('Trinidad and Tobago', 'Trinidad and Tobago'), ('Tunisia', 'Tunisia'), ('Turkey', 'Turkey'), ('Turkmenistan', 'Turkmenistan'), ('Tuvalu', 'Tuvalu'),
        ('Uganda', 'Uganda'), ('Ukraine', 'Ukraine'), ('UAE', 'UAE'), ('UK', 'UK'), ('USA', 'USA'), ('Uruguay', 'Uruguay'), ('Uzbekistan', 'Uzbekistan'),
        ('Vanuatu', 'Vanuatu'), ('Vatican City', 'Vatican City'), ('Venezuela', 'Venezuela'), ('Vietnam', 'Vietnam'), ('Yemen', 'Yemen'), ('Zambia', 'Zambia'), ('Zimbabwe', 'Zimbabwe')
    ]

    provider_type = models.CharField(max_length=50, choices=PROVIDER_TYPES, default='Company')
    country = models.CharField(max_length=100, blank=True, null=True, choices=COUNTRY_CHOICES)

    STATUS_CHOICES = [('active', 'Active'), ('inactive', 'Inactive')]
    session_status = models.CharField(max_length=8, blank=False, choices=STATUS_CHOICES, default='inactive')

    # tier = models.CharField(max_length=50, blank=True, choices=TIER_CHOICES)

    name = models.CharField(max_length=255, blank=True)
    vision = models.TextField(blank=True, null=True)
    logo = models.TextField(blank=True, null=True)
    # logo_stage_ingested = models.BooleanField(default=False)
    # logo_prod_ingested = models.BooleanField(default=False)
    # logo_img = models.ImageField(upload_to='logos/', blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    telephones = ArrayField(
        base_field=models.CharField(max_length=30),
        blank=True,
        default=list,
        help_text="One or more contact telephone numbers.",
    )
    mobiles = ArrayField(
        base_field=models.CharField(max_length=30),
        blank=True,
        default=list,
        help_text="One or more contact mobile numbers.",
    )
    # emails = models.TextField(blank=True, null=True)
    emails = ArrayField(
        base_field=models.EmailField(max_length=320),
        blank=True,
        default=list,         # never use `null=True` with arrays; an empty list is clearer
        help_text="One or more contact e-mail addresses.",
    )
    office_locations = models.TextField(blank=True, null=True)
    key_individuals = models.TextField(blank=True, null=True)
    representatives = models.TextField(blank=True, null=True)
    date_modified = models.DateTimeField(auto_now=True)
    date_created = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.user.username} Profile"


class ServiceProviderMemberProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='member_profile')
    name = models.CharField(max_length=255, blank=False, null=False)
    company = models.ForeignKey(ServiceProviderProfile, on_delete=models.CASCADE, related_name='members')
    def clean(self):
        if self.company.provider_type != 'Company':
            raise ValidationError("Cannot link a ServiceProviderMemberProfile unless the ServiceProviderProfile has provider_type='Company'.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Ensure validation is called on save.
        super().save(*args, **kwargs)

    role_description = models.CharField(max_length=255, blank=True, null=True)
    telephone = models.CharField(max_length=30, blank=True, null=True)
    mobile = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    linkedin = models.URLField(blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)

    additional_info = models.TextField(blank=True, null=True)
    date_modified = models.DateTimeField(auto_now=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} Member Profile"



# ('Investor', 'Investor'),
# ('Startup', 'Startup'),