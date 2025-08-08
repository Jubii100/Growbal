import os
import django
import sys
import mysql.connector as mc
from datetime import datetime
from mysql.connector.errors import IntegrityError
import asyncio
import string
import random
from dotenv import load_dotenv
sys.path.insert(0, '../growbal_django')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "growbal.settings")

django.setup()

from services.models import Service
from services.serializers import ServiceSerializer
from accounts.serializers import ServiceProviderProfileSerializer
from accounts.models import ServiceProviderProfile
from asgiref.sync import sync_to_async
import shutil
import mimetypes

@sync_to_async
def load_all_services():
    services = Service.objects.all()
    serializer = ServiceSerializer(services, many=True)
    return serializer.data


@sync_to_async
def load_all_service_provider_profiles():
    profiles = ServiceProviderProfile.objects.prefetch_related("services").all()
    serialized_profiles = []

    for profile in profiles:
        profile_data = ServiceProviderProfileSerializer(profile).data
        services = profile.services.all()
        services_data = ServiceSerializer(services, many=True).data
        profile_data["services"] = services_data
        serialized_profiles.append(profile_data)
    
    return serialized_profiles

@sync_to_async
def update_service_general_descriptions(descriptions):
    services_to_update = Service.objects.filter(
        service_description=descriptions.company_service_description
    )

    services_to_update.update(
        general_service_description=descriptions.general_service_description
    )

# ── DB CONFIG ──────────────────────────────────────────────────────
HOST     = "127.0.0.1"
PORT     = 3306
USER     = "root"
PASSWORD = "rootpass"
SCHEMA   = "growbal"

# # ── CONNECT ────────────────────────────────────────────────────────
# cnx = mc.connect(
#     host=HOST, port=PORT,
#     user=USER, password=PASSWORD,
#     database=SCHEMA,
#     auth_plugin="mysql_native_password",
# )
# cur = cnx.cursor(dictionary=True)
# dict_keys(['user', 'provider_type', 'country', 'session_status', 'name', 'logo', 'website', 'linkedin', 'facebook', 'instagram', 'telephone', 'mobile', 'emails', 'office_locations', 'key_individuals', 'services'])

def truncate_string(value, max_length):
    if value is None:
        return None
    return value[:max_length]

def generate_unique_slug(cursor, length=8):
    cursor.execute(f"SELECT slug FROM `{SCHEMA}`.`establishment`")
    existing_slugs = {row["slug"] for row in cursor.fetchall()}

    while True:
        slug = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        if slug not in existing_slugs and slug is not None:
            return slug

# ── INSERT FUNCTION ────────────────────────────────────────────────
def insert_establishment(profile_dict, cursor, slug):
    company_name = profile_dict.get('name')

    # Check if company already exists
    cursor.execute(f"SELECT id FROM `{SCHEMA}`.`establishment` WHERE company_name = %s", (company_name,))
    result = cursor.fetchone()

    if result:
        # Return existing ID immediately
        return result['id']

    insert_query = f"""
    INSERT INTO `{SCHEMA}`.`establishment` (
        mobile, email, web_site, phone, description, creation_date, company_name, adress, slug, blocked, deleted, verified, type
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    mobile = profile_dict.get('mobiles')[0] if profile_dict.get('mobiles') else None
    phone = profile_dict.get('telephones')[0] if profile_dict.get('telephones') else None
    values = (
        mobile,
        profile_dict.get('emails')[0] if profile_dict.get('emails') else None,
        profile_dict.get('website') or None,
        phone,
        profile_dict["services"][0].get('service_description') if profile_dict.get('services') else None,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        company_name,
        truncate_string(profile_dict.get('office_locations'), 255) if profile_dict.get('office_locations') else None,
        slug,
        False,
        False,
        False,
        0
    )

    cursor.execute(insert_query, values)
    establishment_id = cursor.lastrowid
    return establishment_id

# ── INSERT FUNCTION FOR SERVICE TABLE ──────────────────────────────
def insert_service(service_dict, cursor):
    service_title = service_dict.get('service_title')
    general_service_description = service_dict.get('general_service_description')

    # Check if service already exists
    cursor.execute(f"""
        SELECT id FROM `{SCHEMA}`.`service` 
        WHERE name = %s AND description = %s
    """, (service_title, general_service_description))

    existing_service = cursor.fetchone()

    if existing_service:
        return False

    insert_query = f"""
    INSERT INTO `{SCHEMA}`.`service` (
        name, description, deleted, type_service_id
    )
    VALUES (%s, %s, %s, %s)
    """

    values = (
        service_title,
        general_service_description,
        False,
        1
    )

    cursor.execute(insert_query, values)
    service_id = cursor.lastrowid
    return service_id

# ── INSERT FUNCTION FOR ESTABLISHMENT_SERVICE TABLE ──────────────────────────────
def insert_establishment_service(establishment_id, service_id, cursor):
    insert_query = f"""
    INSERT INTO `{SCHEMA}`.`establishment_services` (
        establishment_id, service_id, deleted
    )
    VALUES (%s, %s, %s)
    """

    # Prepare values
    values = (
        establishment_id,
        service_id,
        False
    )

    print(f"Inserting establishment_service record: {values}")

    # Execute query
    cursor.execute(insert_query, values)
    record_id = cursor.lastrowid
    return record_id


# ── INSERT FUNCTION FOR user TABLE ──────────────────────────────
def insert_user(profile_dict, establishment_id, cursor):
    insert_query = f"""
    INSERT INTO `{SCHEMA}`.`user` (
        adress, creation_date, email, full_name, phone, web_site, establishment_id, is_deleted, stars, confirm_email, role
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Prepare values
    if profile_dict.get('telephones'):
        phone = profile_dict.get('telephones')[0]
    elif profile_dict.get('mobiles'):
        phone = profile_dict.get('mobiles')[0]
    else:
        phone = None
    values = (
        truncate_string(profile_dict.get('office_locations'), 255) if profile_dict.get('office_locations') else None,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        profile_dict.get('emails')[0] if profile_dict.get('emails') else None,
        profile_dict.get('name') if profile_dict.get('name') else None,
        phone,
        profile_dict.get('website') if profile_dict.get('website') else None,
        establishment_id,
        False,
        0,
        1,
        "4"
    )

    print(f"Inserting user record: {values}")

    # Execute query
    cursor.execute(insert_query, values)
    record_id = cursor.lastrowid
    return record_id

def insert_media_collection(user_id, cursor):
    cursor.execute(f"""
        SELECT media_collection_id FROM `{SCHEMA}`.`media_collection`
        WHERE user_id = %s
    """, (user_id,))

    existing_collection = cursor.fetchone()

    if existing_collection:
        return False

    creation_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    insert_query = f"""
        INSERT INTO `{SCHEMA}`.`media_collection` (
            user_id, creation_date, deleted
        ) VALUES (%s, %s, %s)
    """

    values = (
        user_id,
        creation_date,
        0
    )

    cursor.execute(insert_query, values)
    collection_id = cursor.lastrowid

    return collection_id

def insert_media_record(absolute_logo_path, logos_dest_dir, media_collection_id, content_type, cursor):
    file_name = os.path.basename(absolute_logo_path)

    # Check for existing record
    cursor.execute(f"""
        SELECT id FROM `{SCHEMA}`.`media`
        WHERE label = %s
    """, (file_name,))

    existing_media = cursor.fetchone()

    if existing_media:
        return False

    creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    insert_query = f"""
        INSERT INTO `{SCHEMA}`.`media` (
            content_type, creation_date, deleted, label, media_collection_id
        ) VALUES (%s, %s, %s, %s, %s)
    """

    values = (
        content_type,
        creation_date,
        0,
        file_name,
        media_collection_id
    )

    cursor.execute(insert_query, values)
    media_id = cursor.lastrowid

    # Prepare new file path using media ID and original extension
    file_extension = os.path.splitext(file_name)[1]
    new_file_name = f"{media_id}{file_extension}"
    new_file_path = os.path.join(logos_dest_dir, new_file_name)

    # Update path in database
    cursor.execute(f"""
        UPDATE `{SCHEMA}`.`media`
        SET path = %s
        WHERE id = %s
    """, (new_file_path, media_id))

    # Copy file to the new destination
    # os.makedirs(logos_dest_dir, exist_ok=True)
    if not os.path.exists(logos_dest_dir):
        print(f"Creating destination directory: {logos_dest_dir}")
        os.makedirs(logos_dest_dir)
        print(f"destination directory: {logos_dest_dir} created")
    shutil.copy2(absolute_logo_path, new_file_path)

    return media_id


async def main():
    load_dotenv("envs/1.env")
    logos_dest_dir = os.getenv("LOGO_DEST_DIR")
    service_provider_profiles = await load_all_service_provider_profiles()

    cnx = mc.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD,
        database=SCHEMA, auth_plugin="mysql_native_password"
    )
    cur = cnx.cursor(dictionary=True)

    inserted_count = 0
    skipped_count = 0

    try:
        for profile in service_provider_profiles:
            if not profile.get('emails') or not profile.get('name'):
                continue
            try:
                slug = generate_unique_slug(cur, 8)
                establishment_id = insert_establishment(profile, cur, slug)
                for service in profile["services"]:
                    service_id = insert_service(service, cur)
                    if service_id:
                        insert_establishment_service(establishment_id, service_id, cur)

                inserted_count += 1

                user_id = insert_user(profile, establishment_id, cur)
                print(f"Inserted {inserted_count} profiles...")
                if profile.get('logo') and profile.get('logo').strip() and profile.get('logo').strip() != 'None':
                    try:
                        content_type, _ = mimetypes.guess_type(profile.get('logo'))
                        collection_id = insert_media_collection(user_id, cur)
                        if collection_id:
                            media_id = insert_media_record(profile.get('logo'), logos_dest_dir, collection_id, content_type, cur)
                            print(f"Successfully inserted logo record: {media_id}")
                    except Exception as e:
                        print(f"Skipped logo insertion for: {profile.get('logo')}. Error: {e}")

            except IntegrityError as e:
                if e.errno == 1062:
                    skipped_count += 1
                    print(f"Skipped duplicate entry: {profile.get('name')}")
                else:
                    raise e

        cnx.commit()
        print(f"Final insertion complete. Inserted: {inserted_count}, duplicates skipped: {skipped_count}")

    except Exception as e:
        cnx.rollback()
        print(f"Error encountered, rolled back changes: {e}")
        raise e

    finally:
        cur.close()
        cnx.close()

    print(f"Inserted {inserted_count} profiles.")
    print(f"Skipped {skipped_count} duplicate entries.")

if __name__ == "__main__":
    asyncio.run(main())